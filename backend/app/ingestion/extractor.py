"""Page-aware PDF text extraction, normalization, and low-text/scanned detection using PyMuPDF."""
from dataclasses import dataclass, field
from pathlib import Path
import re

import fitz  # PyMuPDF
from fastapi import status

from app.core.exceptions import AppException

LOW_TEXT_CHAR_THRESHOLD = 40
MIN_DOCUMENT_TEXT_CHARS = 20

HEADING_PATTERN = re.compile(
    r"^(?:(?:chapter|section|lecture|module|part|unit)\s+\d+[:.\-\s]*.*|\d+(?:\.\d+){0,2}\s+[A-Z][^\n]{2,90}|[A-Z][A-Z0-9\s\-:&]{4,80})$",
    re.IGNORECASE,
)


class PDFExtractionError(AppException):
    """Raised when PDF text extraction fails due to corruption, encryption, or missing text."""

    def __init__(
        self,
        detail: str,
        error_code: str = "PDF_EXTRACTION_FAILED",
        status_code: int = 422,
    ) -> None:
        super().__init__(detail=detail, error_code=error_code, status_code=status_code)


@dataclass
class ParagraphSegment:
    """A normalized paragraph extracted from a specific page with optional section heading."""

    page_number: int
    text: str
    section_title: str | None = None


@dataclass
class ExtractedPage:
    """Extracted and normalized content for a single PDF page."""

    page_number: int
    text: str
    char_count: int
    paragraphs: list[ParagraphSegment] = field(default_factory=list)
    section_title: str | None = None
    is_empty: bool = False
    is_low_text: bool = False


@dataclass
class PDFExtractionResult:
    """Complete result of extracting text and diagnostics from a PDF file."""

    page_count: int
    total_chars: int
    pages: list[ExtractedPage]
    warnings: list[str] = field(default_factory=list)


def normalize_paragraph_text(raw_block_text: str) -> str:
    """Normalize paragraph text by fixing hyphenated line breaks and collapsing extra whitespace."""
    text = raw_block_text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ").replace("\u00ad", "")
    # Rejoin hyphenated word breaks across lines (e.g. "algo-\nrithm" -> "algorithm")
    text = re.sub(r"([A-Za-z])-\s*\n\s*([a-z])", r"\1\2", text)
    # Collapse single line wraps inside a paragraph block into spaces
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    return " ".join(lines).strip()


def normalize_document_text(raw_text: str) -> list[str]:
    """Normalize multi-paragraph text while preserving paragraph boundaries."""
    cleaned = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    raw_paragraphs = re.split(r"\n\s*\n+", cleaned)
    normalized: list[str] = []
    for raw_p in raw_paragraphs:
        norm_p = normalize_paragraph_text(raw_p)
        if norm_p:
            normalized.append(norm_p)
    return normalized


def _detect_heading_candidate(paragraph_text: str) -> str | None:
    """Heuristic check if a short block represents a section or lecture heading."""
    stripped = paragraph_text.strip()
    if 3 <= len(stripped) <= 100 and "\n" not in stripped and not stripped.endswith("."):
        if HEADING_PATTERN.match(stripped):
            return stripped[:255]
    return None


def extract_pdf_content(pdf_source: Path | bytes) -> PDFExtractionResult:
    """Extract page-aware normalized text, headings, and quality warnings using PyMuPDF.

    Raises PDFExtractionError if the PDF is corrupted, encrypted, has 0 pages,
    or contains no extractable text (e.g., purely scanned images).
    """
    try:
        if isinstance(pdf_source, bytes):
            doc = fitz.open(stream=pdf_source, filetype="pdf")
        else:
            doc = fitz.open(str(pdf_source))
    except Exception as exc:
        raise PDFExtractionError(
            f"Unable to open PDF file; the document may be corrupted ({exc}).",
            error_code="CORRUPTED_PDF",
        ) from exc

    try:
        if doc.is_encrypted:
            raise PDFExtractionError(
                "Password-protected or encrypted PDFs cannot be processed.",
                error_code="ENCRYPTED_PDF",
            )

        page_count = len(doc)
        if page_count == 0:
            raise PDFExtractionError(
                "PDF document contains 0 pages.",
                error_code="EMPTY_PDF",
            )

        extracted_pages: list[ExtractedPage] = []
        warnings: list[str] = []
        empty_page_numbers: list[int] = []
        low_text_page_numbers: list[int] = []
        total_chars = 0
        active_section_title: str | None = None

        for page_idx in range(page_count):
            page_num = page_idx + 1
            page = doc[page_idx]
            raw_blocks = page.get_text("blocks")

            # Sort blocks top-to-bottom, left-to-right
            sorted_blocks = sorted(raw_blocks, key=lambda b: (round(b[1], 1), round(b[0], 1)))

            page_paragraphs: list[ParagraphSegment] = []
            page_section_title: str | None = active_section_title

            for block in sorted_blocks:
                block_type = block[6] if len(block) > 6 else 0
                if block_type != 0:
                    continue
                raw_text = str(block[4] or "")
                sub_paragraphs = normalize_document_text(raw_text)
                for para_text in sub_paragraphs:
                    heading = _detect_heading_candidate(para_text)
                    if heading is not None:
                        active_section_title = heading
                        if page_section_title is None:
                            page_section_title = heading

                    page_paragraphs.append(
                        ParagraphSegment(
                            page_number=page_num,
                            text=para_text,
                            section_title=active_section_title,
                        )
                    )

            joined_page_text = "\n\n".join(p.text for p in page_paragraphs)
            char_count = len(joined_page_text)
            total_chars += char_count

            is_empty = char_count == 0
            is_low_text = 0 < char_count < LOW_TEXT_CHAR_THRESHOLD

            if is_empty:
                empty_page_numbers.append(page_num)
            elif is_low_text:
                low_text_page_numbers.append(page_num)

            extracted_pages.append(
                ExtractedPage(
                    page_number=page_num,
                    text=joined_page_text,
                    char_count=char_count,
                    paragraphs=page_paragraphs,
                    section_title=page_section_title,
                    is_empty=is_empty,
                    is_low_text=is_low_text,
                )
            )

        if empty_page_numbers:
            pages_str = ", ".join(str(p) for p in empty_page_numbers[:10])
            suffix = "..." if len(empty_page_numbers) > 10 else ""
            warnings.append(
                f"{len(empty_page_numbers)} page(s) contained no extractable text "
                f"(page(s): {pages_str}{suffix}). Scanned images or blank pages were skipped."
            )

        if low_text_page_numbers:
            pages_str = ", ".join(str(p) for p in low_text_page_numbers[:10])
            suffix = "..." if len(low_text_page_numbers) > 10 else ""
            warnings.append(
                f"{len(low_text_page_numbers)} page(s) had very low text density "
                f"(< {LOW_TEXT_CHAR_THRESHOLD} characters; page(s): {pages_str}{suffix}). "
                f"Diagrams or scanned slides may have limited text coverage."
            )

        if total_chars < MIN_DOCUMENT_TEXT_CHARS:
            raise PDFExtractionError(
                "No extractable text was found in this PDF. The file appears to be a "
                "scanned image-only document or blank PDF. Please upload a PDF with selectable text.",
                error_code="SCANNED_OR_EMPTY_PDF",
            )

        return PDFExtractionResult(
            page_count=page_count,
            total_chars=total_chars,
            pages=extracted_pages,
            warnings=warnings,
        )
    finally:
        doc.close()
