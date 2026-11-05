"""Explicit Rubric model, storage serialization, and deterministic numerical verification."""

from __future__ import annotations

import math
import re
from typing import Any
import uuid

from app.retrieval.embeddings import STOPWORDS
from app.schemas.assessment import (
    ActivityRubric,
    MisconceptionPattern,
    NumericalCheckSpec,
    NumericVerificationResult,
    RubricCriterionModel,
)


def _extract_meaningful_phrases(text: str, max_ideas: int = 4) -> list[str]:
    """Extract required conceptual ideas/clauses from reference text or ideal summary."""
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []

    raw_clauses = re.split(r"(?<=[.!?])\s+|;\s+|\b(?:because|whereas|while|so that)\b", cleaned)
    ideas: list[str] = []
    seen: set[str] = set()
    for clause in raw_clauses:
        c = clause.strip(" ,.-:")
        if len(c) < 12:
            continue
        norm = c.lower()
        if norm in seen:
            continue
        seen.add(norm)
        ideas.append(c)
        if len(ideas) >= max_ideas:
            break

    if not ideas and cleaned:
        ideas.append(cleaned[:140])
    return ideas


def _extract_technical_terms(text: str, limit: int = 6) -> list[str]:
    """Extract domain-specific technical terms from reference text."""
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", text or "")
    seen: set[str] = set()
    terms: list[str] = []
    for word in words:
        low = word.lower()
        if low in STOPWORDS or low in seen or len(low) < 3:
            continue
        seen.add(low)
        terms.append(word)
        if len(terms) >= limit:
            break
    return terms


def _detect_default_misconception_patterns(
    concept_title: str,
    ideal_answer_summary: str,
    passage_text: str,
) -> list[MisconceptionPattern]:
    """Build explicit, evidence-gated misconception patterns for the concept."""
    combined = f"{concept_title} {ideal_answer_summary} {passage_text}".lower()
    patterns: list[MisconceptionPattern] = []

    if "mmu" in combined or "virtual" in combined or "page table" in combined:
        patterns.append(
            MisconceptionPattern(
                pattern_id="misc_inverted_address_translation",
                misconception_label="Confuses direction of MMU address translation (claiming physical addresses are translated into virtual addresses).",
                trigger_phrases=[
                    "physical to virtual",
                    "physical address into virtual",
                    "physical addresses into virtual",
                    "physical frame into virtual page",
                    "translates physical addresses to virtual",
                ],
                correction_explanation="The hardware MMU translates virtual page numbers (used by processes) into physical frame numbers in RAM, not physical-to-virtual.",
            )
        )
        patterns.append(
            MisconceptionPattern(
                pattern_id="misc_page_fault_terminates_process",
                misconception_label="Believes a standard page fault on an unmapped valid page immediately crashes or terminates the process instead of trapping to the OS kernel to load the page.",
                trigger_phrases=[
                    "page fault crashes the computer",
                    "page fault always kills the process",
                    "page fault deletes the page table",
                    "mmu ignores unmapped pages",
                ],
                correction_explanation="When a valid virtual page is unmapped in RAM, the MMU raises a page fault trap so the OS kernel can fetch the page from disk into a physical frame.",
            )
        )

    if "tlb" in combined or "translation lookaside buffer" in combined:
        patterns.append(
            MisconceptionPattern(
                pattern_id="misc_tlb_replaces_page_table",
                misconception_label="Claims the TLB completely replaces the page table in main memory or that TLB lookups never miss.",
                trigger_phrases=[
                    "replaces the page table",
                    "eliminates the page table",
                    "tlb never misses",
                    "stored on disk cache",
                    "tlb is a disk cache",
                ],
                correction_explanation="The TLB is a fast hardware cache of recent page table entries; on a TLB miss, the system must still walk the page table in main memory.",
            )
        )
        patterns.append(
            MisconceptionPattern(
                pattern_id="misc_asid_flushes_every_switch",
                misconception_label="Claims Address Space Identifiers (ASIDs) force a full TLB flush on every context switch.",
                trigger_phrases=[
                    "asid forces a full tlb flush",
                    "asids require flushing the entire tlb",
                    "asid clears the tlb on every context switch",
                ],
                correction_explanation="ASIDs tag TLB entries with a process identifier specifically to avoid flushing the entire TLB on every context switch.",
            )
        )

    if "raft" in combined or "consensus" in combined or "leader election" in combined:
        patterns.append(
            MisconceptionPattern(
                pattern_id="misc_raft_no_majority_quorum",
                misconception_label="Claims a Raft candidate can become leader or commit entries without a majority quorum of nodes.",
                trigger_phrases=[
                    "without a majority",
                    "single vote is enough",
                    "does not need a majority",
                    "any follower can commit",
                    "minority of votes",
                ],
                correction_explanation="Raft requires a strict majority quorum ((N/2) + 1) for both leader election (RequestVote) and log commitment (AppendEntries).",
            )
        )

    if "starvation" in combined or "priority scheduling" in combined or "aging" in combined:
        patterns.append(
            MisconceptionPattern(
                pattern_id="misc_aging_decreases_priority",
                misconception_label="Claims aging solves starvation by decreasing the priority of waiting processes rather than gradually increasing it.",
                trigger_phrases=[
                    "decreases the priority of waiting",
                    "lowers the priority of waiting",
                    "aging reduces priority of starved",
                    "deletes low priority processes",
                ],
                correction_explanation="Aging prevents starvation by gradually increasing the priority of processes that wait in the ready queue for a long time.",
            )
        )

    # Always include a general explicit contradiction detector pattern
    terms = _extract_technical_terms(f"{concept_title} {ideal_answer_summary}", limit=3)
    primary_term = terms[0].lower() if terms else concept_title.lower()
    patterns.append(
        MisconceptionPattern(
            pattern_id="misc_explicit_negation",
            misconception_label=f"Explicitly denies the core role or existence of {concept_title}.",
            trigger_phrases=[
                f"{primary_term} is never used",
                f"{primary_term} has nothing to do with",
                f"does not use {primary_term} at all",
            ],
            correction_explanation=f"Review the course material on how {concept_title} functions as a core mechanism.",
        )
    )

    return patterns


def _detect_numerical_check_spec(
    question_text: str,
    ideal_answer_summary: str,
) -> NumericalCheckSpec | None:
    """Detect if a question/summary defines a quantitative target for deterministic checking."""
    combined = f"{question_text} {ideal_answer_summary}"
    # Only attach an automatic numerical check when the question explicitly asks to calculate/compute a number
    asks_calculation = bool(
        re.search(
            r"\b(calculate|compute|what is the numerical|how many|effective access time|quorum size|speedup)\b",
            question_text.lower(),
        )
    )
    if not asks_calculation:
        return None

    match = re.search(
        r"(?:equals|=|is)\s*(-?\d+(?:\.\d+)?)\s*(ns|ms|s|%|cycles|nodes|bytes|kb|mb|frames|pages|bits)?\b",
        ideal_answer_summary,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    value = float(match.group(1))
    unit = match.group(2)
    return NumericalCheckSpec(
        expected_value=value,
        tolerance=max(0.01, abs(value) * 0.01),
        unit=unit,
        formula_description=ideal_answer_summary[:160],
    )


def build_explicit_rubric(
    *,
    concept_id: uuid.UUID | None,
    concept_title: str,
    ideal_answer_summary: str,
    question_text: str = "",
    passage_text: str = "",
) -> ActivityRubric:
    """Construct a rich, explicit ActivityRubric for an activity."""
    required_ideas = _extract_meaningful_phrases(
        f"{ideal_answer_summary}. {passage_text}", max_ideas=4
    )
    terms = _extract_technical_terms(f"{concept_title} {ideal_answer_summary} {passage_text}", limit=6)
    if len(required_ideas) < 2 and terms:
        for t in terms[:3]:
            idea = f"Explains the role of {t} in {concept_title}"
            if idea not in required_ideas:
                required_ideas.append(idea)

    mid = max(1, len(required_ideas) // 2)
    core_ideas = required_ideas[:mid] or [f"Defines {concept_title} accurately"]
    reasoning_ideas = required_ideas[mid:] or [
        f"Explains the cause-and-effect mechanism of {concept_title}"
    ]

    misconceptions = _detect_default_misconception_patterns(
        concept_title=concept_title,
        ideal_answer_summary=ideal_answer_summary,
        passage_text=passage_text,
    )
    numeric_spec = _detect_numerical_check_spec(question_text, ideal_answer_summary)

    criteria: list[RubricCriterionModel] = [
        RubricCriterionModel(
            criterion_id="core_concepts",
            name="Core Concepts & Required Ideas",
            description=f"Identifies and accurately states the foundational concepts of {concept_title} ({', '.join(terms[:3]) or concept_title}).",
            max_points=50.0,
            required_ideas=core_ideas,
            misconception_patterns=misconceptions,
        ),
        RubricCriterionModel(
            criterion_id="causal_reasoning",
            name="Causal Reasoning & Mechanism",
            description="Explains the step-by-step cause-and-effect relationship grounded in the course material.",
            max_points=50.0,
            required_ideas=reasoning_ideas,
            numerical_check=numeric_spec,
        ),
    ]

    return ActivityRubric(
        rubric_version="1.0",
        concept_id=concept_id,
        concept_title=concept_title,
        required_ideas=required_ideas,
        criteria=criteria,
        misconception_patterns=misconceptions,
        numerical_check=numeric_spec,
    )


def serialize_rubric_for_storage(rubric: ActivityRubric) -> list[dict[str, Any]]:
    """Serialize an ActivityRubric into the list[dict] format stored in Activity.rubric_json."""
    rows: list[dict[str, Any]] = []
    for idx, crit in enumerate(rubric.criteria):
        row = crit.model_dump(mode="json")
        if idx == 0:
            row["_rubric_meta"] = {
                "rubric_version": rubric.rubric_version,
                "concept_id": str(rubric.concept_id) if rubric.concept_id else None,
                "concept_title": rubric.concept_title,
                "required_ideas": rubric.required_ideas,
                "misconception_patterns": [
                    m.model_dump(mode="json") for m in rubric.misconception_patterns
                ],
                "numerical_check": (
                    rubric.numerical_check.model_dump(mode="json")
                    if rubric.numerical_check
                    else None
                ),
            }
        rows.append(row)
    return rows


def parse_activity_rubric(
    *,
    rubric_json: list[dict[str, Any]] | dict[str, Any] | None,
    concept_id: uuid.UUID,
    concept_title: str,
    ideal_answer_summary: str = "",
    question_text: str = "",
) -> ActivityRubric:
    """Reconstruct an explicit ActivityRubric from Activity.rubric_json (upgrading legacy rubrics seamlessly)."""
    if isinstance(rubric_json, dict):
        if "criteria" in rubric_json:
            parsed = ActivityRubric.model_validate(
                {**rubric_json, "concept_id": concept_id, "concept_title": concept_title}
            )
            if not parsed.misconception_patterns:
                parsed.misconception_patterns = _detect_default_misconception_patterns(
                    concept_title, ideal_answer_summary, question_text
                )
            return parsed
        rubric_json = [rubric_json]

    fallback = build_explicit_rubric(
        concept_id=concept_id,
        concept_title=concept_title,
        ideal_answer_summary=ideal_answer_summary or concept_title,
        question_text=question_text,
    )

    if not rubric_json or not isinstance(rubric_json, list):
        return fallback

    meta = rubric_json[0].get("_rubric_meta") if isinstance(rubric_json[0], dict) else None
    criteria: list[RubricCriterionModel] = []
    all_required_ideas: list[str] = []

    for idx, item in enumerate(rubric_json):
        if not isinstance(item, dict):
            continue
        crit_id = str(item.get("criterion_id") or f"crit_{idx + 1}")
        name = str(item.get("name") or f"Criterion {idx + 1}")
        desc = str(item.get("description") or name)
        max_pts = float(item.get("max_points") or (100.0 / max(1, len(rubric_json))))
        req_ideas = list(item.get("required_ideas") or [])
        if not req_ideas:
            req_ideas = _extract_meaningful_phrases(desc, max_ideas=2) or [desc]
        for idea in req_ideas:
            if idea not in all_required_ideas:
                all_required_ideas.append(idea)

        misc_raw = item.get("misconception_patterns") or []
        misc_list = [
            MisconceptionPattern.model_validate(m)
            for m in misc_raw
            if isinstance(m, dict)
        ]
        num_raw = item.get("numerical_check")
        num_spec = (
            NumericalCheckSpec.model_validate(num_raw)
            if isinstance(num_raw, dict)
            else None
        )

        criteria.append(
            RubricCriterionModel(
                criterion_id=crit_id,
                name=name,
                description=desc,
                max_points=max_pts,
                required_ideas=req_ideas,
                misconception_patterns=misc_list,
                numerical_check=num_spec,
            )
        )

    if not criteria:
        return fallback

    if isinstance(meta, dict):
        required_ideas = list(meta.get("required_ideas") or all_required_ideas or fallback.required_ideas)
        misconception_patterns = [
            MisconceptionPattern.model_validate(m)
            for m in (meta.get("misconception_patterns") or [])
            if isinstance(m, dict)
        ] or fallback.misconception_patterns
        num_meta = meta.get("numerical_check")
        numerical_check = (
            NumericalCheckSpec.model_validate(num_meta)
            if isinstance(num_meta, dict)
            else fallback.numerical_check
        )
    else:
        required_ideas = all_required_ideas or fallback.required_ideas
        misconception_patterns = fallback.misconception_patterns
        numerical_check = fallback.numerical_check

    return ActivityRubric(
        rubric_version="1.0",
        concept_id=concept_id,
        concept_title=concept_title,
        required_ideas=required_ideas,
        criteria=criteria,
        misconception_patterns=misconception_patterns,
        numerical_check=numerical_check,
    )


def _extract_numeric_candidates_from_text(text: str) -> list[float]:
    """Extract numeric values (including decimals, fractions like 3/5, and simple equations) from student text."""
    candidates: list[float] = []
    seen: set[float] = set()

    def _add(val: float) -> None:
        rounded = round(val, 6)
        if not math.isnan(rounded) and not math.isinf(rounded) and rounded not in seen:
            seen.add(rounded)
            candidates.append(val)

    # 1. Numbers following '=' or 'is' or 'equals' first (highest priority)
    eq_matches = re.findall(
        r"(?:=|\bequals\b|\bis\b|\bresult\s+is\b)\s*(-?\d+(?:\.\d+)?)",
        text.lower(),
    )
    for m in eq_matches:
        try:
            _add(float(m))
        except ValueError:
            pass

    # 2. Fractions a/b
    for num_s, den_s in re.findall(r"\b(-?\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\b", text):
        try:
            den = float(den_s)
            if den != 0:
                _add(float(num_s) / den)
        except ValueError:
            pass

    # 3. All standalone numbers
    for m in re.findall(r"(?<![A-Za-z])(-?\d+(?:\.\d+)?)", text):
        try:
            _add(float(m))
        except ValueError:
            pass

    return candidates


def verify_numerical_calculation(
    student_answer: str,
    spec: NumericalCheckSpec | None,
) -> NumericVerificationResult:
    """Deterministically verify numerical calculations in a student's answer."""
    if spec is None:
        return NumericVerificationResult(applied=False)

    extracted = _extract_numeric_candidates_from_text(student_answer)
    unit_suffix = f" {spec.unit}" if spec.unit else ""

    if not extracted:
        return NumericVerificationResult(
            applied=True,
            expected_value=spec.expected_value,
            extracted_student_values=[],
            matched_value=None,
            is_correct=False,
            tolerance=spec.tolerance,
            unit=spec.unit,
            detail=(
                f"Expected numerical value {spec.expected_value}{unit_suffix}, "
                "but the student answer did not include any numerical value."
            ),
        )

    # Check if the final/primary concluded number (or any explicit result) matches within tolerance
    for val in extracted:
        if abs(val - spec.expected_value) <= spec.tolerance:
            return NumericVerificationResult(
                applied=True,
                expected_value=spec.expected_value,
                extracted_student_values=extracted,
                matched_value=val,
                is_correct=True,
                tolerance=spec.tolerance,
                unit=spec.unit,
                detail=(
                    f"Deterministic numerical check passed: student value {val}{unit_suffix} "
                    f"matches expected {spec.expected_value}{unit_suffix} (tolerance ±{spec.tolerance})."
                ),
            )

    primary_wrong = extracted[0]
    return NumericVerificationResult(
        applied=True,
        expected_value=spec.expected_value,
        extracted_student_values=extracted,
        matched_value=primary_wrong,
        is_correct=False,
        tolerance=spec.tolerance,
        unit=spec.unit,
        detail=(
            f"Deterministic numerical check failed: student calculated {primary_wrong}{unit_suffix}, "
            f"which differs from expected {spec.expected_value}{unit_suffix} (tolerance ±{spec.tolerance})."
        ),
    )
