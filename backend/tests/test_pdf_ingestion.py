"""Tests for Phase 3 Course Management and PDF Ingestion Pipeline."""
from pathlib import Path

import fitz  # PyMuPDF
from fastapi.testclient import TestClient
import pytest

from app.core.config import settings


def _build_multi_page_test_pdf() -> bytes:
    """Create an in-memory 4-page PDF with headings, hyphenation, an empty page, and a low-text page."""
    doc = fitz.open()

    # Page 1: Heading + rich paragraphs with hyphenated line break
    page1 = doc.new_page()
    page1_text = (
        "Chapter 1: Process Scheduling\n\n"
        "Operating systems allocate CPU time across runnable processes using preemp-\n"
        "tive and non-preemptive scheduling algorithms. In preemptive scheduling, a higher "
        "priority task can interrupt a currently running lower priority task immediately.\n\n"
        "Turnaround time measures the total time from process submission to completion, "
        "whereas waiting time measures only the time spent in the ready queue."
    )
    page1.insert_text((50, 60), page1_text, fontsize=11)

    # Page 2: Intentionally blank page (0 extractable chars) -> triggers empty page warning
    doc.new_page()

    # Page 3: Very low text density (< 40 chars) -> triggers low-text warning
    page3 = doc.new_page()
    page3.insert_text((50, 60), "Fig 1.2 Diagram", fontsize=11)

    # Page 4: Another section with long text to ensure multi-chunk overlapping behavior
    page4 = doc.new_page()
    repeated_explanation = (
        "Starvation occurs when low-priority processes wait indefinitely because a steady "
        "stream of higher-priority processes keeps arriving in the ready queue. "
        "Aging resolves starvation by gradually boosting the priority of waiting processes "
        "proportional to their waiting time in the system. "
    ) * 4
    page4_text = f"1.2 Starvation and Aging\n\n{repeated_explanation}"
    page4.insert_textbox(fitz.Rect(50, 50, 540, 750), page4_text, fontsize=10)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _build_blank_scanned_pdf() -> bytes:
    """Create a valid 2-page PDF containing zero selectable text (simulating a scanned/blank PDF)."""
    doc = fitz.open()
    page1 = doc.new_page()
    # Draw only a vector rectangle (no text)
    page1.draw_rect(fitz.Rect(100, 100, 400, 400), color=(0.2, 0.4, 0.8), width=2)
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _create_user_and_course(
    client: TestClient, email: str = "student1@uni.edu", title: str = "Operating Systems"
) -> tuple[dict, dict]:
    user_resp = client.post(
        "/api/v1/users",
        json={
            "email": email,
            "full_name": "Test Student",
            "password": "Password123!",
        },
    )
    assert user_resp.status_code == 201
    user = user_resp.json()

    course_resp = client.post(
        "/api/v1/courses",
        json={
            "user_id": user["id"],
            "title": title,
            "code": "CS-301",
            "description": "Kernel abstractions and scheduling.",
        },
    )
    assert course_resp.status_code == 201
    return user, course_resp.json()


def test_valid_pdf_upload_extraction_warnings_and_chunk_metadata(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify valid PDF upload extracts pages, normalizes text, detects warnings, and stores ChunkMetadata."""
    monkeypatch.setattr(settings, "UPLOAD_STORAGE_DIR", str(tmp_path / "uploads"))
    user, course = _create_user_and_course(client)
    pdf_bytes = _build_multi_page_test_pdf()

    upload_resp = client.post(
        f"/api/v1/courses/{course['id']}/documents?user_id={user['id']}",
        files={"file": ("Lecture_01_Scheduling.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_resp.status_code == 201
    doc_data = upload_resp.json()

    assert doc_data["course_id"] == course["id"]
    assert doc_data["user_id"] == user["id"]
    assert doc_data["filename"] == "Lecture_01_Scheduling.pdf"
    assert doc_data["status"] == "READY"
    assert doc_data["page_count"] == 4
    assert doc_data["chunk_count"] >= 2
    assert doc_data["error_message"] is None

    # Verify both empty-page (page 2) and low-text (page 3) warnings were reported
    warnings_joined = " ".join(doc_data["extraction_warnings"])
    assert "no extractable text" in warnings_joined
    assert "low text density" in warnings_joined

    # Inspect chunks endpoint
    chunks_resp = client.get(
        f"/api/v1/documents/{doc_data['id']}/chunks?user_id={user['id']}"
    )
    assert chunks_resp.status_code == 200
    chunks = chunks_resp.json()
    assert len(chunks) == doc_data["chunk_count"]

    first_chunk = chunks[0]
    assert first_chunk["document_id"] == doc_data["id"]
    assert first_chunk["course_id"] == course["id"]
    assert first_chunk["chunk_index"] == 0
    assert first_chunk["page_start"] == 1
    assert first_chunk["page_end"] >= 1
    assert first_chunk["section_title"] is not None
    # Verify hyphenated line break "preemp-\ntive" was normalized into "preemptive"
    assert "preemptive" in first_chunk["chunk_text"]

    # Verify indices are sequential 0..N-1
    assert [c["chunk_index"] for c in chunks] == list(range(len(chunks)))


def test_invalid_file_uploads_rejected(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify non-PDF extension, non-PDF bytes, 0-byte file, and oversized PDF are rejected."""
    monkeypatch.setattr(settings, "UPLOAD_STORAGE_DIR", str(tmp_path / "uploads"))
    user, course = _create_user_and_course(client, email="invalid_tester@uni.edu")

    # 1. Non-PDF extension
    resp_txt = client.post(
        f"/api/v1/courses/{course['id']}/documents?user_id={user['id']}",
        files={"file": ("notes.txt", b"Hello world", "text/plain")},
    )
    assert resp_txt.status_code == 400
    assert resp_txt.json()["error_code"] == "INVALID_PDF_UPLOAD"

    # 2. Fake .pdf without %PDF- magic bytes
    resp_fake = client.post(
        f"/api/v1/courses/{course['id']}/documents?user_id={user['id']}",
        files={"file": ("fake.pdf", b"Not a real PDF content", "application/pdf")},
    )
    assert resp_fake.status_code == 400
    assert resp_fake.json()["error_code"] == "INVALID_PDF_UPLOAD"

    # 3. Empty 0-byte file
    resp_empty = client.post(
        f"/api/v1/courses/{course['id']}/documents?user_id={user['id']}",
        files={"file": ("zero.pdf", b"", "application/pdf")},
    )
    assert resp_empty.status_code == 400

    # 4. File exceeding MAX_UPLOAD_SIZE_MB
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    oversized_bytes = b"%PDF-1.7\n" + (b"0" * (1024 * 1024 + 500))
    resp_large = client.post(
        f"/api/v1/courses/{course['id']}/documents?user_id={user['id']}",
        files={"file": ("huge.pdf", oversized_bytes, "application/pdf")},
    )
    assert resp_large.status_code == 413
    assert resp_large.json()["error_code"] == "FILE_TOO_LARGE"


def test_scanned_or_blank_pdf_and_corrupted_pdf_handling(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify scanned/blank PDFs and corrupted PDFs fail explicitly and persist FAILED status."""
    monkeypatch.setattr(settings, "UPLOAD_STORAGE_DIR", str(tmp_path / "uploads"))
    user, course = _create_user_and_course(client, email="scanned_tester@uni.edu")

    # 1. Blank/scanned PDF with 0 selectable text
    blank_pdf = _build_blank_scanned_pdf()
    resp_blank = client.post(
        f"/api/v1/courses/{course['id']}/documents?user_id={user['id']}",
        files={"file": ("Scanned_Slides.pdf", blank_pdf, "application/pdf")},
    )
    assert resp_blank.status_code == 422
    assert resp_blank.json()["error_code"] == "SCANNED_OR_EMPTY_PDF"

    # 2. Corrupted PDF bytes (has %PDF- header but invalid structure)
    corrupted_pdf = b"%PDF-1.7\nthis_is_corrupted_binary_stream_data_without_xref"
    resp_corrupt = client.post(
        f"/api/v1/courses/{course['id']}/documents?user_id={user['id']}",
        files={"file": ("Corrupted.pdf", corrupted_pdf, "application/pdf")},
    )
    assert resp_corrupt.status_code == 422
    assert resp_corrupt.json()["error_code"] == "CORRUPTED_PDF"

    # Verify both failed documents are recorded in the course document list with status="FAILED"
    docs_list = client.get(
        f"/api/v1/courses/{course['id']}/documents?user_id={user['id']}"
    ).json()
    assert len(docs_list) == 2
    assert all(d["status"] == "FAILED" for d in docs_list)
    assert all(d["error_message"] is not None for d in docs_list)


def test_document_ownership_isolation_and_deletion(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify users cannot access or delete another user's documents, and owner deletion cleans up disk and DB."""
    monkeypatch.setattr(settings, "UPLOAD_STORAGE_DIR", str(tmp_path / "uploads"))
    owner, course = _create_user_and_course(client, email="doc_owner@uni.edu")
    intruder_resp = client.post(
        "/api/v1/users",
        json={
            "email": "doc_intruder@uni.edu",
            "full_name": "Intruder",
            "password": "Password123!",
        },
    )
    intruder = intruder_resp.json()

    pdf_bytes = _build_multi_page_test_pdf()

    # Intruder cannot upload to owner's course
    forbidden_upload = client.post(
        f"/api/v1/courses/{course['id']}/documents?user_id={intruder['id']}",
        files={"file": ("Intruder.pdf", pdf_bytes, "application/pdf")},
    )
    assert forbidden_upload.status_code == 403

    # Owner uploads valid PDF
    upload_resp = client.post(
        f"/api/v1/courses/{course['id']}/documents?user_id={owner['id']}",
        files={"file": ("Owner_Notes.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_resp.status_code == 201
    doc_data = upload_resp.json()
    stored_file = Path(doc_data["file_path"])
    assert stored_file.is_file()

    # Intruder cannot view document, chunks, or delete document
    assert (
        client.get(
            f"/api/v1/documents/{doc_data['id']}?user_id={intruder['id']}"
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/api/v1/documents/{doc_data['id']}/chunks?user_id={intruder['id']}"
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/v1/documents/{doc_data['id']}?user_id={intruder['id']}"
        ).status_code
        == 403
    )

    # Owner deletes document -> 204 No Content, file deleted from disk, DB record removed
    del_resp = client.delete(
        f"/api/v1/documents/{doc_data['id']}?user_id={owner['id']}"
    )
    assert del_resp.status_code == 204
    assert not stored_file.exists()

    get_after_del = client.get(
        f"/api/v1/documents/{doc_data['id']}?user_id={owner['id']}"
    )
    assert get_after_del.status_code == 404
