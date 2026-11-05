"""Phase 7 Adaptive Learning & Learning Coach Automated Test Suite.

Verifies:
1. All Mastery Policy patterns (no evidence -> diagnostic, incorrect -> explanation + easier practice,
   partial -> hint + retry, success after hints -> record assisted evidence + test again,
   independent success -> harder practice, repeated independent success -> strong evidence + transfer + future review).
2. Deterministic Python rules for learning state updates (never LLM mastery mutation).
3. Do not claim mastery from one answer (single perfect answer stays LEARNING / EMERGING_EVIDENCE).
4. Uncertainty preservation and evidence history audit trail (LearningEvidence).
5. Student ability to override CoachRecommendation and choose another activity.
6. Concept Progress, Concept Map, Revision Recommendations, and Course Learning Profile APIs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import fitz
from fastapi.testclient import TestClient


def _build_adaptive_course_pdf() -> bytes:
    """Create a multi-page course PDF for adaptive learning tests."""
    doc = fitz.open()

    p1 = doc.new_page()
    p1.insert_text(
        (50, 60),
        "1. Virtual Memory & Address Translation\n\n"
        "The Memory Management Unit (MMU) translates virtual page numbers into physical frame "
        "numbers using page tables stored in main RAM. Because virtual memory decouples process "
        "address spaces from physical RAM, the operating system isolates processes and prevents "
        "unauthorized cross-process memory access.",
        fontsize=11,
    )

    p2 = doc.new_page()
    p2.insert_text(
        (50, 60),
        "2. Translation Lookaside Buffer (TLB)\n\n"
        "The Translation Lookaside Buffer (TLB) is a fast hardware cache inside the MMU that "
        "stores recent virtual-to-physical page translations. When a TLB hit occurs, address "
        "translation completes in a single cycle without reading the page table in main memory.",
        fontsize=11,
    )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_adaptation_benchmark_suite() -> None:
    """Run the Phase 7 adaptation benchmark scenarios and assert 100% policy compliance."""
    root_dir = Path(__file__).resolve().parents[2]
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))
    from evaluation.adaptation.benchmark_adaptation import run_adaptation_benchmark

    report = run_adaptation_benchmark()
    assert report["total_scenarios"] == 8
    assert report["passed_scenarios"] == 8
    assert report["pass_rate"] == 1.0


def test_end_to_end_adaptive_session_coach_routing_and_learning_profile_api(
    client: TestClient,
) -> None:
    """Verify full adaptive progression, evidence history, student activity override, and Learning Profile API."""
    # 1. Create user & course and upload PDF
    user_resp = client.post(
        "/api/v1/users",
        json={
            "email": "phase7.adaptive@university.edu",
            "full_name": "Phase 7 Adaptive Student",
            "password": "StrongPassword123!",
        },
    )
    assert user_resp.status_code == 201
    user_id = user_resp.json()["id"]

    course_resp = client.post(
        "/api/v1/courses",
        json={
            "user_id": user_id,
            "title": "Operating Systems: Adaptive Mastery",
            "code": "CS-407",
            "description": "Phase 7 adaptive learning verification course.",
        },
    )
    assert course_resp.status_code == 201
    course_id = course_resp.json()["id"]

    pdf_bytes = _build_adaptive_course_pdf()
    up_resp = client.post(
        f"/api/v1/courses/{course_id}/documents?user_id={user_id}",
        files={"file": ("os_adaptive.pdf", pdf_bytes, "application/pdf")},
    )
    assert up_resp.status_code == 201

    # 2. Inspect initial Course Learning Profile (No evidence -> DIAGNOSTIC_QUESTION)
    profile_init = client.get(
        f"/api/v1/courses/{course_id}/learning-profile?user_id={user_id}"
    )
    assert profile_init.status_code == 200
    prof_data = profile_init.json()
    assert prof_data["total_concepts"] >= 1
    assert prof_data["mastered_concepts_count"] == 0
    assert prof_data["overall_uncertainty_score"] == 1.0

    target_concept = prof_data["concepts"][0]
    concept_id = target_concept["concept_id"]
    assert target_concept["evidence_status"] == "NO_EVIDENCE"
    assert (
        target_concept["recommended_next_action"]["recommended_activity"]
        == "DIAGNOSTIC_QUESTION"
    )

    # 3. Start interactive session -> should begin with DIAGNOSTIC_QUESTION
    start_resp = client.post(
        "/api/v1/sessions",
        json={
            "user_id": user_id,
            "course_id": course_id,
            "concept_id": concept_id,
            "learning_goal": "Understand MMU address translation and isolation.",
        },
    )
    assert start_resp.status_code == 201
    session_data = start_resp.json()
    session_id = session_data["id"]
    assert session_data["current_activity"]["activity_type"] == "DIAGNOSTIC_QUESTION"

    # 4. Pattern A: Incorrect answer -> Coach recommends EXPLANATION (and student can override to EASIER_PRACTICE)
    act1_id = session_data["current_activity"]["id"]
    sub1_resp = client.post(
        f"/api/v1/sessions/{session_id}/submit-answer",
        json={
            "user_id": user_id,
            "activity_id": act1_id,
            "response_text": "Virtual memory makes the CPU clock speed faster without using RAM.",
        },
    )
    assert sub1_resp.status_code == 200
    sub1_data = sub1_resp.json()
    assert sub1_data["evaluation"]["verdict"] in {"INCORRECT", "OFF_TOPIC"}
    assert sub1_data["coach_recommendation"]["recommended_activity"] == "EXPLANATION"
    assert sub1_data["coach_recommendation"]["difficulty"] == "BASIC"
    assert sub1_data["concept_progress"]["mastery_status"] == "NEEDS_REVIEW"
    assert sub1_data["learning_evidence"]["evidence_type"] in {
        "INCORRECT_ATTEMPT_EVIDENCE",
        "MISCONCEPTION_EVIDENCE",
    }
    assert len(sub1_data["coach_recommendation"]["alternative_activities"]) >= 2

    # Student exercises autonomy: chooses EASIER_PRACTICE instead of EXPLANATION
    next1_resp = client.post(
        f"/api/v1/sessions/{session_id}/next-activity",
        json={
            "user_id": user_id,
            "requested_activity_type": "EASIER_PRACTICE",
            "student_confirmed": True,
        },
    )
    assert next1_resp.status_code == 200
    act2 = next1_resp.json()["current_activity"]
    assert act2["activity_type"] == "EASIER_PRACTICE"
    assert act2["difficulty"] == "BASIC"

    # 5. Pattern B: Partial answer (only 1 of 2 required ideas) -> PARTIALLY_CORRECT -> HINT_AND_RETRY
    partial_answer = (
        "The Memory Management Unit (MMU) translates virtual page numbers into physical frame "
        "numbers using page tables stored in main RAM."
    )
    sub_partial_resp = client.post(
        f"/api/v1/sessions/{session_id}/submit-answer",
        json={
            "user_id": user_id,
            "activity_id": act2["id"],
            "response_text": partial_answer,
        },
    )
    assert sub_partial_resp.status_code == 200
    sub_partial_data = sub_partial_resp.json()
    assert sub_partial_data["evaluation"]["verdict"] == "PARTIALLY_CORRECT"
    assert (
        sub_partial_data["coach_recommendation"]["recommended_activity"]
        == "HINT_AND_RETRY"
    )
    assert (
        sub_partial_data["coach_recommendation"]["evidence_status"]
        == "DEVELOPING_EVIDENCE"
    )

    # Advance to HINT_AND_RETRY (which pre-reveals Hint #1 automatically)
    next_hint_retry_resp = client.post(
        f"/api/v1/sessions/{session_id}/next-activity",
        json={"user_id": user_id},
    )
    assert next_hint_retry_resp.status_code == 200
    act_hint_retry = next_hint_retry_resp.json()["current_activity"]
    assert act_hint_retry["activity_type"] == "HINT_AND_RETRY"
    assert len(act_hint_retry["hints_used"]) >= 1

    # 6. Pattern C: Success after hints -> record assisted evidence, test again (TARGETED_PRACTICE)
    full_grounded_answer = (
        "The Memory Management Unit (MMU) translates virtual page numbers into physical frame "
        "numbers using page tables stored in main RAM. Because virtual memory decouples process "
        "address spaces from physical RAM, the operating system isolates processes and prevents "
        "unauthorized cross-process memory access. Furthermore, the Translation Lookaside Buffer (TLB) "
        "is a fast hardware cache inside the MMU that stores recent virtual-to-physical page translations "
        "so a TLB hit completes translation in a single cycle without reading main memory."
    )
    sub2_resp = client.post(
        f"/api/v1/sessions/{session_id}/submit-answer",
        json={
            "user_id": user_id,
            "activity_id": act_hint_retry["id"],
            "response_text": full_grounded_answer,
        },
    )
    assert sub2_resp.status_code == 200
    sub2_data = sub2_resp.json()
    assert sub2_data["evaluation"]["verdict"] == "CORRECT"
    assert (
        sub2_data["coach_recommendation"]["evidence_status"] == "ASSISTED_PROFICIENCY"
    )
    assert (
        sub2_data["coach_recommendation"]["recommended_activity"] == "TARGETED_PRACTICE"
    )
    assert sub2_data["concept_progress"]["mastery_status"] != "MASTERED"

    # 7. Pattern D: First independent success -> never claim mastery from one unassisted answer -> HARDER_PRACTICE
    next2_resp = client.post(
        f"/api/v1/sessions/{session_id}/next-activity",
        json={"user_id": user_id},
    )
    assert next2_resp.status_code == 200
    act3 = next2_resp.json()["current_activity"]
    assert act3["activity_type"] == "TARGETED_PRACTICE"

    sub3_resp = client.post(
        f"/api/v1/sessions/{session_id}/submit-answer",
        json={
            "user_id": user_id,
            "activity_id": act3["id"],
            "response_text": full_grounded_answer,
        },
    )
    assert sub3_resp.status_code == 200
    sub3_data = sub3_resp.json()
    assert sub3_data["evaluation"]["verdict"] == "CORRECT"
    assert sub3_data["coach_recommendation"]["evidence_status"] == "EMERGING_EVIDENCE"
    assert (
        sub3_data["coach_recommendation"]["recommended_activity"] == "HARDER_PRACTICE"
    )
    assert sub3_data["coach_recommendation"]["difficulty"] == "ADVANCED"
    # Rule: Do NOT claim mastery after a single independent success
    assert sub3_data["concept_progress"]["mastery_status"] == "LEARNING"
    assert sub3_data["concept_progress"]["mastery_score"] <= 76.0

    # 8. Pattern E: Repeated independent success -> MASTERED + TRANSFER_QUESTION + scheduled future review
    next3_resp = client.post(
        f"/api/v1/sessions/{session_id}/next-activity",
        json={"user_id": user_id},
    )
    assert next3_resp.status_code == 200
    act4 = next3_resp.json()["current_activity"]
    assert act4["activity_type"] == "HARDER_PRACTICE"
    assert act4["difficulty"] == "ADVANCED"

    sub4_resp = client.post(
        f"/api/v1/sessions/{session_id}/submit-answer",
        json={
            "user_id": user_id,
            "activity_id": act4["id"],
            "response_text": full_grounded_answer,
        },
    )
    assert sub4_resp.status_code == 200
    sub4_data = sub4_resp.json()
    assert sub4_data["evaluation"]["verdict"] == "CORRECT"
    assert (
        sub4_data["coach_recommendation"]["evidence_status"]
        == "STRONG_INDEPENDENT_EVIDENCE"
    )
    assert (
        sub4_data["coach_recommendation"]["recommended_activity"]
        == "TRANSFER_QUESTION"
    )
    assert sub4_data["concept_progress"]["mastery_status"] == "MASTERED"
    assert sub4_data["concept_progress"]["mastery_score"] >= 84.0
    assert sub4_data["concept_progress"]["next_review_at"] is not None

    # 9. Verify Course Learning Profile, Concept Progress, Concept Map, and Revision Task endpoints
    profile_after = client.get(
        f"/api/v1/courses/{course_id}/learning-profile?user_id={user_id}"
    )
    assert profile_after.status_code == 200
    prof_after_data = profile_after.json()
    assert prof_after_data["mastered_concepts_count"] >= 1
    assert len(prof_after_data["recent_activity"]) == 5
    assert len(prof_after_data["observed_strengths"]) >= 1
    assert len(prof_after_data["revision_recommendations"]) >= 1

    concept_prog_resp = client.get(
        f"/api/v1/courses/{course_id}/concepts/{concept_id}/progress?user_id={user_id}"
    )
    assert concept_prog_resp.status_code == 200
    cp_item = concept_prog_resp.json()
    assert cp_item["mastery_status"] == "MASTERED"
    assert cp_item["independent_success_count"] == 2
    assert cp_item["assisted_success_count"] == 1
    assert len(cp_item["recent_evidence"]) == 5

    cmap_resp = client.get(
        f"/api/v1/courses/{course_id}/concept-map?user_id={user_id}"
    )
    assert cmap_resp.status_code == 200
    assert len(cmap_resp.json()) >= 1

    # Complete the scheduled revision task via PATCH /api/v1/revision-tasks/{task_id}
    rev_task_id = prof_after_data["revision_recommendations"][0]["id"]
    patch_resp = client.patch(
        f"/api/v1/revision-tasks/{rev_task_id}?user_id={user_id}",
        json={"status": "COMPLETED"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "COMPLETED"
    assert patch_resp.json()["completed_at"] is not None
