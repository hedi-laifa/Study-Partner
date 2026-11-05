"""Transparent, deterministic Python mastery heuristic for Phase 7 Adaptive Learning.

Enforces:
- 100% deterministic Python rules (LLMs never directly modify concept mastery)
- Do not claim mastery from a single answer (requires >= 2 independent successes)
- Discounted weight for hint-assisted successes (cannot reach MASTERED via hints alone)
- Uncertainty preservation based on evaluation confidence and evidence count
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.schemas.learning import EvidenceStatus, MasteryStatus


@dataclass(frozen=True)
class MasteryUpdateOutcome:
    """Deterministic result of updating a concept's mastery and evidence status."""

    previous_mastery_score: float
    new_mastery_score: float
    score_delta: float
    mastery_status: MasteryStatus
    evidence_status: EvidenceStatus
    evidence_type: str
    uncertainty_score: float
    attempts_count: int
    correct_attempts_count: int
    independent_success_count: int
    assisted_success_count: int
    consecutive_independent_successes: int
    next_review_at: datetime | None
    explanation: str


def compute_evidence_uncertainty(
    *,
    attempts_count: int,
    independent_success_count: int,
    latest_confidence: float,
    uncertain_evaluation: bool,
) -> float:
    """Compute concept-level uncertainty in [0.05, 1.0].

    High uncertainty (1.0) when no evidence exists or when answers are ambiguous;
    decreases only as consistent, high-confidence independent evidence accumulates.
    """
    if attempts_count <= 0:
        return 1.0

    # Base uncertainty shrinks with more attempts
    sample_uncertainty = 1.0 / (1.0 + 0.55 * attempts_count + 0.35 * independent_success_count)
    eval_uncertainty = 1.0 - max(0.0, min(1.0, latest_confidence))

    blended = 0.55 * sample_uncertainty + 0.45 * eval_uncertainty
    if uncertain_evaluation:
        blended = max(0.68, blended + 0.22)
    elif attempts_count == 1:
        # Single-answer evidence always retains meaningful uncertainty (>= 0.38)
        blended = max(0.38, blended)

    return round(min(1.0, max(0.05, blended)), 2)


def compute_transparent_mastery_update(
    *,
    previous_mastery_score: float,
    previous_attempts_count: int,
    previous_correct_count: int,
    previous_independent_success_count: int,
    previous_assisted_success_count: int,
    previous_consecutive_independent: int,
    verdict: str,
    rubric_score: float,
    hints_used: int,
    difficulty: str,
    confidence: float,
    uncertain_evaluation: bool,
    has_misconception: bool,
    now: datetime | None = None,
) -> MasteryUpdateOutcome:
    """Deterministically compute updated mastery score, status, evidence type, and review schedule."""
    timestamp = now or datetime.now(timezone.utc)
    attempts_count = previous_attempts_count + 1
    norm_verdict = (verdict or "INCORRECT").upper()
    norm_diff = (difficulty or "INTERMEDIATE").upper()

    diff_multiplier = {
        "BASIC": 0.92,
        "INTERMEDIATE": 1.00,
        "ADVANCED": 1.08,
    }.get(norm_diff, 1.00)

    hint_discount = 1.0
    if hints_used == 1:
        hint_discount = 0.80
    elif hints_used == 2:
        hint_discount = 0.70
    elif hints_used >= 3:
        hint_discount = 0.60

    effective_score = min(100.0, max(0.0, rubric_score * diff_multiplier * hint_discount))

    correct_count = previous_correct_count
    ind_success = previous_independent_success_count
    ass_success = previous_assisted_success_count
    consec_ind = previous_consecutive_independent

    if norm_verdict == "CORRECT":
        correct_count += 1
        if hints_used == 0 and not uncertain_evaluation:
            ind_success += 1
            consec_ind += 1
            evidence_type = (
                "REPEATED_INDEPENDENT_SUCCESS"
                if consec_ind >= 2
                else "INDEPENDENT_SUCCESS"
            )
        else:
            ass_success += 1
            consec_ind = 0
            evidence_type = "ASSISTED_SUCCESS_AFTER_HINTS"
    elif norm_verdict == "PARTIALLY_CORRECT":
        consec_ind = 0
        evidence_type = "PARTIAL_UNDERSTANDING"
    elif norm_verdict == "INSUFFICIENT_EVIDENCE" or uncertain_evaluation:
        consec_ind = 0
        evidence_type = "UNCERTAIN_AMBIGUOUS_EVIDENCE"
    elif has_misconception:
        consec_ind = 0
        evidence_type = "MISCONCEPTION_EVIDENCE"
    else:
        consec_ind = 0
        evidence_type = "INCORRECT_ATTEMPT_EVIDENCE"

    # Weighted moving update (damped when evaluation is uncertain)
    if previous_attempts_count == 0:
        raw_new = effective_score * 0.72
    elif uncertain_evaluation or norm_verdict == "INSUFFICIENT_EVIDENCE":
        raw_new = 0.80 * previous_mastery_score + 0.20 * effective_score
    else:
        raw_new = 0.40 * previous_mastery_score + 0.60 * effective_score

    # Enforce strict mastery guardrails:
    # 1. Never claim mastery (>= 80) from a single answer (attempts_count == 1)
    # 2. Never claim mastery without at least 2 independent successes
    if ind_success == 0:
        # Only assisted or partial/incorrect attempts so far
        capped_score = min(raw_new, 74.0 if ass_success > 0 else 65.0)
    elif ind_success == 1:
        # Exactly one independent success -> cap at 76.0 (LEARNING, not MASTERED)
        capped_score = min(raw_new, 76.0)
    else:
        # 2+ independent successes: if consecutive independent >= 2 and current is CORRECT without hints,
        # ensure score reflects strong mastery (>= 84.0)
        if consec_ind >= 2 and norm_verdict == "CORRECT" and hints_used == 0:
            capped_score = max(84.0, min(100.0, raw_new + 12.0))
        else:
            capped_score = min(100.0, raw_new)

    new_score = round(max(0.0, capped_score), 1)
    score_delta = round(new_score - previous_mastery_score, 1)

    uncertainty = compute_evidence_uncertainty(
        attempts_count=attempts_count,
        independent_success_count=ind_success,
        latest_confidence=confidence,
        uncertain_evaluation=(uncertain_evaluation or norm_verdict == "INSUFFICIENT_EVIDENCE"),
    )

    next_review_at: datetime | None = None
    if new_score >= 80.0 and ind_success >= 2:
        mastery_status: MasteryStatus = "MASTERED"
        evidence_status: EvidenceStatus = "STRONG_INDEPENDENT_EVIDENCE"
        next_review_at = timestamp + timedelta(days=3)
        explanation = (
            f"Repeated independent success ({ind_success} unassisted correct answers) "
            f"established strong mastery evidence ({new_score}/100). Scheduled future review in 3 days."
        )
    elif norm_verdict == "INSUFFICIENT_EVIDENCE" or uncertain_evaluation:
        mastery_status = "NEEDS_REVIEW" if new_score < 50.0 else "LEARNING"
        evidence_status = "UNCERTAIN_EVIDENCE"
        explanation = (
            f"Answer was ambiguous or lacked verifiable detail (uncertainty={uncertainty}). "
            f"Mastery held conservatively at {new_score}/100 pending clearer evidence."
        )
    elif norm_verdict in {"INCORRECT", "OFF_TOPIC"}:
        mastery_status = "NEEDS_REVIEW"
        evidence_status = "NEEDS_REMEDIATION"
        next_review_at = timestamp + timedelta(hours=4)
        explanation = (
            f"Incorrect response recorded ({new_score}/100). Concept flagged for explanation "
            f"and easier foundational practice."
        )
    elif norm_verdict == "CORRECT" and hints_used > 0:
        mastery_status = "LEARNING"
        evidence_status = "ASSISTED_PROFICIENCY"
        next_review_at = timestamp + timedelta(hours=12)
        explanation = (
            f"Correct answer achieved after {hints_used} hint(s) ({new_score}/100). "
            f"Assisted evidence recorded; an unassisted verification attempt is required before mastery."
        )
    elif norm_verdict == "CORRECT" and ind_success == 1:
        mastery_status = "LEARNING"
        evidence_status = "EMERGING_EVIDENCE"
        next_review_at = timestamp + timedelta(days=1)
        explanation = (
            f"First independent success recorded ({new_score}/100). Mastery is never claimed from a "
            f"single answer; one more independent success at higher difficulty will confirm mastery."
        )
    else:
        mastery_status = "LEARNING" if new_score >= 45.0 else "NEEDS_REVIEW"
        evidence_status = "DEVELOPING_EVIDENCE"
        next_review_at = timestamp + timedelta(hours=12)
        explanation = (
            f"Partial understanding demonstrated ({new_score}/100). Targeted hint and retry "
            f"recommended to close remaining conceptual gaps."
        )

    return MasteryUpdateOutcome(
        previous_mastery_score=previous_mastery_score,
        new_mastery_score=new_score,
        score_delta=score_delta,
        mastery_status=mastery_status,
        evidence_status=evidence_status,
        evidence_type=evidence_type,
        uncertainty_score=uncertainty,
        attempts_count=attempts_count,
        correct_attempts_count=correct_count,
        independent_success_count=ind_success,
        assisted_success_count=ass_success,
        consecutive_independent_successes=consec_ind,
        next_review_at=next_review_at,
        explanation=explanation,
    )
