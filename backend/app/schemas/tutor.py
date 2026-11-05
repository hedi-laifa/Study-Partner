"""Pydantic schemas for RAG Retrieval and AI Tutor Q&A."""
from typing import Literal
import uuid

from pydantic import BaseModel, Field


class ConversationTurn(BaseModel):
    """A single turn in the student-tutor conversation history."""

    role: Literal["student", "tutor"]
    content: str = Field(min_length=1, max_length=4000)


class TutorAskRequest(BaseModel):
    """Request payload for POST /api/courses/{id}/ask."""

    question: str = Field(min_length=2, max_length=2000)
    user_id: uuid.UUID | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    conversation_history: list[ConversationTurn] = Field(default_factory=list)


class SourceReference(BaseModel):
    """Citation reference for a retrieved course document chunk."""

    source_index: int
    course_id: uuid.UUID | None = None
    document_id: uuid.UUID
    filename: str
    chunk_index: int
    page_start: int
    page_end: int
    section_title: str | None = None
    excerpt: str
    relevance_score: float


class RetrievalMetadataSchema(BaseModel):
    """Diagnostic metadata about the semantic retrieval and LLM execution."""

    top_k_requested: int
    passages_retrieved: int
    total_candidates_indexed: int
    retrieval_latency_ms: float
    embedding_model: str
    llm_model: str
    max_relevance_score: float


class TutorLLMOutput(BaseModel):
    """Structured JSON schema expected from the Ollama Tutor LLM call."""

    answer: str = Field(description="Grounded explanation citing [Source N, p. X]")
    comprehension_questions: list[str] = Field(
        default_factory=list,
        description="1 to 3 follow-up check-for-understanding questions",
    )
    hints: list[str] = Field(
        default_factory=list,
        description="1 to 3 pedagogical hints to help answer the comprehension questions",
    )
    cited_source_indices: list[int] = Field(
        default_factory=list,
        description="1-based indices of the sources actually used in the answer",
    )
    insufficient_evidence: bool = Field(
        default=False,
        description="True if the provided passages do not contain enough evidence to answer the question",
    )


class TutorAskResponse(BaseModel):
    """Response payload returned by POST /api/courses/{id}/ask."""

    answer: str
    comprehension_questions: list[str] = Field(default_factory=list)
    hints: list[str] = Field(default_factory=list)
    source_references: list[SourceReference] = Field(default_factory=list)
    relevant_pages: list[int] = Field(default_factory=list)
    relevant_page_numbers: list[int] = Field(default_factory=list)
    retrieval_metadata: RetrievalMetadataSchema
    insufficient_evidence: bool = False
