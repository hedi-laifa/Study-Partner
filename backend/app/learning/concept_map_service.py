"""Concept Map Service organizing course concepts into a prerequisite/sequence graph."""

from __future__ import annotations

import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Concept
from app.models.learning import ConceptProgress
from app.repositories.session_repository import SessionRepository
from app.schemas.learning import ConceptMapNode, EvidenceStatus, MasteryStatus


class ConceptMapService:
    """Builds and queries the course Concept Map with prerequisite links and mastery states."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.session_repo = SessionRepository(db)

    def ensure_and_list_concepts(self, course_id: uuid.UUID) -> list[Concept]:
        """Ensure course concepts are extracted from READY PDFs and return them in sequence order."""
        return self.session_repo.ensure_course_concepts_from_chunks(course_id)

    def build_course_concept_map(
        self,
        *,
        course_id: uuid.UUID,
        user_id: uuid.UUID,
        evidence_status_map: dict[uuid.UUID, EvidenceStatus] | None = None,
    ) -> list[ConceptMapNode]:
        """Construct an ordered list of ConceptMapNodes with prerequisite and dependent edges."""
        concepts = self.ensure_and_list_concepts(course_id)
        if not concepts:
            return []

        prog_stmt = select(ConceptProgress).where(
            ConceptProgress.course_id == course_id,
            ConceptProgress.user_id == user_id,
        )
        progress_by_concept = {
            p.concept_id: p for p in self.db.scalars(prog_stmt).all()
        }

        nodes: list[ConceptMapNode] = []
        for idx, concept in enumerate(concepts):
            prereq_ids = [concepts[idx - 1].id] if idx > 0 else []
            dep_ids = [concepts[idx + 1].id] if idx + 1 < len(concepts) else []
            prog = progress_by_concept.get(concept.id)
            m_score = round(prog.mastery_score, 1) if prog else 0.0
            m_status: MasteryStatus = (
                prog.mastery_status  # type: ignore[assignment]
                if prog and prog.mastery_status in {"NOT_STARTED", "NEEDS_REVIEW", "LEARNING", "MASTERED"}
                else "NOT_STARTED"
            )
            ev_status: EvidenceStatus = (
                evidence_status_map.get(concept.id, "NO_EVIDENCE")
                if evidence_status_map
                else ("STRONG_INDEPENDENT_EVIDENCE" if m_status == "MASTERED" else "NO_EVIDENCE")
            )

            nodes.append(
                ConceptMapNode(
                    concept_id=concept.id,
                    title=concept.title,
                    summary=concept.summary,
                    display_order=concept.display_order,
                    source_pages=list(concept.source_pages or []),
                    prerequisite_concept_ids=prereq_ids,
                    dependent_concept_ids=dep_ids,
                    mastery_score=m_score,
                    mastery_status=m_status,
                    evidence_status=ev_status,
                )
            )
        return nodes
