"""Learning Evidence Service managing immutable concept-level evidence history and recency."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Concept
from app.models.learning import LearningEvidence


class LearningEvidenceService:
    """Persists and queries concept-level LearningEvidence records while preserving full history."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def record_evidence(
        self,
        *,
        user_id: uuid.UUID,
        concept_id: uuid.UUID,
        evaluation_id: uuid.UUID | None,
        evidence_type: str,
        score_delta: float,
        observed_score: float,
        summary: str,
        metadata_json: dict[str, Any],
    ) -> LearningEvidence:
        """Create and persist a new immutable LearningEvidence row."""
        evidence = LearningEvidence(
            user_id=user_id,
            concept_id=concept_id,
            evaluation_id=evaluation_id,
            evidence_type=evidence_type,
            score_delta=score_delta,
            observed_score=observed_score,
            summary=summary,
            metadata_json=metadata_json,
        )
        self.db.add(evidence)
        self.db.commit()
        self.db.refresh(evidence)
        return evidence

    def list_evidence_for_concept(
        self,
        *,
        user_id: uuid.UUID,
        concept_id: uuid.UUID,
    ) -> list[LearningEvidence]:
        """Return all historical LearningEvidence records for a user and concept (oldest to newest)."""
        stmt = (
            select(LearningEvidence)
            .where(
                LearningEvidence.user_id == user_id,
                LearningEvidence.concept_id == concept_id,
            )
            .order_by(LearningEvidence.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def list_recent_evidence_for_course(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        limit: int = 20,
    ) -> list[tuple[LearningEvidence, Concept]]:
        """Return the most recent LearningEvidence items across all concepts in a course."""
        stmt = (
            select(LearningEvidence, Concept)
            .join(Concept, LearningEvidence.concept_id == Concept.id)
            .where(
                LearningEvidence.user_id == user_id,
                Concept.course_id == course_id,
            )
            .order_by(LearningEvidence.created_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).all())  # type: ignore[return-value]

    @staticmethod
    def compute_evidence_recency_hours(
        evidences: list[LearningEvidence],
        now: datetime | None = None,
    ) -> float | None:
        """Compute hours elapsed since the most recent LearningEvidence record."""
        if not evidences:
            return None
        latest_ts = evidences[-1].created_at
        if latest_ts.tzinfo is None:
            latest_ts = latest_ts.replace(tzinfo=timezone.utc)
        ref_now = now or datetime.now(timezone.utc)
        delta_sec = max(0.0, (ref_now - latest_ts).total_seconds())
        return round(delta_sec / 3600.0, 2)

    @staticmethod
    def summarize_evidence_history(
        evidences: list[LearningEvidence],
    ) -> dict[str, Any]:
        """Aggregate independent/assisted success counts, strengths, and gaps from evidence history."""
        independent_success_count = 0
        assisted_success_count = 0
        consecutive_independent = 0
        strengths: list[str] = []
        gaps: list[str] = []

        for ev in evidences:
            meta = dict(ev.metadata_json or {})
            verdict = str(meta.get("verdict") or "").upper()
            hints_used = int(meta.get("hints_used") or 0)
            uncertain = bool(meta.get("uncertain_evaluation") or False)

            if verdict == "CORRECT" and hints_used == 0 and not uncertain:
                independent_success_count += 1
                consecutive_independent += 1
            elif verdict == "CORRECT" and hints_used > 0:
                assisted_success_count += 1
                consecutive_independent = 0
            else:
                consecutive_independent = 0

            for s in meta.get("strengths") or []:
                if s and s not in strengths:
                    strengths.append(str(s))
            for g in meta.get("gaps") or []:
                if g and g not in gaps:
                    gaps.append(str(g))
            misc = meta.get("misconception")
            if misc:
                misc_item = f"Misconception to resolve: {misc}"
                if misc_item not in gaps:
                    gaps.insert(0, misc_item)

        # If the most recent evidence was a clean CORRECT answer with 0 gaps, prune resolved gaps
        if evidences:
            last_meta = dict(evidences[-1].metadata_json or {})
            if (
                str(last_meta.get("verdict") or "").upper() == "CORRECT"
                and int(last_meta.get("hints_used") or 0) == 0
                and consecutive_independent >= 2
            ):
                gaps = []

        return {
            "independent_success_count": independent_success_count,
            "assisted_success_count": assisted_success_count,
            "consecutive_independent_successes": consecutive_independent,
            "observed_strengths": strengths[:5],
            "areas_needing_practice": gaps[:5],
        }
