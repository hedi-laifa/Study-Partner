"""Document ingestion, PDF extraction, validation, and chunking package."""
from app.ingestion.chunker import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    ChunkDraft,
    build_overlapping_chunks,
)
from app.ingestion.extractor import (
    ExtractedPage,
    PDFExtractionError,
    PDFExtractionResult,
    ParagraphSegment,
    extract_pdf_content,
    normalize_document_text,
    normalize_paragraph_text,
)
from app.ingestion.validator import (
    InvalidPDFUploadError,
    sanitize_filename,
    validate_pdf_upload,
)

__all__ = [
    "ChunkDraft",
    "DEFAULT_CHUNK_OVERLAP",
    "DEFAULT_CHUNK_SIZE",
    "ExtractedPage",
    "InvalidPDFUploadError",
    "PDFExtractionError",
    "PDFExtractionResult",
    "ParagraphSegment",
    "build_overlapping_chunks",
    "extract_pdf_content",
    "normalize_document_text",
    "normalize_paragraph_text",
    "sanitize_filename",
    "validate_pdf_upload",
]
