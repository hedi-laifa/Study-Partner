"""Executable benchmark runner for Phase 6 Assessment Agent evaluation against human labels."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import uuid

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.assessment.metrics import (  # noqa: E402
    AssessmentBenchmarkMetrics,
    compute_assessment_benchmark_metrics,
)
from app.assessment.service import AssessmentAgentService  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.schemas.assessment import AssessmentSchema  # noqa: E402


def run_assessment_benchmark(
    benchmark_path: Path | None = None,
    output_report_path: Path | None = None,
) -> tuple[AssessmentBenchmarkMetrics, list[AssessmentSchema]]:
    """Run the human-reviewed assessment benchmark and compute agreement metrics."""
    eval_dir = Path(__file__).resolve().parent
    bm_file = benchmark_path or (eval_dir / "human_reviewed_benchmark.json")
    report_file = output_report_path or (eval_dir / "latest_benchmark_report.json")

    payload = json.loads(bm_file.read_text(encoding="utf-8"))
    cases: list[dict] = payload["cases"]

    # Ensure deterministic evaluation speed during benchmark runs if local Ollama is offline
    original_fallback = settings.TUTOR_OFFLINE_FALLBACK
    original_timeout = settings.OLLAMA_TIMEOUT_SECONDS
    settings.TUTOR_OFFLINE_FALLBACK = True
    settings.OLLAMA_TIMEOUT_SECONDS = 0.15

    try:
        agent = AssessmentAgentService()
        predictions: list[AssessmentSchema] = []
        for case in cases:
            result = agent.evaluate_answer(
                concept_id=uuid.UUID(str(case["concept_id"])),
                concept_title=str(case["concept_title"]),
                question_text=str(case["question_text"]),
                rubric_json=case["rubric"],
                ideal_answer_summary=str(case["ideal_answer_summary"]),
                student_answer=str(case["student_answer"]),
                relevant_pages=[1, 2],
            )
            predictions.append(result)
    finally:
        settings.TUTOR_OFFLINE_FALLBACK = original_fallback
        settings.OLLAMA_TIMEOUT_SECONDS = original_timeout

    metrics = compute_assessment_benchmark_metrics(cases, predictions)
    report_file.write_text(
        json.dumps(metrics.to_dict(), indent=2),
        encoding="utf-8",
    )
    return metrics, predictions


def main() -> None:
    metrics, _ = run_assessment_benchmark()
    print("=" * 78)
    print("STUDY PARTNER AI — PHASE 6 ASSESSMENT AGENT BENCHMARK REPORT")
    print("=" * 78)
    print(f"Total Human-Reviewed Cases       : {metrics.total_cases}")
    print(
        f"Verdict Exact Match Accuracy     : {metrics.verdict_accuracy * 100:.1f}% "
        f"({metrics.verdict_exact_matches}/{metrics.total_cases})"
    )
    print(f"Multi-Class Cohen's Kappa (κ)    : {metrics.cohens_kappa:.4f}")
    print(f"Rubric Score MAE                 : {metrics.score_mae:.2f} pts")
    print(f"Misconception Precision          : {metrics.misconception_precision * 100:.1f}%")
    print(f"Misconception Recall             : {metrics.misconception_recall * 100:.1f}%")
    print(f"False-Positive Misconceptions    : {metrics.false_positive_misconceptions}")
    print(
        f"Error Classification Accuracy    : {metrics.error_classification_accuracy * 100:.1f}%"
    )
    print(
        f"Uncertainty Calibration Rate     : {metrics.uncertainty_calibration_rate * 100:.1f}%"
    )
    print("-" * 78)
    print("Per-Category Verdict Accuracy:")
    for cat, acc in metrics.per_category_accuracy.items():
        print(f"  - {cat:<12}: {acc * 100:.1f}%")
    print("=" * 78)


if __name__ == "__main__":
    main()
