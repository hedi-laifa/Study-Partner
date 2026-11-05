"""Automated tests for Phase 6: Assessment Agent, Explicit Rubrics, Rules, and Benchmark."""

from __future__ import annotations

from pathlib import Path
import uuid

import fitz  # PyMuPDF
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assessment.prompts import (
    ASSESSMENT_PROMPT_VERSION,
    build_assessment_prompts,
    get_assessment_prompt,
)
from app.assessment.rubric import (
    build_explicit_rubric,
    parse_activity_rubric,
    serialize_rubric_for_storage,
    verify_numerical_calculation,
)
from app.assessment.service import AssessmentAgentService
from app.models.learning import ConceptProgress
from app.schemas.assessment import (
    AssessmentSchema,
    NumericalCheckSpec,
)


def _create_phase6_course_pdf() -> bytes:
    """Create a 2-page Operating Systems PDF for Phase 6 integration tests."""
    doc = fitz.open()
    pages = [
        (
            "1. Virtual Memory and MMU Address Translation",
            (
                "Virtual memory abstracts physical RAM by providing each process with an isolated "
                "virtual address space. The hardware Memory Management Unit (MMU) translates virtual "
                "page numbers into physical frame numbers using a page table. When a virtual "
                "page is unmapped, the MMU triggers a page fault trap so the OS kernel can load the page "
                "from disk into a free physical frame."
            ),
        ),
        (
            "2. Priority Scheduling and Starvation Mitigation",
            (
                "Preemptive priority scheduling allocates the CPU to the highest-priority ready process. "
                "A continuous stream of high-priority processes can cause starvation by indefinitely "
                "blocking low-priority processes. Aging resolves starvation by gradually increasing the "
                "priority of processes that wait in the ready queue for a long time."
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


def test_assessment_schema_validation_and_rules() -> None:
    """Verify AssessmentSchema enforces evidence-backed misconceptions, uncertainty caps, and no mastery assignment."""
    cid = uuid.uuid4()

    # 1. Valid CORRECT schema
    valid = AssessmentSchema(
        concept_id=cid,
        verdict="CORRECT",
        rubric_score=95.0,
        strengths=["Explained MMU virtual-to-physical translation"],
        gaps=[],
        misconception=None,
        evidence=["Matched 2/2 required rubric ideas."],
        confidence=0.92,
        next_activity="ADVANCE_DIFFICULTY",
        feedback_explanation="Excellent explanation of MMU translation.",
    )
    assert valid.verdict == "CORRECT"
    assert valid.error_classification == "NONE"
    assert valid.uncertain_evaluation is False

    # 2. Rule: Do not infer misconceptions without explicit student quote/claim evidence
    with pytest.raises(ValidationError, match="Do not infer misconceptions without explicit evidence"):
        AssessmentSchema(
            concept_id=cid,
            verdict="INCORRECT",
            rubric_score=20.0,
            strengths=[],
            gaps=["Missing page fault trap"],
            misconception="Student confuses MMU with CPU scheduler",
            evidence=["Rubric criterion 1 was not satisfied."],  # No quote or student claim!
            confidence=0.85,
            next_activity="REMEDIATION_EXPLANATION",
            feedback_explanation="Incorrect.",
        )

    # 3. Supported misconception with explicit quote evidence succeeds
    with_evidence = AssessmentSchema(
        concept_id=cid,
        verdict="INCORRECT",
        rubric_score=20.0,
        strengths=[],
        gaps=["Correct MMU direction"],
        misconception="Confuses direction of MMU address translation.",
        evidence=['Student stated: "The MMU translates physical to virtual addresses."'],
        confidence=0.90,
        next_activity="REMEDIATION_EXPLANATION",
        feedback_explanation="The MMU translates virtual addresses to physical frames.",
        error_classification="FACTUAL_MISTAKE",
    )
    assert with_evidence.misconception is not None
    assert with_evidence.error_classification == "FACTUAL_MISTAKE"

    # 4. Rule: Do not claim certainty when an answer is ambiguous / INSUFFICIENT_EVIDENCE
    ambiguous = AssessmentSchema(
        concept_id=cid,
        verdict="INSUFFICIENT_EVIDENCE",
        rubric_score=20.0,
        strengths=[],
        gaps=["Clarify MMU direction"],
        misconception=None,
        evidence=['Student answer is ambiguous: "Either virtual to physical or physical to virtual."'],
        confidence=0.95,  # Should be automatically capped <= 0.55
        next_activity="CLARIFY_AMBIGUOUS_ANSWER",
        feedback_explanation="Your answer is ambiguous.",
        error_classification="AMBIGUOUS_OR_VAGUE",
    )
    assert ambiguous.confidence <= 0.55
    assert ambiguous.uncertain_evaluation is True

    # 5. Rule: Do not assign mastery directly (extra="forbid" rejects mastery_score)
    with pytest.raises(ValidationError):
        AssessmentSchema(
            concept_id=cid,
            verdict="CORRECT",
            rubric_score=90.0,
            strengths=["Good"],
            gaps=[],
            misconception=None,
            evidence=["Matched rubric."],
            confidence=0.9,
            next_activity="ADVANCE_DIFFICULTY",
            feedback_explanation="Good.",
            mastery_score=90.0,  # type: ignore[call-arg]
        )


def test_deterministic_numerical_verification_and_versioned_prompts() -> None:
    """Verify deterministic numeric calculation checks and versioned assessment prompts."""
    spec = NumericalCheckSpec(
        expected_value=110.0,
        tolerance=0.5,
        unit="ns",
        formula_description="EAT = 0.90 * 100 + 0.10 * 200 = 110 ns",
    )

    ok_res = verify_numerical_calculation(
        "EAT = 0.90 * 100 + 0.10 * 200 = 110 ns.", spec
    )
    assert ok_res.applied is True
    assert ok_res.is_correct is True
    assert ok_res.matched_value == 110.0

    wrong_res = verify_numerical_calculation(
        "I computed EAT = 190 ns by multiplying 0.90 by 200.", spec
    )
    assert wrong_res.applied is True
    assert wrong_res.is_correct is False
    assert wrong_res.matched_value == 190.0

    missing_num_res = verify_numerical_calculation(
        "The effective access time is faster with a cache.", spec
    )
    assert missing_num_res.applied is True
    assert missing_num_res.is_correct is False
    assert missing_num_res.extracted_student_values == []

    # Verify versioned prompt registry
    prompt_def = get_assessment_prompt(ASSESSMENT_PROMPT_VERSION)
    assert prompt_def.version == "assessment-v1.0.0"

    cid = uuid.uuid4()
    rubric = build_explicit_rubric(
        concept_id=cid,
        concept_title="TLB Effective Access Time",
        ideal_answer_summary="EAT equals 110 ns.",
        question_text="Calculate the Effective Access Time.",
    )
    stored = serialize_rubric_for_storage(rubric)
    restored = parse_activity_rubric(
        rubric_json=stored,
        concept_id=cid,
        concept_title="TLB Effective Access Time",
        ideal_answer_summary="EAT equals 110 ns.",
        question_text="Calculate the Effective Access Time.",
    )
    assert restored.concept_id == cid
    assert len(restored.criteria) == 2

    sys_p, usr_p = build_assessment_prompts(
        concept_id=str(cid),
        concept_title="TLB Effective Access Time",
        question_text="Calculate EAT.",
        rubric=restored,
        ideal_answer_summary="EAT equals 110 ns.",
        student_answer="EAT = 110 ns",
        numeric_verification=ok_res,
    )
    assert "assessment-v1.0.0" in sys_p
    assert "DO NOT INFER MISCONCEPTIONS WITHOUT EVIDENCE" in sys_p
    assert "110.0 ns" in usr_p


def test_assessment_agent_end_to_end_session_integration(
    client: TestClient, db_session: Session
) -> None:
    """Verify full answer submission -> rubric retrieval -> Assessment Agent -> persistence -> frontend payload."""
    user_resp = client.post(
        "/api/v1/users",
        json={
            "email": "phase6_student@uni.edu",
            "full_name": "Phase 6 Student",
            "password": "Password123!",
        },
    )
    assert user_resp.status_code == 201
    user_id = user_resp.json()["id"]

    course_resp = client.post(
        "/api/v1/courses",
        json={
            "user_id": user_id,
            "title": "Operating Systems Principles",
            "code": "CS-402",
            "description": "MMU translation and priority scheduling.",
        },
    )
    assert course_resp.status_code == 201
    course_id = course_resp.json()["id"]

    pdf_bytes = _create_phase6_course_pdf()
    upload_resp = client.post(
        f"/api/v1/courses/{course_id}/documents?user_id={user_id}",
        files={"file": ("os_phase6.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_resp.status_code == 201

    concepts = client.get(f"/api/v1/courses/{course_id}/concepts?user_id={user_id}").json()
    mmu_concept = concepts[0]

    # Start session
    start_resp = client.post(
        "/api/v1/sessions",
        json={
            "user_id": user_id,
            "course_id": course_id,
            "concept_id": mmu_concept["id"],
            "learning_goal": "Understand MMU virtual-to-physical translation and page fault traps",
        },
    )
    assert start_resp.status_code == 201
    session = start_resp.json()
    session_id = session["id"]
    act1_id = session["current_activity"]["id"]

    # Inspect explicit activity rubric via GET /api/v1/sessions/{session_id}/activities/{activity_id}/rubric
    rubric_resp = client.get(
        f"/api/v1/sessions/{session_id}/activities/{act1_id}/rubric?user_id={user_id}"
    )
    assert rubric_resp.status_code == 200
    rubric_data = rubric_resp.json()
    assert rubric_data["concept_id"] == mmu_concept["id"]
    assert len(rubric_data["required_ideas"]) >= 1
    assert len(rubric_data["criteria"]) == 2
    assert len(rubric_data["misconception_patterns"]) >= 1

    # Submit an answer with an explicit supported misconception
    misconception_answer = (
        "The hardware MMU translates physical to virtual addresses for processes, "
        "and when a page fault happens, the page fault crashes the computer immediately."
    )
    sub1_resp = client.post(
        f"/api/v1/sessions/{session_id}/submit-answer",
        json={
            "user_id": user_id,
            "activity_id": act1_id,
            "response_text": misconception_answer,
        },
    )
    assert sub1_resp.status_code == 200
    sub1 = sub1_resp.json()

    # Original answer must be preserved verbatim
    assert sub1["attempt"]["response_text"] == misconception_answer

    eval1 = sub1["evaluation"]
    assert eval1["concept_id"] == mmu_concept["id"]
    assert eval1["verdict"] == "INCORRECT"
    assert eval1["rubric_score"] < 40.0
    assert eval1["misconception"] is not None
    assert "physical" in eval1["misconception"].lower()
    assert len(eval1["evidence"]) >= 1
    assert "Student stated:" in eval1["evidence"][0]
    assert eval1["error_classification"] == "FACTUAL_MISTAKE"
    assert eval1["next_activity"] == "REMEDIATION_EXPLANATION"
    assert eval1["prompt_version"] == "assessment-v1.0.0"

    # Advance to Activity #2 and submit an ambiguous answer
    next_resp = client.post(
        f"/api/v1/sessions/{session_id}/next-activity",
        json={"user_id": user_id},
    )
    assert next_resp.status_code == 200
    act2_id = next_resp.json()["current_activity"]["id"]

    ambiguous_answer = (
        "The MMU translates virtual to physical or physical to virtual depending on the OS, "
        "I am not sure which direction is used."
    )
    sub2_resp = client.post(
        f"/api/v1/sessions/{session_id}/submit-answer",
        json={
            "user_id": user_id,
            "activity_id": act2_id,
            "response_text": ambiguous_answer,
        },
    )
    assert sub2_resp.status_code == 200
    eval2 = sub2_resp.json()["evaluation"]
    assert eval2["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert eval2["uncertain_evaluation"] is True
    assert eval2["confidence"] <= 0.55
    assert eval2["misconception"] is None
    assert eval2["error_classification"] == "AMBIGUOUS_OR_VAGUE"
    assert eval2["next_activity"] == "CLARIFY_AMBIGUOUS_ANSWER"

    # Rule verification: AssessmentSchema contains no mastery_score/mastery_status fields,
    # and deterministic LearningCoachService never claims MASTERED after incorrect/uncertain answers
    assert "mastery_score" not in eval2
    assert "mastery_status" not in eval2
    progress_rows = list(
        db_session.scalars(
            select(ConceptProgress).where(
                ConceptProgress.user_id == uuid.UUID(user_id),
                ConceptProgress.concept_id == uuid.UUID(mmu_concept["id"]),
            )
        ).all()
    )
    assert len(progress_rows) == 1
    assert progress_rows[0].mastery_status != "MASTERED"


def test_human_reviewed_assessment_benchmark_agreement() -> None:
    """Run the 18-case human-reviewed benchmark and assert agreement across all 6 answer categories."""
    import sys

    root_dir = Path(__file__).resolve().parents[2]
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))
    from evaluation.assessment.benchmark_assessment import run_assessment_benchmark

    bm_path = root_dir / "evaluation" / "assessment" / "human_reviewed_benchmark.json"
    metrics, predictions = run_assessment_benchmark(benchmark_path=bm_path)

    assert metrics.total_cases == 18
    assert len(predictions) == 18

    # Verify all 6 required answer categories are present and achieve high agreement with human labels
    required_categories = {"correct", "partial", "incorrect", "vague", "off-topic", "ambiguous"}
    assert required_categories.issubset(set(metrics.per_category_accuracy.keys()))

    assert metrics.verdict_accuracy >= 0.90
    assert metrics.cohens_kappa >= 0.85
    assert metrics.false_positive_misconceptions == 0
    assert metrics.misconception_precision == 1.0
    assert metrics.misconception_recall == 1.0
    assert metrics.error_classification_accuracy >= 0.90
    assert metrics.uncertainty_calibration_rate == 1.0
