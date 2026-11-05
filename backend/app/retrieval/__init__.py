"""Vector embeddings, persistent ChromaDB store, and semantic retrieval package."""
from app.retrieval.embeddings import (
    EmbeddingGenerationError,
    EmbeddingService,
    get_embedding_service,
)
from app.retrieval.retriever import (
    RetrievalOutcome,
    RetrievalService,
    RetrievedPassage,
)
from app.retrieval.vector_store import (
    PersistentChromaStore,
    VectorRecord,
    VectorSearchMatch,
    cosine_similarity,
    get_vector_store,
)

__all__ = [
    "EmbeddingGenerationError",
    "EmbeddingService",
    "PersistentChromaStore",
    "RetrievalOutcome",
    "RetrievalService",
    "RetrievedPassage",
    "VectorRecord",
    "VectorSearchMatch",
    "cosine_similarity",
    "get_embedding_service",
    "get_vector_store",
]
