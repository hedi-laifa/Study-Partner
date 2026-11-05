"""Automated tests for Phase 5: Interactive Study Session."""

from __future__ import annotations

import fitz  # PyMuPDF
from fastapi.testclient import TestClient


def _create_os_course_pdf() -> bytes:
    """Build a multi-page Operating Systems PDF for interactive session testing."""
    doc = fitz.open()
    pages = [
        (
            "1. Virtual Memory and MMU Address Translation",
            (
                "Virtual memory abstracts physical RAM by providing each process with an isolated "
                "virtual address space. The hardware Memory Management Unit (MMU) translates virtual "
                "page numbers into physical frame numbers using a multi-level page table. When a virtual "
                "page is unmapped, the MMU triggers a page fault trap so the OS kernel can load the page "
                "from disk into a free physical frame."
            ),
        ),
        (
            "2. Translation Lookaside Buffer (TLB) Caching",
            (
                "Because walking a multi-level page table in main memory requires multiple memory accesses, "
                "CPUs include a Translation Lookaside Buffer (TLB) hardware cache. A TLB hit resolves "
                "virtual-to-physical translation in a single cycle, whereas a TLB miss requires a page "
                "table walk. Address Space Identifiers (ASIDs) tag TLB entries by process to avoid flushing "
                "the entire TLB on every context switch."
            ),
        ),
    ]
    for heading, body in pages:
        page = doc.new_page()
        page.insert_textbox(
            fitz.Rect(50, 50, 545, 780),
            f"{heading}\n\n{body}",
            fontsize=11,
        )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _setup_student_course_and_pdf(client: TestClient) -> tuple[str, str, str]:
    """Create a user, create a course, upload a 2-page PDF, and return (user_id, course_id, doc_id)."""
    user_resp = client.post(
        "/api/v1/users",
        json={
            "email": "session_student@uni.edu",
            "full_name": "Session Student",
            "password": "Password123!",
        },
    )
    assert user_resp.status_code == 201
    user_id = user_resp.json()["id"]

    course_resp = client.post(
        "/api/v1/courses",
        json={
            "user_id": user_id,
            "title": "Operating Systems",
            "code": "CS-401",
            "description": "Virtual memory, MMU page tables, and TLB caching.",
        },
    )
    assert course_resp.status_code == 201
    course_id = course_resp.json()["id"]

    pdf_bytes = _create_os_course_pdf()
    upload_resp = client.post(
        f"/api/v1/courses/{course_id}/documents?user_id={user_id}",
        files={"file": ("os_virtual_memory.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["id"]
    return user_id, course_id, doc_id


def test_complete_interactive_study_session_lifecycle(client: TestClient) -> None:
    """Test create session -> hints -> explain -> submit answer (with dedup) -> next activity -> end session."""
    user_id, course_id, _ = _setup_student_course_and_pdf(client)

    # 1. Fetch auto-extracted concepts for the course
    concepts_resp = client.get(f"/api/v1/courses/{course_id}/concepts?user_id={user_id}")
    assert concepts_resp.status_code == 200
    concepts = concepts_resp.json()
    assert len(concepts) >= 2
    target_concept_id = concepts[0]["id"]

    # 2. Start a study session on the selected concept and learning goal
    start_resp = client.post(
        "/api/v1/sessions",
        json={
            "user_id": user_id,
            "course_id": course_id,
            "concept_id": target_concept_id,
            "learning_goal": "Understand how MMU page tables translate virtual addresses and handle page faults",
        },
    )
    assert start_resp.status_code == 201
    session = start_resp.json()
    session_id = session["id"]
    assert session["state"] == "DIAGNOSTIC"
    assert session["course_id"] == course_id
    assert session["current_concept_id"] == target_concept_id
    assert session["current_activity"] is not None
    first_act = session["current_activity"]
    assert first_act["activity_type"] == "DIAGNOSTIC_QUESTION"
    assert first_act["status"] == "ACTIVE"
    assert first_act["order_index"] == 0
    assert len(first_act["relevant_pages"]) >= 1

    # 3. Verify invalid transition: cannot advance to next activity before answering the active question
    premature_next = client.post(
        f"/api/v1/sessions/{session_id}/next-activity",
        json={"user_id": user_id},
    )
    assert premature_next.status_code == 409
    assert premature_next.json()["error_code"] == "INVALID_SESSION_STATE"

    # 4. Request graduated hints (Level 1, Level 2, Level 3)
    hint1_resp = client.post(
        f"/api/v1/sessions/{session_id}/hint",
        json={"user_id": user_id},
    )
    assert hint1_resp.status_code == 200
    h1 = hint1_resp.json()
    assert h1["hint_level"] == 1
    assert h1["max_hints"] == 3
    assert len(h1["hint_text"]) > 10

    hint2_resp = client.post(
        f"/api/v1/sessions/{session_id}/hint",
        json={"user_id": user_id},
    )
    assert hint2_resp.status_code == 200
    h2 = hint2_resp.json()
    assert h2["hint_level"] == 2
    assert h2["hint_text"] != h1["hint_text"]

    # 5. Request a concise grounded explanation
    explain_resp = client.post(
        f"/api/v1/sessions/{session_id}/explain",
        json={"user_id": user_id},
    )
    assert explain_resp.status_code == 200
    expl = explain_resp.json()
    assert len(expl["explanation"]) > 20
    assert len(expl["relevant_pages"]) >= 1

    # 6. Submit a strong, well-reasoned answer to the diagnostic question
    strong_answer = (
        "The hardware Memory Management Unit (MMU) translates virtual page numbers into physical "
        "frame addresses using a hierarchical page table because each process operates in an isolated "
        "virtual address space. When a process references an unmapped virtual page, the MMU raises a "
        "page fault trap to the operating system kernel so the OS can load the page into physical RAM."
    )
    submit_resp = client.post(
        f"/api/v1/sessions/{session_id}/submit-answer",
        json={
            "user_id": user_id,
            "activity_id": first_act["id"],
            "response_text": strong_answer,
            "time_spent_seconds": 45,
            "idempotency_key": "req-act1-submit-1",
        },
    )
    assert submit_resp.status_code == 200
    sub_body = submit_resp.json()
    assert sub_body["duplicate_prevented"] is False
    assert sub_body["evaluation"]["total_score"] >= 80.0
    assert sub_body["evaluation"]["passed"] is True
    assert sub_body["session"]["state"] == "FEEDBACK_READY"
    assert sub_body["session"]["progress"]["completed_activities_count"] == 1
    assert sub_body["session"]["progress"]["total_attempts_submitted"] == 1
    # Because 2 hints were used, Phase 7 Learning Coach records assisted evidence and keeps difficulty at INTERMEDIATE for TARGETED_PRACTICE
    assert sub_body["session"]["progress"]["current_difficulty"] == "INTERMEDIATE"
    assert sub_body["coach_recommendation"]["recommended_activity"] == "TARGETED_PRACTICE"

    # 7. Duplicate attempt protection: re-sending the same request must be idempotent and NOT create a 2nd attempt
    dup_resp = client.post(
        f"/api/v1/sessions/{session_id}/submit-answer",
        json={
            "user_id": user_id,
            "activity_id": first_act["id"],
            "response_text": strong_answer,
            "idempotency_key": "req-act1-submit-1",
        },
    )
    assert dup_resp.status_code == 200
    dup_body = dup_resp.json()
    assert dup_body["duplicate_prevented"] is True
    assert dup_body["attempt"]["id"] == sub_body["attempt"]["id"]
    assert dup_body["session"]["progress"]["total_attempts_submitted"] == 1

    # Submitting a DIFFERENT answer while in FEEDBACK_READY (activity already COMPLETED) must return 409
    different_while_completed = client.post(
        f"/api/v1/sessions/{session_id}/submit-answer",
        json={
            "user_id": user_id,
            "activity_id": first_act["id"],
            "response_text": "A completely different second submission after completion.",
        },
    )
    assert different_while_completed.status_code == 409

    # 8. Retrieve session (simulating page reload / session resumption)
    get_resp = client.get(f"/api/v1/sessions/{session_id}?user_id={user_id}")
    assert get_resp.status_code == 200
    fetched = get_resp.json()
    assert fetched["id"] == session_id
    assert fetched["progress"]["hints_used_count"] == 2
    assert fetched["progress"]["explanations_requested_count"] == 1
    assert len(fetched["activity_history"]) == 1
    assert len(fetched["activity_history"][0]["hints_used"]) == 2
    assert fetched["activity_history"][0]["explanation_requested"] is not None

    # 9. Continue with the next activity (difficulty adapted to ADVANCED)
    next_resp = client.post(
        f"/api/v1/sessions/{session_id}/next-activity",
        json={"user_id": user_id},
    )
    assert next_resp.status_code == 200
    next_session = next_resp.json()
    assert next_session["state"] == "QUESTIONING"
    second_act = next_session["current_activity"]
    assert second_act is not None
    assert second_act["id"] != first_act["id"]
    assert second_act["order_index"] == 1
    assert second_act["difficulty"] == "INTERMEDIATE"
    assert second_act["activity_type"] == "TARGETED_PRACTICE"

    # Submit a brief/weak answer to Activity #2 to verify downward difficulty adaptation (INTERMEDIATE -> BASIC)
    submit2_resp = client.post(
        f"/api/v1/sessions/{session_id}/submit-answer",
        json={
            "user_id": user_id,
            "activity_id": second_act["id"],
            "response_text": "Not sure.",
        },
    )
    assert submit2_resp.status_code == 200
    sub2_body = submit2_resp.json()
    assert sub2_body["evaluation"]["total_score"] < 50.0
    assert sub2_body["session"]["progress"]["current_difficulty"] == "BASIC"
    assert sub2_body["session"]["progress"]["completed_activities_count"] == 2

    # 10. End the study session and verify the learning summary
    end_resp = client.post(
        f"/api/v1/sessions/{session_id}/end",
        json={"user_id": user_id},
    )
    assert end_resp.status_code == 200
    ended = end_resp.json()
    assert ended["state"] == "COMPLETED"
    assert ended["completed_at"] is not None
    assert ended["summary"] is not None
    summary = ended["summary"]
    assert summary["total_activities"] == 2
    assert summary["completed_activities"] == 2
    assert summary["total_attempts"] == 2
    assert summary["hints_used_count"] == 2
    assert summary["explanations_requested_count"] == 1
    assert summary["average_score"] > 0.0
    assert len(summary["pages_reviewed"]) >= 1
    assert len(summary["strengths"]) >= 1
    assert len(summary["areas_for_improvement"]) >= 1
    assert len(summary["key_takeaways"]) >= 1
    assert len(summary["recommended_next_steps"]) > 10

    # 11. Verify invalid session states after session completion (all mutations must return 409)
    assert (
        client.post(
            f"/api/v1/sessions/{session_id}/submit-answer",
            json={"user_id": user_id, "response_text": "late answer"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/sessions/{session_id}/hint",
            json={"user_id": user_id},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/sessions/{session_id}/explain",
            json={"user_id": user_id},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/sessions/{session_id}/next-activity",
            json={"user_id": user_id},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/sessions/{session_id}/end",
            json={"user_id": user_id},
        ).status_code
        == 409
    )


def test_interrupted_idle_session_resumption_and_course_sessions_list(
    client: TestClient,
) -> None:
    """Verify an interrupted IDLE session with 0 activities initializes cleanly when resumed."""
    user_id, course_id, _ = _setup_student_course_and_pdf(client)

    # Start a session via API, pause/exit, and verify it appears in the course session list
    start_resp = client.post(
        "/api/v1/sessions",
        json={
            "user_id": user_id,
            "course_id": course_id,
            "learning_goal": "Understand TLB hits, TLB misses, and ASIDs",
        },
    )
    assert start_resp.status_code == 201
    session_id = start_resp.json()["id"]

    # List sessions for the course
    list_resp = client.get(f"/api/v1/courses/{course_id}/sessions?user_id={user_id}")
    assert list_resp.status_code == 200
    sessions = list_resp.json()
    assert len(sessions) == 1
    assert sessions[0]["id"] == session_id

    # Explicitly resume the session via POST /api/v1/sessions/{id}/resume
    resume_resp = client.post(f"/api/v1/sessions/{session_id}/resume?user_id={user_id}")
    assert resume_resp.status_code == 200
    resumed = resume_resp.json()
    assert resumed["id"] == session_id
    assert resumed["current_activity"] is not None
    assert resumed["current_activity"]["status"] == "ACTIVE"
