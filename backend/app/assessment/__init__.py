"""Assessment agent, explicit rubric models, versioned prompts, and agreement metrics."""

from app.assessment.metrics import (
    AssessmentBenchmarkMetrics,
    BenchmarkCaseEvaluation,
    compute_assessment_benchmark_metrics,
    compute_multiclass_cohens_kappa,
)
from app.assessment.prompts import (
    ASSESSMENT_PROMPT_VERSION,
    PROMPT_REGISTRY,
    build_assessment_prompts,
    get_assessment_prompt,
)
from app.assessment.rubric import (
    build_explicit_rubric,
    parse_activity_rubric,
    serialize_rubric_for_storage,
    verify_numerical_calculation,
)
from app.assessment.service import AssessmentAgentService, generate_assessment_feedback
from app.schemas.assessment import (
    ActivityRubric,
    AssessmentSchema,
    AssessmentVerdict,
    ErrorClassification,
    MisconceptionPattern,
    NumericalCheckSpec,
    NumericVerificationResult,
    RubricCriterionModel,
)

__all__ = [
    "ASSESSMENT_PROMPT_VERSION",
    "PROMPT_REGISTRY",
    "ActivityRubric",
    "AssessmentAgentService",
    "AssessmentBenchmarkMetrics",
    "AssessmentSchema",
    "AssessmentVerdict",
    "BenchmarkCaseEvaluation",
    "ErrorClassification",
    "MisconceptionPattern",
    "NumericVerificationResult",
    "NumericalCheckSpec",
    "RubricCriterionModel",
    "build_assessment_prompts",
    "build_explicit_rubric",
    "compute_assessment_benchmark_metrics",
    "compute_multiclass_cohens_kappa",
    "generate_assessment_feedback",
    "get_assessment_prompt",
    "parse_activity_rubric",
    "serialize_rubric_for_storage",
    "verify_numerical_calculation",
]
