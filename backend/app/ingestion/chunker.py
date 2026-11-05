"""Overlapping paragraph-aware text chunker preserving page ranges and section titles."""
from dataclasses import dataclass
import re

from app.ingestion.extractor import ExtractedPage, ParagraphSegment

DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 150


@dataclass
class ChunkDraft:
    """In-memory representation of a generated text chunk prior to database persistence."""

    chunk_index: int
    page_start: int
    page_end: int
    section_title: str | None
    chunk_text: str
    char_count: int


def _split_long_paragraph(
    segment: ParagraphSegment, chunk_size: int, chunk_overlap: int
) -> list[ParagraphSegment]:
    """Split a paragraph that exceeds chunk_size along sentence or word boundaries."""
    text = segment.text
    if len(text) <= chunk_size:
        return [segment]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    sub_segments: list[ParagraphSegment] = []
    current_parts: list[str] = []
    current_len = 0

    for sentence in sentences:
        if len(sentence) > chunk_size:
            # Flush existing parts first
            if current_parts:
                sub_segments.append(
                    ParagraphSegment(
                        page_number=segment.page_number,
                        text=" ".join(current_parts).strip(),
                        section_title=segment.section_title,
                    )
                )
                current_parts = []
                current_len = 0

            # Hard window split with overlap for single very long sentence
            step = max(1, chunk_size - chunk_overlap)
            for idx in range(0, len(sentence), step):
                piece = sentence[idx : idx + chunk_size].strip()
                if piece:
                    sub_segments.append(
                        ParagraphSegment(
                            page_number=segment.page_number,
                            text=piece,
                            section_title=segment.section_title,
                        )
                    )
                if idx + chunk_size >= len(sentence):
                    break
            continue

        added_len = len(sentence) if current_len == 0 else current_len + 1 + len(sentence)
        if added_len <= chunk_size:
            current_parts.append(sentence)
            current_len = added_len
        else:
            if current_parts:
                sub_segments.append(
                    ParagraphSegment(
                        page_number=segment.page_number,
                        text=" ".join(current_parts).strip(),
                        section_title=segment.section_title,
                    )
                )
            current_parts = [sentence]
            current_len = len(sentence)

    if current_parts:
        sub_segments.append(
            ParagraphSegment(
                page_number=segment.page_number,
                text=" ".join(current_parts).strip(),
                section_title=segment.section_title,
            )
        )

    return sub_segments


def build_overlapping_chunks(
    pages: list[ExtractedPage],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[ChunkDraft]:
    """Chunk extracted PDF pages into overlapping paragraph-aware chunks with page_start and page_end."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and < chunk_size.")

    all_segments: list[ParagraphSegment] = []
    for page in pages:
        for para in page.paragraphs:
            if para.text.strip():
                all_segments.extend(
                    _split_long_paragraph(para, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
                )

    if not all_segments:
        return []

    chunks: list[ChunkDraft] = []
    window: list[ParagraphSegment] = []
    window_chars = 0

    def _emit_chunk(segments: list[ParagraphSegment], index: int) -> ChunkDraft:
        text = "\n\n".join(s.text for s in segments).strip()
        page_start = min(s.page_number for s in segments)
        page_end = max(s.page_number for s in segments)
        section_title = next(
            (s.section_title for s in reversed(segments) if s.section_title),
            None,
        )
        return ChunkDraft(
            chunk_index=index,
            page_start=page_start,
            page_end=page_end,
            section_title=section_title,
            chunk_text=text,
            char_count=len(text),
        )

    for seg in all_segments:
        sep_len = 2 if window else 0
        if window and (window_chars + sep_len + len(seg.text) > chunk_size):
            chunks.append(_emit_chunk(window, len(chunks)))

            # Retain trailing segments up to chunk_overlap characters
            overlap_window: list[ParagraphSegment] = []
            overlap_chars = 0
            for prev_seg in reversed(window):
                add_len = len(prev_seg.text) + (2 if overlap_window else 0)
                if overlap_chars + add_len <= chunk_overlap or (
                    not overlap_window and len(prev_seg.text) <= chunk_overlap * 2
                ):
                    overlap_window.insert(0, prev_seg)
                    overlap_chars += add_len
                else:
                    break

            # If a single trailing segment was too large for overlap_window, slice its tail text
            if not overlap_window and chunk_overlap > 0 and window:
                last_seg = window[-1]
                tail_text = last_seg.text[-chunk_overlap:].lstrip()
                if tail_text and tail_text != seg.text:
                    overlap_window = [
                        ParagraphSegment(
                            page_number=last_seg.page_number,
                            text=tail_text,
                            section_title=last_seg.section_title,
                        )
                    ]
                    overlap_chars = len(tail_text)

            window = overlap_window
            window_chars = overlap_chars
            sep_len = 2 if window else 0

        window.append(seg)
        window_chars += sep_len + len(seg.text)

    if window:
        # Avoid emitting a duplicate trailing chunk identical to the overlap
        candidate = _emit_chunk(window, len(chunks))
        if not chunks or candidate.chunk_text != chunks[-1].chunk_text:
            chunks.append(candidate)

    return chunks
