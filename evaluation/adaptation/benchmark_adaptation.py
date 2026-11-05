"""Phase 7 Adaptive Learning & Learning Coach Benchmark Runner.

Executes deterministic multi-step learning scenarios verifying every Mastery Policy rule:
1. No evidence -> DIAGNOSTIC_QUESTION
2. Incorrect answer -> EXPLANATION -> EASIER_PRACTICE (BASIC)
3. Partial answer -> HINT_AND_RETRY
4. Success after hints -> record assisted evidence (never MASTERED) -> TARGETED_PRACTICE (test again)
5. First independent success -> never MASTERED from one answer -> HARDER_PRACTICE (ADVANCED)
6. Repeated independent success -> strong evidence (MASTERED) -> TRANSFER_QUESTION + scheduled REVIEW
7. Due for spaced review -> REVIEW
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path
from typing import Any
import uuid

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.learning.mastery_heuristic import compute_transparent_mastery_update  # noqa: E402
from app.learning.routing_policy import select_next_adaptive_activity  # noqa: E402


def run_adaptation_benchmark() -> dict[str, Any]:
    """Run all canonical Phase 7 evaluation pattern scenarios and verify 100% policy compliance."""
    concept_id = uuid.uuid4()
    concept_title = "Virtual Memory & Page Tables"
    session_goal = "Master virtual-to-physical address translation and page fault handling."
    now = datetime.now(timezone.utc)

    scenarios: list[dict[str, Any]] = []

    # Scenario 1: No evidence -> DIAGNOSTIC_QUESTION
    rec_1 = select_next_adaptive_activity(
        concept_id=concept_id,
        concept_title=concept_title,
        session_goal=session_goal,
        attempts_count=0,
        latest_verdict=None,
        latest_score=None,
        hints_used_on_latest=0,
        current_difficulty="INTERMEDIATE",
        independent_success_count=0,
        assisted_success_count=0,
        consecutive_independent_successes=0,
        evidence_status="NO_EVIDENCE",
        uncertainty_score=1.0,
    )
    scenarios.append(
        {
            "scenario_id": "no_evidence_diagnostic",
            "expected_activity": "DIAGNOSTIC_QUESTION",
            "actual_activity": rec_1.recommended_activity,
            "passed": rec_1.recommended_activity == "DIAGNOSTIC_QUESTION"
            and rec_1.policy_rule_applied == "NO_EVIDENCE_DIAGNOSTIC",
            "reason": rec_1.reason,
        }
    )

    # Scenario 2a: Incorrect answer -> EXPLANATION
    out_2a = compute_transparent_mastery_update(
        previous_mastery_score=30.0,
        previous_attempts_count=0,
        previous_correct_count=0,
        previous_independent_success_count=0,
        previous_assisted_success_count=0,
        previous_consecutive_independent=0,
        verdict="INCORRECT",
        rubric_score=20.0,
        hints_used=0,
        difficulty="INTERMEDIATE",
        confidence=0.90,
        uncertain_evaluation=False,
        has_misconception=True,
        now=now,
    )
    rec_2a = select_next_adaptive_activity(
        concept_id=concept_id,
        concept_title=concept_title,
        session_goal=session_goal,
        attempts_count=out_2a.attempts_count,
        latest_verdict="INCORRECT",
        latest_score=20.0,
        hints_used_on_latest=0,
        current_difficulty="INTERMEDIATE",
        independent_success_count=out_2a.independent_success_count,
        assisted_success_count=out_2a.assisted_success_count,
        consecutive_independent_successes=out_2a.consecutive_independent_successes,
        evidence_status=out_2a.evidence_status,
        uncertainty_score=out_2a.uncertainty_score,
        previous_activity_types=["DIAGNOSTIC_QUESTION"],
        latest_misconception="Claimed page tables reside in CPU registers.",
    )
    scenarios.append(
        {
            "scenario_id": "incorrect_answer_explanation",
            "expected_activity": "EXPLANATION",
            "actual_activity": rec_2a.recommended_activity,
            "passed": (
                rec_2a.recommended_activity == "EXPLANATION"
                and rec_2a.difficulty == "BASIC"
                and out_2a.score_delta < 0
                and out_2a.mastery_status == "NEEDS_REVIEW"
            ),
            "reason": rec_2a.reason,
        }
    )

    # Scenario 2b: Incorrect answer after EXPLANATION -> EASIER_PRACTICE
    rec_2b = select_next_adaptive_activity(
        concept_id=concept_id,
        concept_title=concept_title,
        session_goal=session_goal,
        attempts_count=out_2a.attempts_count,
        latest_verdict="INCORRECT",
        latest_score=25.0,
        hints_used_on_latest=0,
        current_difficulty="BASIC",
        independent_success_count=0,
        assisted_success_count=0,
        consecutive_independent_successes=0,
        evidence_status=out_2a.evidence_status,
        uncertainty_score=out_2a.uncertainty_score,
        previous_activity_types=["DIAGNOSTIC_QUESTION", "EXPLANATION"],
    )
    scenarios.append(
        {
            "scenario_id": "incorrect_answer_easier_practice",
            "expected_activity": "EASIER_PRACTICE",
            "actual_activity": rec_2b.recommended_activity,
            "passed": rec_2b.recommended_activity == "EASIER_PRACTICE"
            and rec_2b.difficulty == "BASIC",
            "reason": rec_2b.reason,
        }
    )

    # Scenario 3: Partial answer -> HINT_AND_RETRY
    out_3 = compute_transparent_mastery_update(
        previous_mastery_score=25.0,
        previous_attempts_count=1,
        previous_correct_count=0,
        previous_independent_success_count=0,
        previous_assisted_success_count=0,
        previous_consecutive_independent=0,
        verdict="PARTIALLY_CORRECT",
        rubric_score=58.0,
        hints_used=0,
        difficulty="INTERMEDIATE",
        confidence=0.88,
        uncertain_evaluation=False,
        has_misconception=False,
        now=now,
    )
    rec_3 = select_next_adaptive_activity(
        concept_id=concept_id,
        concept_title=concept_title,
        session_goal=session_goal,
        attempts_count=out_3.attempts_count,
        latest_verdict="PARTIALLY_CORRECT",
        latest_score=58.0,
        hints_used_on_latest=0,
        current_difficulty="INTERMEDIATE",
        independent_success_count=out_3.independent_success_count,
        assisted_success_count=out_3.assisted_success_count,
        consecutive_independent_successes=out_3.consecutive_independent_successes,
        evidence_status=out_3.evidence_status,
        uncertainty_score=out_3.uncertainty_score,
        previous_activity_types=["DIAGNOSTIC_QUESTION"],
        latest_gaps=["Explain how the page fault handler loads the missing frame from disk."],
    )
    scenarios.append(
        {
            "scenario_id": "partial_answer_hint_and_retry",
            "expected_activity": "HINT_AND_RETRY",
            "actual_activity": rec_3.recommended_activity,
            "passed": (
                rec_3.recommended_activity == "HINT_AND_RETRY"
                and out_3.evidence_status == "DEVELOPING_EVIDENCE"
                and out_3.mastery_status != "MASTERED"
            ),
            "reason": rec_3.reason,
        }
    )

    # Scenario 4: Success after hints -> record assisted evidence, test again (TARGETED_PRACTICE)
    out_4 = compute_transparent_mastery_update(
        previous_mastery_score=50.0,
        previous_attempts_count=2,
        previous_correct_count=0,
        previous_independent_success_count=0,
        previous_assisted_success_count=0,
        previous_consecutive_independent=0,
        verdict="CORRECT",
        rubric_score=90.0,
        hints_used=2,
        difficulty="INTERMEDIATE",
        confidence=0.92,
        uncertain_evaluation=False,
        has_misconception=False,
        now=now,
    )
    rec_4 = select_next_adaptive_activity(
        concept_id=concept_id,
        concept_title=concept_title,
        session_goal=session_goal,
        attempts_count=out_4.attempts_count,
        latest_verdict="CORRECT",
        latest_score=90.0,
        hints_used_on_latest=2,
        current_difficulty="INTERMEDIATE",
        independent_success_count=out_4.independent_success_count,
        assisted_success_count=out_4.assisted_success_count,
        consecutive_independent_successes=out_4.consecutive_independent_successes,
        evidence_status=out_4.evidence_status,
        uncertainty_score=out_4.uncertainty_score,
        previous_activity_types=["HINT_AND_RETRY"],
    )
    scenarios.append(
        {
            "scenario_id": "success_after_hints_test_again",
            "expected_activity": "TARGETED_PRACTICE",
            "actual_activity": rec_4.recommended_activity,
            "passed": (
                rec_4.recommended_activity == "TARGETED_PRACTICE"
                and out_4.evidence_status == "ASSISTED_PROFICIENCY"
                and out_4.assisted_success_count == 1
                and out_4.independent_success_count == 0
                and out_4.mastery_status == "LEARNING"
                and out_4.new_mastery_score < 80.0
            ),
            "reason": rec_4.reason,
        }
    )

    # Scenario 5: First independent success -> never claim mastery from one answer -> HARDER_PRACTICE
    out_5 = compute_transparent_mastery_update(
        previous_mastery_score=0.0,
        previous_attempts_count=0,
        previous_correct_count=0,
        previous_independent_success_count=0,
        previous_assisted_success_count=0,
        previous_consecutive_independent=0,
        verdict="CORRECT",
        rubric_score=98.0,
        hints_used=0,
        difficulty="INTERMEDIATE",
        confidence=0.95,
        uncertain_evaluation=False,
        has_misconception=False,
        now=now,
    )
    rec_5 = select_next_adaptive_activity(
        concept_id=concept_id,
        concept_title=concept_title,
        session_goal=session_goal,
        attempts_count=out_5.attempts_count,
        latest_verdict="CORRECT",
        latest_score=98.0,
        hints_used_on_latest=0,
        current_difficulty="INTERMEDIATE",
        independent_success_count=out_5.independent_success_count,
        assisted_success_count=out_5.assisted_success_count,
        consecutive_independent_successes=out_5.consecutive_independent_successes,
        evidence_status=out_5.evidence_status,
        uncertainty_score=out_5.uncertainty_score,
        previous_activity_types=["DIAGNOSTIC_QUESTION"],
    )
    scenarios.append(
        {
            "scenario_id": "first_independent_success_harder_practice",
            "expected_activity": "HARDER_PRACTICE",
            "actual_activity": rec_5.recommended_activity,
            "passed": (
                rec_5.recommended_activity == "HARDER_PRACTICE"
                and rec_5.difficulty == "ADVANCED"
                and out_5.independent_success_count == 1
                and out_5.mastery_status == "LEARNING"
                and out_5.new_mastery_score <= 76.0
                and out_5.evidence_status == "EMERGING_EVIDENCE"
            ),
            "reason": rec_5.reason,
        }
    )

    # Scenario 6: Repeated independent success -> strong evidence (MASTERED) + TRANSFER_QUESTION + future review
    out_6 = compute_transparent_mastery_update(
        previous_mastery_score=out_5.new_mastery_score,
        previous_attempts_count=out_5.attempts_count,
        previous_correct_count=out_5.correct_attempts_count,
        previous_independent_success_count=out_5.independent_success_count,
        previous_assisted_success_count=out_5.assisted_success_count,
        previous_consecutive_independent=out_5.consecutive_independent_successes,
        verdict="CORRECT",
        rubric_score=94.0,
        hints_used=0,
        difficulty="ADVANCED",
        confidence=0.95,
        uncertain_evaluation=False,
        has_misconception=False,
        now=now,
    )
    rec_6 = select_next_adaptive_activity(
        concept_id=concept_id,
        concept_title=concept_title,
        session_goal=session_goal,
        attempts_count=out_6.attempts_count,
        latest_verdict="CORRECT",
        latest_score=94.0,
        hints_used_on_latest=0,
        current_difficulty="ADVANCED",
        independent_success_count=out_6.independent_success_count,
        assisted_success_count=out_6.assisted_success_count,
        consecutive_independent_successes=out_6.consecutive_independent_successes,
        evidence_status=out_6.evidence_status,
        uncertainty_score=out_6.uncertainty_score,
        previous_activity_types=["DIAGNOSTIC_QUESTION", "HARDER_PRACTICE"],
    )
    scenarios.append(
        {
            "scenario_id": "repeated_independent_success_transfer_and_review",
            "expected_activity": "TRANSFER_QUESTION",
            "actual_activity": rec_6.recommended_activity,
            "passed": (
                rec_6.recommended_activity == "TRANSFER_QUESTION"
                and rec_6.difficulty == "ADVANCED"
                and out_6.mastery_status == "MASTERED"
                and out_6.new_mastery_score >= 84.0
                and out_6.evidence_status == "STRONG_INDEPENDENT_EVIDENCE"
                and out_6.next_review_at >= now + timedelta(days=2)
            ),
            "reason": rec_6.reason,
        }
    )

    # Scenario 7: Due for spaced review -> REVIEW
    rec_7 = select_next_adaptive_activity(
        concept_id=concept_id,
        concept_title=concept_title,
        session_goal=session_goal,
        attempts_count=out_6.attempts_count,
        latest_verdict="CORRECT",
        latest_score=94.0,
        hints_used_on_latest=0,
        current_difficulty="ADVANCED",
        independent_success_count=out_6.independent_success_count,
        assisted_success_count=0,
        consecutive_independent_successes=2,
        evidence_status="DUE_FOR_REVIEW",
        uncertainty_score=out_6.uncertainty_score,
        evidence_recency_hours=96.0,
        is_due_for_review=True,
    )
    scenarios.append(
        {
            "scenario_id": "spaced_review_due",
            "expected_activity": "REVIEW",
            "actual_activity": rec_7.recommended_activity,
            "passed": rec_7.recommended_activity == "REVIEW",
            "reason": rec_7.reason,
        }
    )

    passed_count = sum(1 for s in scenarios if s["passed"])
    return {
        "total_scenarios": len(scenarios),
        "passed_scenarios": passed_count,
        "pass_rate": round(passed_count / len(scenarios), 4),
        "scenarios": scenarios,
    }


if __name__ == "__main__":
    report = run_adaptation_benchmark()
    print(
        f"Phase 7 Adaptation Benchmark: {report['passed_scenarios']}/{report['total_scenarios']} "
        f"scenarios passed ({report['pass_rate'] * 100:.1f}%)"
    )
    for item in report["scenarios"]:
        status_str = "PASS" if item["passed"] else "FAIL"
        print(
            f"  [{status_str}] {item['scenario_id']}: "
            f"expected={item['expected_activity']} actual={item['actual_activity']}"
        )
