"""Deterministic Adaptive Routing Policy for Phase 7 Learning Coach."""

from __future__ import annotations

import uuid

from app.schemas.learning import (
    AlternativeActivityOption,
    CoachActivityType,
    CoachRecommendation,
    EvidenceStatus,
)

ALL_ACTIVITY_OPTIONS: tuple[tuple[CoachActivityType, str, str], ...] = (
    (
        "DIAGNOSTIC_QUESTION",
        "Diagnostic Question",
        "Assess baseline understanding of the concept.",
    ),
    (
        "EXPLANATION",
        "Concept Explanation",
        "Review a concise, source-grounded explanation of the core mechanism.",
    ),
    (
        "EASIER_PRACTICE",
        "Easier Practice",
        "Build foundational understanding with a stepped-down BASIC question.",
    ),
    (
        "HINT_AND_RETRY",
        "Hint & Retry",
        "Use a targeted hint to address missing ideas and retry.",
    ),
    (
        "TARGETED_PRACTICE",
        "Targeted Practice",
        "Practice the specific concept independently to verify unassisted understanding.",
    ),
    (
        "HARDER_PRACTICE",
        "Harder Practice",
        "Challenge your reasoning with an ADVANCED difficulty question.",
    ),
    (
        "TRANSFER_QUESTION",
        "Transfer Question",
        "Apply this concept to a novel scenario or boundary condition.",
    ),
    (
        "REVIEW",
        "Spaced Review",
        "Reinforce long-term retention with a structured review check.",
    ),
)


def _step_down_difficulty(difficulty: str) -> str:
    norm = (difficulty or "INTERMEDIATE").upper()
    if norm == "ADVANCED":
        return "INTERMEDIATE"
    return "BASIC"


def _step_up_difficulty(difficulty: str) -> str:
    norm = (difficulty or "INTERMEDIATE").upper()
    if norm == "BASIC":
        return "INTERMEDIATE"
    return "ADVANCED"


def _build_alternative_options(
    primary: CoachActivityType,
    current_difficulty: str,
) -> list[AlternativeActivityOption]:
    """Return selectable alternative activities so the student can always choose another activity."""
    options: list[AlternativeActivityOption] = []
    for act_type, label, desc in ALL_ACTIVITY_OPTIONS:
        if act_type == primary:
            continue
        if act_type in {"EASIER_PRACTICE", "EXPLANATION"}:
            diff = _step_down_difficulty(current_difficulty)
        elif act_type in {"HARDER_PRACTICE", "TRANSFER_QUESTION"}:
            diff = _step_up_difficulty(current_difficulty)
        else:
            diff = current_difficulty
        options.append(
            AlternativeActivityOption(
                activity_type=act_type,
                label=label,
                difficulty=diff,
                description=desc,
            )
        )
    return options


def select_next_adaptive_activity(
    *,
    concept_id: uuid.UUID,
    concept_title: str,
    session_goal: str,
    attempts_count: int,
    latest_verdict: str | None,
    latest_score: float | None,
    hints_used_on_latest: int,
    current_difficulty: str,
    independent_success_count: int,
    assisted_success_count: int,
    consecutive_independent_successes: int,
    evidence_status: EvidenceStatus,
    uncertainty_score: float,
    evidence_recency_hours: float | None = None,
    is_due_for_review: bool = False,
    previous_activity_types: list[str] | None = None,
    latest_gaps: list[str] | None = None,
    latest_misconception: str | None = None,
) -> CoachRecommendation:
    """Select the optimal next learning activity using transparent, deterministic mastery policy rules."""
    prior_types = [t.upper() for t in (previous_activity_types or [])]
    norm_diff = (current_difficulty or "INTERMEDIATE").upper()
    verdict = (latest_verdict or "").upper()

    # Policy Rule 1: No evidence -> Diagnostic Question
    if attempts_count == 0 or not verdict:
        rec_type: CoachActivityType = "DIAGNOSTIC_QUESTION"
        target_diff = "INTERMEDIATE"
        rule = "NO_EVIDENCE_DIAGNOSTIC"
        reason = (
            f"No learning evidence recorded yet for '{concept_title}'. "
            f"Starting with a Diagnostic Question to gauge your baseline understanding toward '{session_goal}'."
        )
        confirm = False

    # Policy Rule 2: Stale evidence / Due for review -> Review
    elif is_due_for_review or (
        evidence_recency_hours is not None and evidence_recency_hours >= 72.0
    ):
        rec_type = "REVIEW"
        target_diff = "INTERMEDIATE"
        rule = "STALE_EVIDENCE_REVIEW"
        hours_str = (
            f"{int(evidence_recency_hours)} hours"
            if evidence_recency_hours is not None
            else "scheduled interval"
        )
        reason = (
            f"Evidence for '{concept_title}' is due for spaced review ({hours_str} since last practice). "
            f"Recommending a Review activity to verify retention."
        )
        confirm = True

    # Policy Rule 3: Incorrect or Off-Topic Answer -> Explanation + Easier Practice
    elif verdict in {"INCORRECT", "OFF_TOPIC"}:
        just_saw_explanation = bool(prior_types and prior_types[-1] == "EXPLANATION")
        target_diff = _step_down_difficulty(norm_diff)
        rule = "INCORRECT_EXPLANATION_AND_EASIER_PRACTICE"
        misc_note = (
            f" and address the misconception ('{latest_misconception}')"
            if latest_misconception
            else ""
        )
        if just_saw_explanation:
            rec_type = "EASIER_PRACTICE"
            reason = (
                f"After reviewing the concept explanation, step down to Easier Practice ({target_diff}) "
                f"to rebuild foundational confidence on '{concept_title}'{misc_note}."
            )
        else:
            rec_type = "EXPLANATION"
            reason = (
                f"Your last attempt on '{concept_title}' was {verdict.lower().replace('_', ' ')} "
                f"({latest_score or 0.0:.0f}/100). Policy recommends a grounded Explanation followed by "
                f"Easier Practice ({target_diff}) to clarify the core mechanism{misc_note}."
            )
        confirm = True

    # Policy Rule 4: Partial or Uncertain/Ambiguous Answer -> Targeted Hint + Retry
    elif verdict in {"PARTIALLY_CORRECT", "INSUFFICIENT_EVIDENCE"}:
        rec_type = "HINT_AND_RETRY"
        target_diff = (
            _step_down_difficulty(norm_diff)
            if (latest_score is not None and latest_score < 45.0)
            else norm_diff
        )
        rule = "PARTIAL_HINT_AND_RETRY"
        gap_focus = (
            f" focusing on: {latest_gaps[0]}"
            if latest_gaps
            else " focusing on the missing causal steps"
        )
        reason = (
            f"Your answer showed partial or incomplete evidence ({latest_score or 0.0:.0f}/100){gap_focus}. "
            f"Policy recommends a Targeted Hint and Retry at {target_diff} difficulty."
        )
        confirm = True

    # Policy Rule 5: Success After Hints -> Record Evidence, Test Again Independently
    elif verdict == "CORRECT" and hints_used_on_latest > 0:
        rec_type = "TARGETED_PRACTICE"
        target_diff = "INTERMEDIATE" if norm_diff == "BASIC" else norm_diff
        rule = "SUCCESS_AFTER_HINTS_TEST_AGAIN"
        reason = (
            f"You answered correctly after using {hints_used_on_latest} hint(s). "
            f"Assisted proficiency evidence has been recorded, but mastery requires unassisted reasoning—"
            f"recommending Targeted Practice at {target_diff} difficulty without hints."
        )
        confirm = False

    # Policy Rule 6: Repeated Independent Success -> Strong Evidence, Transfer Question & Future Review
    elif verdict == "CORRECT" and hints_used_on_latest == 0 and (
        consecutive_independent_successes >= 2 or independent_success_count >= 2
    ):
        if prior_types and prior_types[-1] == "TRANSFER_QUESTION":
            rec_type = "REVIEW"
        else:
            rec_type = "TRANSFER_QUESTION"
        target_diff = "ADVANCED"
        rule = "REPEATED_INDEPENDENT_SUCCESS_STRONG_EVIDENCE"
        reason = (
            f"Repeated independent success ({independent_success_count} unassisted correct answers)! "
            f"Strong mastery evidence recorded and future spaced review scheduled. "
            f"Recommending an ADVANCED Transfer Question to test novel scenario synthesis."
        )
        confirm = True

    # Policy Rule 7: First Independent Success -> Harder Question
    else:
        rec_type = "HARDER_PRACTICE"
        target_diff = _step_up_difficulty(norm_diff)
        rule = "INDEPENDENT_SUCCESS_HARDER_PRACTICE"
        reason = (
            f"Strong independent success without hints ({latest_score or 100.0:.0f}/100)! "
            f"Because mastery is never claimed from a single answer, policy recommends a Harder Practice "
            f"question ({target_diff}) to confirm durable understanding."
        )
        confirm = False

    alternatives = _build_alternative_options(rec_type, target_diff)
    return CoachRecommendation(
        recommended_activity=rec_type,
        target_concept_id=concept_id,
        target_concept_title=concept_title,
        difficulty=target_diff,
        reason=reason,
        policy_rule_applied=rule,
        requires_student_confirmation=confirm,
        evidence_status=evidence_status,
        uncertainty_score=uncertainty_score,
        independent_success_count=independent_success_count,
        assisted_success_count=assisted_success_count,
        alternative_activities=alternatives,
    )
