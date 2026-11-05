"""Tutor agent, configurable Ollama client, and grounded explanation package."""
from app.tutor.llm_client import (
    LLMOutputValidationError,
    LLMServiceUnavailableError,
    OllamaLLMClient,
)
from app.tutor.service import (
    TUTOR_SYSTEM_PROMPT,
    TutorService,
    sanitize_untrusted_passage,
)

__all__ = [
    "LLMOutputValidationError",
    "LLMServiceUnavailableError",
    "OllamaLLMClient",
    "TUTOR_SYSTEM_PROMPT",
    "TutorService",
    "sanitize_untrusted_passage",
]
