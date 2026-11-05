"""PDF upload validation and filename sanitization."""
from pathlib import Path
import re

from fastapi import status

from app.core.exceptions import AppException

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/x-pdf",
    "application/acrobat",
    "applications/vnd.pdf",
    "text/pdf",
    "text/x-pdf",
    "application/octet-stream",
}


class InvalidPDFUploadError(AppException):
    """Raised when an uploaded file fails PDF validation checks."""

    def __init__(
        self,
        detail: str,
        error_code: str = "INVALID_PDF_UPLOAD",
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        super().__init__(detail=detail, error_code=error_code, status_code=status_code)


def sanitize_filename(filename: str) -> str:
    """Sanitize a user-provided filename to prevent path traversal and unsafe characters."""
    base_name = Path(filename).name.strip()
    cleaned = re.sub(r"[^A-Za-z0-9._\- ]+", "_", base_name)
    cleaned = re.sub(r"\s+", "_", cleaned).strip("._")
    if not cleaned.lower().endswith(".pdf"):
        cleaned = f"{cleaned}.pdf"
    return cleaned[:200]


def validate_pdf_upload(
    filename: str | None,
    content_type: str | None,
    file_bytes: bytes,
    max_size_mb: int = 50,
) -> str:
    """Validate PDF extension, MIME type, file size, and PDF magic header.

    Returns the sanitized filename if valid; otherwise raises InvalidPDFUploadError.
    """
    if not filename or not filename.strip():
        raise InvalidPDFUploadError("Uploaded file must have a valid filename.")

    if not filename.strip().lower().endswith(".pdf"):
        raise InvalidPDFUploadError(
            "Invalid file extension. Only .pdf files are supported."
        )

    if content_type:
        normalized_mime = content_type.split(";")[0].strip().lower()
        if normalized_mime and normalized_mime not in ALLOWED_MIME_TYPES:
            raise InvalidPDFUploadError(
                f"Unsupported MIME type '{normalized_mime}'. Expected 'application/pdf'."
            )

    file_size = len(file_bytes)
    if file_size == 0:
        raise InvalidPDFUploadError("Uploaded PDF file is empty (0 bytes).")

    max_bytes = max_size_mb * 1024 * 1024
    if file_size > max_bytes:
        raise InvalidPDFUploadError(
            f"PDF file exceeds maximum allowed size of {max_size_mb} MB.",
            error_code="FILE_TOO_LARGE",
            status_code=413,
        )

    header_window = file_bytes[:1024]
    if b"%PDF-" not in header_window:
        raise InvalidPDFUploadError(
            "File content is not a valid PDF document (missing %PDF- header)."
        )

    return sanitize_filename(filename)
