"""Assessment Agent Service for rubric-based student answer evaluation and feedback generation."""

from __future__ import annotations

import re
from typing import Any
import uuid

from app.assessment.prompts import (
    ASSESSMENT_PROMPT_VERSION,
    build_assessment_prompts,
)
from app.assessment.rubric import (
    parse_activity_rubric,
    verify_numerical_calculation,
)
from app.core.config import settings
from app.core.logging import logger
from app.retrieval.embeddings import STOPWORDS, _stem_token
from app.schemas.assessment import (
    ActivityRubric,
    AssessmentLLMOutput,
    AssessmentSchema,
    AssessmentVerdict,
    ErrorClassification,
    MisconceptionPattern,
    NumericVerificationResult,
)
from app.tutor.llm_client import (
    LLMOutputValidationError,
    LLMServiceUnavailableError,
    OllamaLLMClient,
)

# Phrases indicating an explicit non-answer or high uncertainty/vagueness
_NON_ANSWER_PATTERNS = (
    "i don't know",
    "i dont know",
    "not sure",
    "no idea",
    "skip",
    "pass",
    "idk",
    "cannot remember",
    "can't remember",
)

# Hedging/both-ways patterns indicating an ambiguous, self-contradictory student answer
_AMBIGUITY_PATTERNS = (
    r"\beither\b.+\bor\b.+\bcould be both\b",
    r"\beither\b.+\bor\b.+\bdepending on\b",
    r"\bmight\b.+\bor maybe\b",
    r"\bmaybe it increases\b.+\bor maybe it decreases\b",
    r"\bvirtual to physical or physical to virtual\b",
    r"\bphysical to virtual or virtual to physical\b",
    r"\bcould be true or false\b",
    r"\bi think both opposite\b",
    r"\bnot sure which direction\b",
    r"\beither increases or decreases\b",
    r"\beither needs a majority or does not\b",
)

# Generic filler or function words that carry no domain-specific conceptual evidence
_GENERIC_VAGUE_WORDS = {
    "system",
    "computer",
    "better",
    "faster",
    "slower",
    "good",
    "bad",
    "helps",
    "works",
    "things",
    "stuff",
    "process",
    "data",
    "information",
    "optimize",
    "optimizes",
    "performance",
    "efficient",
    "efficiency",
    "somehow",
    "basically",
    "something",
    "related",
    "important",
    "handles",
    "manages",
    "where",
    "when",
    "what",
    "which",
    "while",
    "whereas",
    "into",
    "from",
    "with",
    "without",
    "using",
    "used",
    "uses",
    "convert",
    "converts",
    "occurs",
    "occur",
    "inside",
    "across",
    "between",
    "through",
    "under",
    "over",
    "after",
    "before",
    "during",
    "because",
    "therefore",
    "explain",
    "explains",
    "how",
    "does",
    "role",
    "play",
    "happens",
    "happen",
    "causes",
    "cause",
    "resolve",
    "resolves",
    "affect",
    "affects",
}


def _tokenize_stems(text: str) -> list[str]:
    return [
        _stem_token(w)
        for w in re.findall(r"[a-z0-9]+", text.lower())
        if len(w) > 2 and w not in STOPWORDS
    ]


def _extract_matching_quote(student_answer: str, phrase: str) -> str:
    """Extract the sentence or clause from student_answer containing the matched phrase."""
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+|\n+", student_answer.strip())
        if s.strip()
    ]
    low_phrase = phrase.lower()
    for sentence in sentences:
        if low_phrase in sentence.lower():
            return sentence
    return student_answer.strip()[:180]


def _detect_supported_misconception(
    student_answer: str,
    rubric: ActivityRubric,
) -> tuple[str | None, str | None, str | None]:
    """Check if the student's answer contains explicit textual evidence of a misconception.

    Returns `(misconception_label, quote_evidence, correction_explanation)` or `(None, None, None)`.
    Never infers a misconception from an omission or from an ambiguous both-ways guess.
    """
    low_answer = re.sub(r"\s+", " ", student_answer.lower()).strip()

    # Do not infer a definite misconception if the student is explicitly hedging both directions ("either X or Y")
    for amb_pat in _AMBIGUITY_PATTERNS:
        if re.search(amb_pat, low_answer):
            return None, None, None

    all_patterns: list[MisconceptionPattern] = list(rubric.misconception_patterns)
    for crit in rubric.criteria:
        for pat in crit.misconception_patterns:
            if pat.pattern_id not in {p.pattern_id for p in all_patterns}:
                all_patterns.append(pat)

    for pattern in all_patterns:
        for trigger in pattern.trigger_phrases:
            trig_clean = trigger.strip().lower()
            if trig_clean and trig_clean in low_answer:
                quote = _extract_matching_quote(student_answer, trig_clean)
                evidence_str = (
                    f'Student stated: "{quote}" (matches misconception trigger "{trigger}").'
                )
                return (
                    pattern.misconception_label,
                    evidence_str,
                    pattern.correction_explanation,
                )

    return None, None, None


def _is_ambiguous_answer(student_answer: str) -> tuple[bool, str | None]:
    """Detect whether the student answer is explicitly ambiguous or self-contradictory."""
    low = re.sub(r"\s+", " ", student_answer.lower()).strip()
    for pat in _AMBIGUITY_PATTERNS:
        match = re.search(pat, low)
        if match:
            quote = _extract_matching_quote(student_answer, match.group(0))
            return (
                True,
                f'Student answer is ambiguous/self-contradictory: "{quote}".',
            )
    return False, None


def _is_vague_or_non_answer(
    student_answer: str,
    matched_domain_stems: set[str],
    numeric_verification: NumericVerificationResult,
) -> tuple[bool, str | None]:
    """Detect whether an answer is a non-answer or too vague to evaluate with certainty."""
    clean = student_answer.strip()
    low = re.sub(r"\s+", " ", clean.lower())
    words = re.findall(r"[a-z0-9]+", low)

    for pat in _NON_ANSWER_PATTERNS:
        if low == pat or low.startswith(pat + ".") or low.startswith(pat + ","):
            return (
                True,
                f'Student submitted a non-answer or uncertainty statement: "{clean}".',
            )
        if pat in low and len(words) <= 10:
            return (
                True,
                f'Student expressed uncertainty without substantive reasoning: "{clean}".',
            )

    if len(words) < 4 and not (
        numeric_verification.applied and numeric_verification.extracted_student_values
    ):
        return (
            True,
            f'Student response is too brief ({len(words)} words) to provide verifiable evidence: "{clean}".',
        )

    # Check if the answer consists almost entirely of generic filler words with <= 1 domain stem
    meaningful_words = [w for w in words if w not in STOPWORDS and len(w) > 2]
    non_generic = [w for w in meaningful_words if w not in _GENERIC_VAGUE_WORDS]
    if len( matched_domain_stems ) == 0 and len(non_generic) <= 2 and len(words) <= 18:
        return (
            True,
            f'Student answer uses only generic phrasing without specific technical concepts: "{clean}".',
        )
    if len(matched_domain_stems) <= 1 and len(non_generic) <= 1 and len(words) <= 14:
        return (
            True,
            f'Student answer is too vague to confirm conceptual understanding: "{clean}".',
        )

    return False, None


def generate_assessment_feedback(
    *,
    concept_title: str,
    verdict: AssessmentVerdict,
    rubric_score: float,
    strengths: list[str],
    gaps: list[str],
    misconception: str | None,
    misconception_correction: str | None,
    error_classification: ErrorClassification,
    numeric_verification: NumericVerificationResult | None,
    next_activity: str,
    relevant_pages: list[int] | None = None,
) -> str:
    """Generate clear, constructive feedback explanation tailored to the assessment diagnosis."""
    page_note = f" (see course PDF p. {relevant_pages[0]})" if relevant_pages else ""

    if verdict == "CORRECT":
        strength_summary = strengths[0] if strengths else f"Explained {concept_title} accurately."
        return (
            f"Correct ({rubric_score:.1f}/100)! {strength_summary} "
            f"Your reasoning covers the required concepts for {concept_title}{page_note}."
        )

    if verdict == "OFF_TOPIC":
        return (
            f"Off-Topic (0/100): Your response discusses concepts unrelated to {concept_title}{page_note}. "
            f"Review the question prompt and focus on: {gaps[0] if gaps else concept_title}."
        )

    if verdict == "INSUFFICIENT_EVIDENCE":
        return (
            f"Insufficient Evidence ({rubric_score:.1f}/100 — Uncertain Evaluation): "
            f"Your answer is too vague or ambiguous to verify your understanding of {concept_title}{page_note}. "
            f"Please clarify your reasoning specifically regarding: {gaps[0] if gaps else concept_title}."
        )

    if error_classification == "CALCULATION_ERROR" and numeric_verification and numeric_verification.detail:
        return (
            f"{verdict.replace('_', ' ').title()} ({rubric_score:.1f}/100 — Calculation Error): "
            f"{numeric_verification.detail} "
            f"Check your arithmetic and formula setup for {concept_title}{page_note}."
        )

    if error_classification == "FACTUAL_MISTAKE" and misconception:
        correction = f" {misconception_correction}" if misconception_correction else ""
        return (
            f"Incorrect ({rubric_score:.1f}/100 — Factual Mistake Detected): "
            f"Your answer contains a supported misconception: {misconception}{correction}{page_note}"
        )

    if verdict == "PARTIALLY_CORRECT":
        strength_part = strengths[0] if strengths else f"You identified core aspects of {concept_title}."
        gap_part = gaps[0] if gaps else "additional causal steps from the rubric"
        return (
            f"Partially Correct ({rubric_score:.1f}/100 — Incomplete Reasoning): "
            f"{strength_part} However, your explanation is incomplete: {gap_part}{page_note}."
        )

    gap_summary = gaps[0] if gaps else f"Missing core concepts of {concept_title}"
    return (
        f"Incorrect ({rubric_score:.1f}/100): {gap_summary}{page_note}. "
        f"Recommended next step: {next_activity.replace('_', ' ').lower()}."
    )


class AssessmentAgentService:
    """Phase 6 Assessment Agent evaluating student answers against explicit rubrics."""

    def __init__(self, llm_client: OllamaLLMClient | None = None) -> None:
        self.llm_client = llm_client or OllamaLLMClient()
        self.prompt_version = ASSESSMENT_PROMPT_VERSION

    def evaluate_answer(
        self,
        *,
        concept_id: uuid.UUID,
        concept_title: str,
        question_text: str,
        rubric_json: list[dict[str, Any]] | dict[str, Any] | ActivityRubric | None,
        ideal_answer_summary: str,
        student_answer: str,
        relevant_pages: list[int] | None = None,
    ) -> AssessmentSchema:
        """Evaluate a student's answer against an explicit rubric and return a validated AssessmentSchema."""
        if isinstance(rubric_json, ActivityRubric):
            rubric = rubric_json
        else:
            rubric = parse_activity_rubric(
                rubric_json=rubric_json,
                concept_id=concept_id,
                concept_title=concept_title,
                ideal_answer_summary=ideal_answer_summary,
                question_text=question_text,
            )

        # Always run deterministic numerical check first when applicable
        numeric_check_spec = rubric.numerical_check
        if numeric_check_spec is None:
            for crit in rubric.criteria:
                if crit.numerical_check is not None:
                    numeric_check_spec = crit.numerical_check
                    break
        numeric_verification = verify_numerical_calculation(
            student_answer=student_answer,
            spec=numeric_check_spec,
        )

        system_prompt, user_prompt = build_assessment_prompts(
            concept_id=str(concept_id),
            concept_title=concept_title,
            question_text=question_text,
            rubric=rubric,
            ideal_answer_summary=ideal_answer_summary,
            student_answer=student_answer,
            numeric_verification=numeric_verification,
            version=self.prompt_version,
        )

        try:
            llm_out = self.llm_client.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=AssessmentLLMOutput,
                temperature=0.1,
                max_retries=1,
            )
            return self._validate_and_finalize_llm_output(
                llm_out=llm_out,
                concept_id=concept_id,
                concept_title=concept_title,
                rubric=rubric,
                student_answer=student_answer,
                numeric_verification=numeric_verification,
                relevant_pages=relevant_pages,
            )
        except (LLMServiceUnavailableError, LLMOutputValidationError, ValueError) as exc:
            if not settings.TUTOR_OFFLINE_FALLBACK:
                raise exc
            logger.info(
                "Using deterministic explicit-rubric Assessment Agent engine (prompt_version=%s).",
                self.prompt_version,
            )
            return self.evaluate_deterministically(
                concept_id=concept_id,
                concept_title=concept_title,
                question_text=question_text,
                rubric=rubric,
                ideal_answer_summary=ideal_answer_summary,
                student_answer=student_answer,
                numeric_verification=numeric_verification,
                relevant_pages=relevant_pages,
            )

    def _validate_and_finalize_llm_output(
        self,
        *,
        llm_out: AssessmentLLMOutput,
        concept_id: uuid.UUID,
        concept_title: str,
        rubric: ActivityRubric,
        student_answer: str,
        numeric_verification: NumericVerificationResult,
        relevant_pages: list[int] | None,
    ) -> AssessmentSchema:
        """Apply strict evidence and numerical guards to raw LLM assessment output."""
        supported_misc, misc_evidence, _ = _detect_supported_misconception(
            student_answer, rubric
        )
        # Rule: Do not infer misconceptions without evidence in student's text
        final_misconception = llm_out.misconception
        evidence = list(llm_out.evidence or [])
        if final_misconception:
            has_student_quote = any(
                '"' in ev or "student" in ev.lower() for ev in evidence
            )
            if not has_student_quote:
                if supported_misc and misc_evidence:
                    final_misconception = supported_misc
                    evidence.append(misc_evidence)
                else:
                    final_misconception = None

        if numeric_verification.applied and numeric_verification.detail:
            evidence.append(numeric_verification.detail)

        if not evidence:
            evidence.append(
                f'Evaluated student response ("{student_answer.strip()[:120]}") against rubric for {concept_title}.'
            )

        error_cls: ErrorClassification = "NONE"
        raw_err = (llm_out.error_classification or "NONE").strip().upper()
        if raw_err in {
            "NONE",
            "INCOMPLETE_REASONING",
            "FACTUAL_MISTAKE",
            "CALCULATION_ERROR",
            "AMBIGUOUS_OR_VAGUE",
            "OFF_TOPIC",
        }:
            error_cls = raw_err  # type: ignore[assignment]

        if numeric_verification.applied and numeric_verification.is_correct is False:
            error_cls = "CALCULATION_ERROR"

        return AssessmentSchema(
            concept_id=concept_id,
            verdict=llm_out.verdict,  # type: ignore[arg-type]
            rubric_score=llm_out.rubric_score,
            strengths=llm_out.strengths,
            gaps=llm_out.gaps,
            misconception=final_misconception,
            evidence=evidence,
            confidence=llm_out.confidence,
            next_activity=llm_out.next_activity or "PRACTICE_SAME_CONCEPT",
            feedback_explanation=llm_out.feedback_explanation,
            error_classification=error_cls,
            criteria_scores=llm_out.criteria_scores,
            numeric_verification=numeric_verification if numeric_verification.applied else None,
            prompt_version=self.prompt_version,
        )

    def evaluate_deterministically(
        self,
        *,
        concept_id: uuid.UUID,
        concept_title: str,
        question_text: str,
        rubric: ActivityRubric,
        ideal_answer_summary: str,
        student_answer: str,
        numeric_verification: NumericVerificationResult | None = None,
        relevant_pages: list[int] | None = None,
    ) -> AssessmentSchema:
        """Deterministic explicit-rubric assessment engine enforcing all Phase 6 rules."""
        clean_answer = student_answer.strip()
        if numeric_verification is None:
            numeric_verification = verify_numerical_calculation(
                clean_answer, rubric.numerical_check
            )

        answer_stems = set(_tokenize_stems(clean_answer))
        domain_text = " ".join(
            [
                concept_title,
                question_text,
                ideal_answer_summary,
                " ".join(rubric.required_ideas),
                " ".join(
                    idea
                    for crit in rubric.criteria
                    for idea in [crit.name, crit.description, *crit.required_ideas]
                ),
            ]
        )
        domain_stems = {
            s
            for s in _tokenize_stems(domain_text)
            if s not in {_stem_token(w) for w in _GENERIC_VAGUE_WORDS}
        }
        matched_domain_stems = answer_stems & domain_stems

        # 1. Check for explicit ambiguity / self-contradiction first
        is_ambiguous, ambiguity_evidence = _is_ambiguous_answer(clean_answer)
        if is_ambiguous and ambiguity_evidence:
            missing = rubric.required_ideas[:2] or [
                f"State a single unambiguous explanation of {concept_title}"
            ]
            feedback = generate_assessment_feedback(
                concept_title=concept_title,
                verdict="INSUFFICIENT_EVIDENCE",
                rubric_score=25.0,
                strengths=[],
                gaps=missing,
                misconception=None,
                misconception_correction=None,
                error_classification="AMBIGUOUS_OR_VAGUE",
                numeric_verification=numeric_verification,
                next_activity="CLARIFY_AMBIGUOUS_ANSWER",
                relevant_pages=relevant_pages,
            )
            return AssessmentSchema(
                concept_id=concept_id,
                verdict="INSUFFICIENT_EVIDENCE",
                rubric_score=25.0,
                strengths=[],
                gaps=missing,
                misconception=None,
                evidence=[ambiguity_evidence],
                confidence=0.45,
                next_activity="CLARIFY_AMBIGUOUS_ANSWER",
                feedback_explanation=feedback,
                error_classification="AMBIGUOUS_OR_VAGUE",
                uncertain_evaluation=True,
                criteria_scores=[
                    {
                        "criterion_id": crit.criterion_id,
                        "name": crit.name,
                        "awarded_points": round(crit.max_points * 0.25, 1),
                        "max_points": crit.max_points,
                        "feedback": "Answer is hedged or self-contradictory; clarify which mechanism actually applies.",
                    }
                    for crit in rubric.criteria
                ],
                numeric_verification=numeric_verification if numeric_verification.applied else None,
                prompt_version=self.prompt_version,
            )

        # 2. Check for supported misconception (must have explicit quote evidence)
        misconception_label, misc_evidence, misc_correction = _detect_supported_misconception(
            clean_answer, rubric
        )

        # 3. Check for vague or non-answer (when no explicit misconception or numeric calculation is present)
        is_vague, vague_evidence = _is_vague_or_non_answer(
            clean_answer, matched_domain_stems, numeric_verification
        )
        if is_vague and vague_evidence and misconception_label is None:
            missing = rubric.required_ideas[:2] or [
                f"Provide specific technical details explaining {concept_title}"
            ]
            feedback = generate_assessment_feedback(
                concept_title=concept_title,
                verdict="INSUFFICIENT_EVIDENCE",
                rubric_score=15.0,
                strengths=[],
                gaps=missing,
                misconception=None,
                misconception_correction=None,
                error_classification="AMBIGUOUS_OR_VAGUE",
                numeric_verification=numeric_verification,
                next_activity="CLARIFY_AMBIGUOUS_ANSWER",
                relevant_pages=relevant_pages,
            )
            return AssessmentSchema(
                concept_id=concept_id,
                verdict="INSUFFICIENT_EVIDENCE",
                rubric_score=15.0,
                strengths=[],
                gaps=missing,
                misconception=None,
                evidence=[vague_evidence],
                confidence=0.50,
                next_activity="CLARIFY_AMBIGUOUS_ANSWER",
                feedback_explanation=feedback,
                error_classification="AMBIGUOUS_OR_VAGUE",
                uncertain_evaluation=True,
                criteria_scores=[
                    {
                        "criterion_id": crit.criterion_id,
                        "name": crit.name,
                        "awarded_points": round(crit.max_points * 0.15, 1),
                        "max_points": crit.max_points,
                        "feedback": "Insufficient detail to verify mastery of this rubric criterion.",
                    }
                    for crit in rubric.criteria
                ],
                numeric_verification=numeric_verification if numeric_verification.applied else None,
                prompt_version=self.prompt_version,
            )

        # 4. Check for off-topic answer (substantive text with zero domain overlap and no numeric match)
        if (
            len(matched_domain_stems) == 0
            and misconception_label is None
            and not (numeric_verification.applied and numeric_verification.is_correct)
        ):
            missing = rubric.required_ideas or [f"Address {concept_title} as asked in the prompt"]
            feedback = generate_assessment_feedback(
                concept_title=concept_title,
                verdict="OFF_TOPIC",
                rubric_score=0.0,
                strengths=[],
                gaps=missing,
                misconception=None,
                misconception_correction=None,
                error_classification="OFF_TOPIC",
                numeric_verification=numeric_verification,
                next_activity="REFOCUS_ON_COURSE_CONCEPT",
                relevant_pages=relevant_pages,
            )
            return AssessmentSchema(
                concept_id=concept_id,
                verdict="OFF_TOPIC",
                rubric_score=0.0,
                strengths=[],
                gaps=missing,
                misconception=None,
                evidence=[
                    f'Student response ("{clean_answer[:120]}") shares zero required conceptual terms with {concept_title}.'
                ],
                confidence=0.90,
                next_activity="REFOCUS_ON_COURSE_CONCEPT",
                feedback_explanation=feedback,
                error_classification="OFF_TOPIC",
                uncertain_evaluation=False,
                criteria_scores=[
                    {
                        "criterion_id": crit.criterion_id,
                        "name": crit.name,
                        "awarded_points": 0.0,
                        "max_points": crit.max_points,
                        "feedback": f"Response is unrelated to {crit.name}.",
                    }
                    for crit in rubric.criteria
                ],
                numeric_verification=numeric_verification if numeric_verification.applied else None,
                prompt_version=self.prompt_version,
            )

        # 5. Evaluate explicit rubric required ideas and criteria
        strengths: list[str] = []
        gaps: list[str] = []
        evidence: list[str] = []
        criteria_scores: list[dict[str, Any]] = []

        # Evaluate each required idea in the rubric
        all_ideas = list(rubric.required_ideas)
        if not all_ideas:
            for c in rubric.criteria:
                all_ideas.extend(c.required_ideas)

        matched_ideas: list[str] = []
        missing_ideas: list[str] = []

        generic_stems = {_stem_token(w) for w in _GENERIC_VAGUE_WORDS}
        idea_stem_sets: list[set[str]] = []
        for idea in all_ideas:
            stems = {s for s in _tokenize_stems(idea) if s not in generic_stems}
            if not stems:
                stems = set(_tokenize_stems(idea))
            idea_stem_sets.append(stems)

        for idx_idea, idea in enumerate(all_ideas):
            unique_idea_stems = idea_stem_sets[idx_idea]
            other_stems = (
                set().union(*(s for j, s in enumerate(idea_stem_sets) if j != idx_idea))
                if len(idea_stem_sets) > 1
                else set()
            )
            distinctive_stems = unique_idea_stems - other_stems

            overlap = answer_stems & unique_idea_stems
            ratio = len(overlap) / max(1, min(len(unique_idea_stems), 5))

            if distinctive_stems:
                dist_overlap = answer_stems & distinctive_stems
                dist_ratio = len(dist_overlap) / max(1, min(len(distinctive_stems), 4))
                is_idea_matched = (dist_ratio >= 0.4 or len(dist_overlap) >= 2) and (
                    ratio >= 0.45 or len(overlap) >= 2
                )
            else:
                is_idea_matched = ratio >= 0.5 or len(overlap) >= 2

            if is_idea_matched:
                matched_ideas.append(idea)
            else:
                missing_ideas.append(idea)

        # Check causal reasoning connectors
        reasoning_markers = {
            "becaus",
            "therefor",
            "sinc",
            "when",
            "caus",
            "result",
            "prevent",
            "translat",
            "allow",
            "ensur",
            "if",
            "then",
            "via",
            "through",
            "avoid",
            "so",
        }
        has_reasoning = any(s in reasoning_markers for s in answer_stems)
        word_count = len(clean_answer.split())

        total_awarded = 0.0
        for idx, crit in enumerate(rubric.criteria):
            crit_ideas = crit.required_ideas or all_ideas
            crit_matched = [i for i in crit_ideas if i in matched_ideas]
            crit_missing = [i for i in crit_ideas if i not in crit_matched]

            idea_fraction = len(crit_matched) / max(1, len(crit_ideas))
            crit_stems = {
                s
                for s in _tokenize_stems(" ".join(crit_ideas) + " " + crit.description)
                if s not in {_stem_token(w) for w in _GENERIC_VAGUE_WORDS}
            }
            crit_stem_cov = (
                min(1.0, len(answer_stems & crit_stems) / max(1, min(len(crit_stems), 5)))
                if crit_stems
                else 0.0
            )
            effective_cov = max(idea_fraction, crit_stem_cov * 0.75)

            if crit.numerical_check is not None or (
                idx == len(rubric.criteria) - 1 and numeric_verification.applied
            ):
                if numeric_verification.is_correct:
                    raw_pts = crit.max_points * max(0.9, effective_cov)
                else:
                    raw_pts = crit.max_points * min(0.35, effective_cov * 0.4)
            elif idea_fraction == 0.0 and crit_stem_cov < 0.35:
                raw_pts = crit.max_points * (crit_stem_cov * 0.4)
            elif idx == 0:
                raw_pts = crit.max_points * (
                    effective_cov * 0.85 + (0.15 if word_count >= 10 else word_count * 0.015)
                )
            else:
                raw_pts = crit.max_points * (
                    effective_cov * 0.75
                    + (0.15 if has_reasoning else 0.04)
                    + (0.10 if word_count >= 14 else word_count * 0.007)
                )

            if misconception_label is not None:
                raw_pts = min(raw_pts, crit.max_points * 0.30)

            awarded = round(min(crit.max_points, max(0.0, raw_pts)), 1)
            total_awarded += awarded

            if awarded >= crit.max_points * 0.75:
                crit_fb = f"Demonstrated strong understanding of {crit.name}."
            elif awarded >= crit.max_points * 0.45:
                crit_fb = (
                    f"Partially addressed {crit.name}; missing: "
                    f"{crit_missing[0] if crit_missing else 'complete step-by-step link'}."
                )
            else:
                crit_fb = (
                    f"Did not sufficiently cover {crit.name}: "
                    f"{crit_missing[0] if crit_missing else crit.description}"
                )

            criteria_scores.append(
                {
                    "criterion_id": crit.criterion_id,
                    "name": crit.name,
                    "awarded_points": awarded,
                    "max_points": crit.max_points,
                    "matched_ideas": crit_matched,
                    "missing_ideas": crit_missing,
                    "feedback": crit_fb,
                }
            )

        for idea in matched_ideas:
            strengths.append(f"Correctly covered required idea: {idea}")
        for idea in missing_ideas:
            gaps.append(f"Missing required idea: {idea}")

        if numeric_verification.applied and numeric_verification.detail:
            evidence.append(numeric_verification.detail)
            if numeric_verification.is_correct:
                strengths.insert(
                    0,
                    f"Accurately calculated expected value ({numeric_verification.expected_value}"
                    f"{' ' + numeric_verification.unit if numeric_verification.unit else ''}).",
                )
            else:
                gaps.insert(0, numeric_verification.detail)

        if misconception_label and misc_evidence:
            evidence.insert(0, misc_evidence)
            gaps.insert(0, f"Factual misconception to correct: {misconception_label}")

        if matched_ideas:
            evidence.append(
                f"Matched {len(matched_ideas)}/{len(all_ideas)} required rubric ideas in student response."
            )
        elif matched_domain_stems:
            evidence.append(
                f"Student referenced relevant concept stems ({', '.join(sorted(list(matched_domain_stems))[:5])}) "
                f"but missed key rubric clauses."
            )

        rubric_score = round(min(100.0, max(0.0, total_awarded)), 1)

        # Determine final verdict, error_classification, confidence, and next_activity
        if misconception_label is not None:
            verdict: AssessmentVerdict = "INCORRECT"
            error_classification: ErrorClassification = "FACTUAL_MISTAKE"
            rubric_score = min(rubric_score, 32.0)
            next_activity = "REMEDIATION_EXPLANATION"
            confidence = 0.90
        elif numeric_verification.applied and numeric_verification.is_correct is False:
            error_classification = "CALCULATION_ERROR"
            if len(matched_ideas) >= max(1, len(all_ideas) // 2) and rubric_score >= 45.0:
                verdict = "PARTIALLY_CORRECT"
                rubric_score = min(65.0, max(48.0, rubric_score))
                next_activity = "PRACTICE_SAME_CONCEPT"
            else:
                verdict = "INCORRECT"
                rubric_score = min(35.0, rubric_score)
                next_activity = "REMEDIATION_EXPLANATION"
            confidence = 0.92
        elif rubric_score >= 78.0 and (
            len(missing_ideas) == 0
            or (len(all_ideas) >= 3 and len(matched_ideas) >= len(all_ideas) - 1)
        ):
            verdict = "CORRECT"
            error_classification = "NONE"
            gaps = []
            if not strengths:
                strengths.append(f"Thoroughly explained {concept_title}.")
            next_activity = "ADVANCE_DIFFICULTY"
            confidence = 0.90
        elif rubric_score >= 42.0 or len(matched_ideas) >= 1:
            verdict = "PARTIALLY_CORRECT"
            error_classification = "INCOMPLETE_REASONING"
            rubric_score = max(45.0, min(74.0, rubric_score))
            if not strengths:
                strengths.append(f"Identified foundational terminology for {concept_title}.")
            if not gaps:
                gaps.append(
                    f"Expand on the complete cause-and-effect mechanism of {concept_title}."
                )
            next_activity = "PRACTICE_SAME_CONCEPT"
            confidence = 0.84
        else:
            verdict = "INCORRECT"
            error_classification = "INCOMPLETE_REASONING"
            if not gaps:
                gaps.append(f"Did not explain the required core mechanism of {concept_title}.")
            next_activity = "REMEDIATION_EXPLANATION"
            confidence = 0.82

        feedback = generate_assessment_feedback(
            concept_title=concept_title,
            verdict=verdict,
            rubric_score=rubric_score,
            strengths=strengths,
            gaps=gaps,
            misconception=misconception_label,
            misconception_correction=misc_correction,
            error_classification=error_classification,
            numeric_verification=numeric_verification,
            next_activity=next_activity,
            relevant_pages=relevant_pages,
        )

        return AssessmentSchema(
            concept_id=concept_id,
            verdict=verdict,
            rubric_score=rubric_score,
            strengths=strengths,
            gaps=gaps,
            misconception=misconception_label,
            evidence=evidence,
            confidence=confidence,
            next_activity=next_activity,
            feedback_explanation=feedback,
            error_classification=error_classification,
            uncertain_evaluation=confidence < 0.65,
            criteria_scores=criteria_scores,
            numeric_verification=numeric_verification if numeric_verification.applied else None,
            prompt_version=self.prompt_version,
        )
