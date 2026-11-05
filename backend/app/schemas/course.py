"""Pydantic schemas for Course, Document, ChunkMetadata, and Concept entities."""
from datetime import datetime
from typing import Any, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CourseCreate(BaseModel):
    """Payload to create a new course owned by a user."""

    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=50)
    description: str | None = None


class CourseUpdate(BaseModel):
    """Payload to update an existing course."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=50)
    description: str | None = None


class CourseRead(BaseModel):
    """Serialized Course response schema."""

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    code: str | None
    description: str | None
    document_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


DocumentStatus = Literal["UPLOADED", "PROCESSING", "READY", "FAILED"]


class DocumentCreate(BaseModel):
    """Payload to create a Document metadata record."""

    user_id: uuid.UUID
    course_id: uuid.UUID
    filename: str = Field(min_length=1, max_length=255)
    file_path: str = Field(min_length=1, max_length=500)
    file_size_bytes: int = Field(ge=0)
    mime_type: str = Field(default="application/pdf", max_length=100)
    page_count: int | None = Field(default=None, ge=0)


class DocumentUpdate(BaseModel):
    """Payload to update Document ingestion state."""

    page_count: int | None = Field(default=None, ge=0)
    chunk_count: int | None = Field(default=None, ge=0)
    status: DocumentStatus | None = None
    error_message: str | None = None
    extraction_warnings: list[str] | None = None


class DocumentRead(BaseModel):
    """Serialized Document response schema."""

    id: uuid.UUID
    user_id: uuid.UUID
    course_id: uuid.UUID
    filename: str
    file_path: str
    file_size_bytes: int
    mime_type: str
    page_count: int | None
    chunk_count: int
    status: str
    error_message: str | None
    extraction_warnings: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChunkMetadataCreate(BaseModel):
    """Payload to register chunk metadata referencing a ChromaDB vector."""

    document_id: uuid.UUID
    course_id: uuid.UUID
    chroma_vector_id: str | None = None
    chunk_index: int = Field(ge=0)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    page_number: int | None = Field(default=None, ge=1)
    section_title: str | None = Field(default=None, max_length=255)
    chunk_text: str | None = None
    text_content: str | None = None
    char_count: int | None = Field(default=None, ge=1)
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_chunk_fields(self) -> "ChunkMetadataCreate":
        resolved_text = self.chunk_text or self.text_content
        if not resolved_text or not resolved_text.strip():
            raise ValueError("Either chunk_text or text_content must be provided.")
        self.chunk_text = resolved_text
        self.text_content = resolved_text

        if self.page_start is None and self.page_number is not None:
            self.page_start = self.page_number
        if self.page_end is None and self.page_start is not None:
            self.page_end = self.page_start
        if self.page_number is None and self.page_start is not None:
            self.page_number = self.page_start

        if self.char_count is None:
            self.char_count = len(resolved_text)
        if not self.chroma_vector_id:
            self.chroma_vector_id = f"{self.document_id}_chunk_{self.chunk_index}"
        return self


class ChunkMetadataRead(BaseModel):
    """Serialized ChunkMetadata response schema."""

    id: uuid.UUID
    document_id: uuid.UUID
    course_id: uuid.UUID
    chroma_vector_id: str
    chunk_index: int
    page_start: int | None
    page_end: int | None
    page_number: int | None
    section_title: str | None
    chunk_text: str
    text_content: str
    char_count: int
    metadata_json: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


ConceptDifficulty = Literal["BASIC", "INTERMEDIATE", "ADVANCED"]


class ConceptCreate(BaseModel):
    """Payload to create an academic Concept within a Course."""

    course_id: uuid.UUID
    source_document_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1)
    difficulty: ConceptDifficulty = "INTERMEDIATE"
    display_order: int = Field(default=0, ge=0)
    source_pages: list[int] = Field(default_factory=list)


class ConceptRead(BaseModel):
    """Serialized Concept response schema."""

    id: uuid.UUID
    course_id: uuid.UUID
    source_document_id: uuid.UUID | None
    title: str
    summary: str
    difficulty: str
    display_order: int
    source_pages: list[int]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
