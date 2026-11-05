"""Local embedding service using Sentence Transformers with deterministic caching and fallback."""
import hashlib
import math
import re
from typing import Any

from fastapi import status

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import logger

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "for", "from",
    "how", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "was",
    "what", "when", "where", "which", "who", "why", "with", "can", "explain", "describe",
}


class EmbeddingGenerationError(AppException):
    """Raised when text embedding generation fails or receives invalid input."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            detail=detail,
            error_code="EMBEDDING_GENERATION_ERROR",
            status_code=422,
        )


def _stem_token(word: str) -> str:
    """Lightweight morphological stemmer for consistent semantic token matching."""
    if len(word) > 6 and word.endswith("ing"):
        return word[:-3]
    if len(word) > 6 and word.endswith("tion"):
        return word[:-4]
    if len(word) > 5 and word.endswith("ed"):
        return word[:-2]
    if len(word) > 5 and word.endswith("es"):
        return word[:-2]
    if len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _extract_semantic_features(text: str) -> dict[str, float]:
    """Extract weighted unigram stems, bigrams, and character n-grams from text."""
    normalized = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    raw_tokens = [t for t in normalized.split() if len(t) > 1 and t not in STOPWORDS]
    if not raw_tokens:
        raw_tokens = [t for t in normalized.split() if t]

    features: dict[str, float] = {}
    stems = [_stem_token(t) for t in raw_tokens]

    # 1. Unigram tokens & stems (highest weight)
    for token, stem in zip(raw_tokens, stems):
        features[f"tok:{token}"] = features.get(f"tok:{token}", 0.0) + 1.5
        features[f"stm:{stem}"] = features.get(f"stm:{stem}", 0.0) + 2.0
        # Character 4-grams for subword resilience
        if len(stem) >= 4:
            for idx in range(len(stem) - 3):
                cgram = stem[idx : idx + 4]
                features[f"cg:{cgram}"] = features.get(f"cg:{cgram}", 0.0) + 0.35

    # 2. Local word bigrams
    for idx in range(len(stems) - 1):
        bigram = f"bi:{stems[idx]}_{stems[idx + 1]}"
        features[bigram] = features.get(bigram, 0.0) + 1.2

    # Sublinear TF scaling: 1 + log(tf)
    return {feat: 1.0 + math.log(weight) if weight > 1.0 else weight for feat, weight in features.items()}


def _compute_feature_hash_embedding(text: str, dimension: int) -> list[float]:
    """Compute an L2-normalized dense vector of `dimension` using signed feature hashing."""
    vector = [0.0] * dimension
    features = _extract_semantic_features(text)
    if not features:
        raise EmbeddingGenerationError("Cannot generate embedding for empty or whitespace-only text.")

    for feat, weight in features.items():
        digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
        h_val = int.from_bytes(digest, "little")
        bucket = h_val % dimension
        sign = 1.0 if ((h_val >> 32) & 1) == 0 else -1.0
        vector[bucket] += sign * weight

    norm = math.sqrt(sum(v * v for v in vector))
    if norm <= 1e-12:
        raise EmbeddingGenerationError("Generated embedding vector has zero norm.")
    return [round(v / norm, 6) for v in vector]


class EmbeddingService:
    """Configurable local embedding service with SHA-256 content caching.

    Uses SentenceTransformers when local model weights are available, and seamlessly
    supports deterministic local 384-dim semantic embeddings in offline/test environments.
    """

    def __init__(
        self,
        model_name: str | None = None,
        dimension: int | None = None,
    ) -> None:
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self.dimension = dimension or settings.EMBEDDING_DIMENSION
        self._cache: dict[str, list[float]] = {}
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self._st_model: Any = None
        self._st_Checked: bool = False

    def _get_sentence_transformer(self) -> Any:
        """Lazily load SentenceTransformer if installed and weights are cached locally."""
        if self._st_Checked:
            return self._st_model
        self._st_Checked = True
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

            self._st_model = SentenceTransformer(
                self.model_name, local_files_only=True
            )
            logger.info(f"Loaded SentenceTransformer model '{self.model_name}'")
        except Exception:
            self._st_model = None
        return self._st_model

    def _cache_key(self, normalized_text: str) -> str:
        digest = hashlib.sha256(
            f"{self.model_name}:{self.dimension}:{normalized_text}".encode("utf-8")
        ).hexdigest()
        return digest

    @staticmethod
    def _validate_and_normalize_input(text: str) -> str:
        if not isinstance(text, str):
            raise EmbeddingGenerationError("Input to embedding service must be a string.")
        cleaned = re.sub(r"\s+", " ", text).strip()
        if not cleaned:
            raise EmbeddingGenerationError(
                "Cannot generate embedding for empty or whitespace-only text."
            )
        return cleaned

    def embed_text(self, text: str) -> list[float]:
        """Generate a normalized embedding vector for a single text string, utilizing cache."""
        cleaned = self._validate_and_normalize_input(text)
        key = self._cache_key(cleaned)

        cached = self._cache.get(key)
        if cached is not None:
            self.cache_hits += 1
            return list(cached)

        self.cache_misses += 1
        st_model = self._get_sentence_transformer()
        if st_model is not None:
            try:
                raw_vec = st_model.encode(cleaned, normalize_embeddings=True)
                embedding = [float(x) for x in raw_vec.tolist()]
            except Exception as exc:
                raise EmbeddingGenerationError(
                    f"SentenceTransformer failed to encode text: {exc}"
                ) from exc
        else:
            embedding = _compute_feature_hash_embedding(cleaned, self.dimension)

        self._cache[key] = embedding
        return list(embedding)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts, avoiding re-computation for cached items."""
        if not texts:
            return []
        return [self.embed_text(t) for t in texts]


_default_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Return the singleton EmbeddingService instance."""
    global _default_embedding_service
    if _default_embedding_service is None or (
        _default_embedding_service.model_name != settings.EMBEDDING_MODEL_NAME
    ):
        _default_embedding_service = EmbeddingService(
            model_name=settings.EMBEDDING_MODEL_NAME,
            dimension=settings.EMBEDDING_DIMENSION,
        )
    return _default_embedding_service
