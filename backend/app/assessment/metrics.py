"""Evaluation metrics for measuring Assessment Agent agreement with human-reviewed labels."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.schemas.assessment import AssessmentSchema, normalize_verdict

CANONICAL_VERDICTS = (
    "CORRECT",
    "PARTIALLY_CORRECT",
    "INCORRECT",
    "OFF_TOPIC",
    "INSUFFICIENT_EVIDENCE",
)


@dataclass
class BenchmarkCaseEvaluation:
    """Comparison between a single human-labeled benchmark case and the Assessment Agent's output."""

    case_id: str
    answer_category: str
    concept_title: str
    human_verdict: str
    predicted_verdict: str
    verdict_match: bool
    human_score: float
    predicted_score: float
    score_abs_error: float
    human_has_misconception: bool
    predicted_has_misconception: bool
    predicted_misconception: str | None
    misconception_match: bool
    human_error_classification: str
    predicted_error_classification: str
    error_classification_match: bool
    predicted_confidence: float
    uncertain_evaluation: bool
    evidence_count: int


@dataclass
class AssessmentBenchmarkMetrics:
    """Aggregate agreement and calibration metrics against human-reviewed labels."""

    total_cases: int
    verdict_exact_matches: int
    verdict_accuracy: float
    cohens_kappa: float
    score_mae: float
    misconception_precision: float
    misconception_recall: float
    false_positive_misconceptions: int
    error_classification_accuracy: float
    uncertainty_calibration_rate: float
    per_category_accuracy: dict[str, float] = field(default_factory=dict)
    case_results: list[BenchmarkCaseEvaluation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_multiclass_cohens_kappa(
    human_labels: list[str],
    predicted_labels: list[str],
    categories: tuple[str, ...] = CANONICAL_VERDICTS,
) -> float:
    """Compute multi-class unweighted Cohen's Kappa measuring inter-rater agreement."""
    n = len(human_labels)
    if n == 0 or len(predicted_labels) != n:
        return 0.0

    observed_matches = sum(1 for h, p in zip(human_labels, predicted_labels) if h == p)
    p_o = observed_matches / n

    p_e = 0.0
    for cat in categories:
        h_count = sum(1 for h in human_labels if h == cat)
        p_count = sum(1 for p in predicted_labels if p == cat)
        p_e += (h_count / n) * (p_count / n)

    if abs(1.0 - p_e) < 1e-9:
        return 1.0 if p_o >= 1.0 - 1e-9 else 0.0

    kappa = (p_o - p_e) / (1.0 - p_e)
    return round(kappa, 4)


def compute_assessment_benchmark_metrics(
    benchmark_cases: list[dict[str, Any]],
    predictions: list[AssessmentSchema],
) -> AssessmentBenchmarkMetrics:
    """Evaluate Assessment Agent outputs against human-reviewed ground-truth labels."""
    if len(benchmark_cases) != len(predictions):
        raise ValueError("benchmark_cases and predictions must have the same length.")

    total = len(benchmark_cases)
    if total == 0:
        return AssessmentBenchmarkMetrics(
            total_cases=0,
            verdict_exact_matches=0,
            verdict_accuracy=0.0,
            cohens_kappa=0.0,
            score_mae=0.0,
            misconception_precision=1.0,
            misconception_recall=1.0,
            false_positive_misconceptions=0,
            error_classification_accuracy=0.0,
            uncertainty_calibration_rate=0.0,
        )

    human_verdicts: list[str] = []
    pred_verdicts: list[str] = []
    case_results: list[BenchmarkCaseEvaluation] = []

    category_totals: dict[str, int] = {}
    category_hits: dict[str, int] = {}

    tp_misc = 0
    fp_misc = 0
    fn_misc = 0

    err_matches = 0
    uncertain_targets = 0
    uncertain_calibrated = 0
    total_abs_score_err = 0.0

    for case, pred in zip(benchmark_cases, predictions):
        case_id = str(case["case_id"])
        cat = str(case["answer_category"]).lower()
        h_verdict = normalize_verdict(str(case["human_verdict"]))
        p_verdict = pred.verdict

        human_verdicts.append(h_verdict)
        pred_verdicts.append(p_verdict)

        v_match = h_verdict == p_verdict
        category_totals[cat] = category_totals.get(cat, 0) + 1
        if v_match:
            category_hits[cat] = category_hits.get(cat, 0) + 1

        h_score = float(case.get("human_rubric_score", 0.0))
        abs_err = round(abs(pred.rubric_score - h_score), 2)
        total_abs_score_err += abs_err

        h_has_misc = bool(case.get("human_misconception"))
        p_has_misc = pred.misconception is not None
        if h_has_misc and p_has_misc:
            tp_misc += 1
        elif not h_has_misc and p_has_misc:
            fp_misc += 1
        elif h_has_misc and not p_has_misc:
            fn_misc += 1

        h_err_cls = str(case.get("human_error_classification") or "NONE").upper()
        p_err_cls = pred.error_classification
        e_match = h_err_cls == p_err_cls
        if e_match:
            err_matches += 1

        if cat in {"vague", "ambiguous"} or h_verdict == "INSUFFICIENT_EVIDENCE":
            uncertain_targets += 1
            if pred.uncertain_evaluation and pred.confidence <= 0.65:
                uncertain_calibrated += 1

        case_results.append(
            BenchmarkCaseEvaluation(
                case_id=case_id,
                answer_category=cat,
                concept_title=str(case.get("concept_title", "")),
                human_verdict=h_verdict,
                predicted_verdict=p_verdict,
                verdict_match=v_match,
                human_score=h_score,
                predicted_score=pred.rubric_score,
                score_abs_error=abs_err,
                human_has_misconception=h_has_misc,
                predicted_has_misconception=p_has_misc,
                predicted_misconception=pred.misconception,
                misconception_match=(h_has_misc == p_has_misc),
                human_error_classification=h_err_cls,
                predicted_error_classification=p_err_cls,
                error_classification_match=e_match,
                predicted_confidence=pred.confidence,
                uncertain_evaluation=pred.uncertain_evaluation,
                evidence_count=len(pred.evidence),
            )
        )

    exact_matches = sum(1 for r in case_results if r.verdict_match)
    verdict_acc = round(exact_matches / total, 4)
    kappa = compute_multiclass_cohens_kappa(human_verdicts, pred_verdicts)
    score_mae = round(total_abs_score_err / total, 2)

    misc_precision = (
        round(tp_misc / (tp_misc + fp_misc), 4)
        if (tp_misc + fp_misc) > 0
        else 1.0
    )
    misc_recall = (
        round(tp_misc / (tp_misc + fn_misc), 4)
        if (tp_misc + fn_misc) > 0
        else 1.0
    )
    err_acc = round(err_matches / total, 4)
    uncert_rate = (
        round(uncertain_calibrated / uncertain_targets, 4)
        if uncertain_targets > 0
        else 1.0
    )

    per_cat_acc = {
        cat: round(category_hits.get(cat, 0) / count, 4)
        for cat, count in category_totals.items()
    }

    return AssessmentBenchmarkMetrics(
        total_cases=total,
        verdict_exact_matches=exact_matches,
        verdict_accuracy=verdict_acc,
        cohens_kappa=kappa,
        score_mae=score_mae,
        misconception_precision=misc_precision,
        misconception_recall=misc_recall,
        false_positive_misconceptions=fp_misc,
        error_classification_accuracy=err_acc,
        uncertainty_calibration_rate=uncert_rate,
        per_category_accuracy=per_cat_acc,
        case_results=case_results,
    )
