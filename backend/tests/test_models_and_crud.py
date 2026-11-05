"""Tests for all 12 SQLAlchemy models, CRUD services, ownership enforcement, and API endpoints."""
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, OwnershipViolationError
from app.schemas.course import (
    ChunkMetadataCreate,
    ConceptCreate,
    CourseCreate,
    DocumentCreate,
    DocumentUpdate,
)
from app.schemas.learning import (
    ConceptProgressCreate,
    ConceptProgressUpdate,
    LearningEvidenceCreate,
    RevisionTaskCreate,
    RevisionTaskUpdate,
)
from app.schemas.session import (
    ActivityCreate,
    AttemptCreate,
    EvaluationCreate,
    StudySessionCreate,
    StudySessionUpdate,
)
from app.schemas.user import UserCreate
from app.services.course_service import CourseService
from app.services.session_service import LearningSessionService
from app.services.user_service import UserService
from app.utils.security import verify_password


def test_user_creation_and_password_hash_hidden_in_api(client: TestClient) -> None:
    """Verify User registration hashes passwords and NEVER exposes password_hash in API responses."""
    response = client.post(
        "/api/v1/users",
        json={
            "email": "student@university.edu",
            "full_name": "Ada Lovelace",
            "password": "StrongPassword123!",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "student@university.edu"
    assert data["full_name"] == "Ada Lovelace"
    assert data["is_active"] is True
    assert "id" in data
    assert "password" not in data
    assert "password_hash" not in data

    # Fetch user via GET and verify password_hash is still never exposed
    get_resp = client.get(f"/api/v1/users/{data['id']}")
    assert get_resp.status_code == 200
    assert "password_hash" not in get_resp.json()

    # Duplicate email returns 409 CONFLICT
    dup_resp = client.post(
        "/api/v1/users",
        json={
            "email": "student@university.edu",
            "full_name": "Duplicate User",
            "password": "AnotherPassword123!",
        },
    )
    assert dup_resp.status_code == 409
    assert dup_resp.json()["error_code"] == "CONFLICT"


def test_course_api_and_user_ownership_enforcement(client: TestClient) -> None:
    """Verify course CRUD operations and strict user ownership enforcement."""
    user1 = client.post(
        "/api/v1/users",
        json={
            "email": "owner@university.edu",
            "full_name": "Owner Student",
            "password": "Password123!",
        },
    ).json()
    user2 = client.post(
        "/api/v1/users",
        json={
            "email": "intruder@university.edu",
            "full_name": "Other Student",
            "password": "Password123!",
        },
    ).json()

    # Create course for user1
    course_resp = client.post(
        "/api/v1/courses",
        json={
            "user_id": user1["id"],
            "title": "Operating Systems",
            "code": "CS-301",
            "description": "Processes, threads, scheduling, and virtual memory.",
        },
    )
    assert course_resp.status_code == 201
    course = course_resp.json()
    assert course["user_id"] == user1["id"]

    # User2 attempting to update or delete user1's course gets 403 FORBIDDEN
    forbidden_patch = client.patch(
        f"/api/v1/courses/{course['id']}?user_id={user2['id']}",
        json={"title": "Hijacked Course"},
    )
    assert forbidden_patch.status_code == 403
    assert forbidden_patch.json()["error_code"] == "FORBIDDEN_OWNERSHIP_VIOLATION"

    forbidden_delete = client.delete(
        f"/api/v1/courses/{course['id']}?user_id={user2['id']}"
    )
    assert forbidden_delete.status_code == 403

    # User1 can update their own course
    ok_patch = client.patch(
        f"/api/v1/courses/{course['id']}?user_id={user1['id']}",
        json={"title": "Advanced Operating Systems"},
    )
    assert ok_patch.status_code == 200
    assert ok_patch.json()["title"] == "Advanced Operating Systems"


def test_complete_domain_models_and_history_preservation(db_session: Session) -> None:
    """Verify all 12 ORM models, relationships, ChunkMetadata without vectors, and attempt/evaluation history."""
    user_svc = UserService(db_session)
    course_svc = CourseService(db_session)
    session_svc = LearningSessionService(db_session)

    # 1. User
    user = user_svc.create_user(
        UserCreate(
            email="alan@cambridge.edu",
            full_name="Alan Turing",
            password="EnigmaPassword99!",
        )
    )
    assert verify_password("EnigmaPassword99!", user.password_hash)

    with pytest.raises(ConflictError):
        user_svc.create_user(
            UserCreate(
                email="alan@cambridge.edu",
                full_name="Duplicate Alan",
                password="EnigmaPassword99!",
            )
        )

    # 2. Course
    course = course_svc.create_course(
        CourseCreate(
            user_id=user.id,
            title="Computability Theory",
            code="CS-401",
            description="Turing machines and decidability.",
        )
    )

    # 3. Document
    doc = course_svc.create_document(
        DocumentCreate(
            user_id=user.id,
            course_id=course.id,
            filename="Lecture_01_Turing_Machines.pdf",
            file_path="storage/uploads/lecture_01.pdf",
            file_size_bytes=204800,
            page_count=18,
        )
    )
    doc = course_svc.update_document(
        doc.id,
        DocumentUpdate(status="READY", chunk_count=1),
        requesting_user_id=user.id,
    )
    assert doc.status == "READY"

    # 4. ChunkMetadata (ensure no embedding column exists in table)
    mapper = inspect(db_session.bind).get_columns("chunk_metadata")  # type: ignore[arg-type]
    column_names = {col["name"] for col in mapper}
    assert "embedding" not in column_names
    assert "chroma_vector_id" in column_names

    chunk = course_svc.create_chunk_metadata(
        ChunkMetadataCreate(
            document_id=doc.id,
            course_id=course.id,
            chroma_vector_id=f"{doc.id}_chunk_0",
            chunk_index=0,
            page_number=3,
            text_content="The Halting Problem is undecidable over Turing machines.",
            char_count=56,
            metadata_json={"section": "Halting Problem"},
        )
    )
    assert chunk.chroma_vector_id == f"{doc.id}_chunk_0"

    # 5. Concept
    concept = course_svc.create_concept(
        ConceptCreate(
            course_id=course.id,
            source_document_id=doc.id,
            title="The Halting Problem",
            summary="Proof by diagonalization that no general algorithm decides halting.",
            difficulty="ADVANCED",
            display_order=1,
            source_pages=[3, 4],
        )
    )

    # 6. StudySession
    study_session = session_svc.create_study_session(
        StudySessionCreate(
            user_id=user.id,
            course_id=course.id,
            current_concept_id=concept.id,
            state="TEACHING",
            context_data={"topic": "Halting Problem"},
        )
    )
    study_session = session_svc.update_study_session(
        study_session.id,
        StudySessionUpdate(state="QUESTIONING"),
        requesting_user_id=user.id,
    )
    assert study_session.state == "QUESTIONING"

    # 7. Activity
    activity = session_svc.create_activity(
        ActivityCreate(
            session_id=study_session.id,
            concept_id=concept.id,
            activity_type="CONCEPTUAL_QUESTION",
            difficulty="ADVANCED",
            prompt_text="Why does assuming a halting decider H lead to a contradiction?",
            rubric_json=[
                {"criterion_id": "c1", "name": "Self-reference construction", "max_points": 50},
                {"criterion_id": "c2", "name": "Contradiction derivation", "max_points": 50},
            ],
            ideal_answer_summary="Construct machine D that does the opposite of H(D, D).",
            source_chunk_ids=[chunk.chroma_vector_id],
        )
    )

    # 8. Attempt (verify multiple attempts are preserved chronologically)
    attempt_1 = session_svc.record_attempt(
        AttemptCreate(
            activity_id=activity.id,
            user_id=user.id,
            response_text="Because infinite loops take forever to check.",
            time_spent_seconds=45,
        )
    )
    attempt_2 = session_svc.record_attempt(
        AttemptCreate(
            activity_id=activity.id,
            user_id=user.id,
            response_text="By constructing a diagonal machine D that loops if H says halt and halts if H says loop.",
            time_spent_seconds=90,
        )
    )
    attempts = session_svc.list_attempts_for_activity(activity.id)
    assert len(attempts) == 2
    assert attempts[0].id == attempt_1.id
    assert attempts[0].attempt_number == 1
    assert attempts[1].id == attempt_2.id
    assert attempts[1].attempt_number == 2

    # 9. Evaluation (verify evaluation history is preserved)
    eval_1 = session_svc.record_evaluation(
        EvaluationCreate(
            attempt_id=attempt_1.id,
            total_score=35.0,
            passed=False,
            criteria_scores_json=[{"criterion_id": "c1", "awarded_points": 15}],
            strengths_json=["Identified infinite loops"],
            gaps_json=["Missed diagonal self-reference proof"],
            overall_feedback="Review the diagonalization construction.",
            evaluator_model="llama3.1:8b",
            coach_action="RETEACH",
        )
    )
    eval_2 = session_svc.record_evaluation(
        EvaluationCreate(
            attempt_id=attempt_2.id,
            total_score=95.0,
            passed=True,
            criteria_scores_json=[
                {"criterion_id": "c1", "awarded_points": 48},
                {"criterion_id": "c2", "awarded_points": 47},
            ],
            strengths_json=["Clear diagonal construction", "Exact contradiction"],
            gaps_json=[],
            overall_feedback="Outstanding proof explanation.",
            evaluator_model="llama3.1:8b",
            coach_action="ADVANCE",
        )
    )
    assert len(session_svc.list_evaluations_for_attempt(attempt_1.id)) == 1
    assert len(session_svc.list_evaluations_for_attempt(attempt_2.id)) == 1

    # 10. LearningEvidence
    evidence = session_svc.record_learning_evidence(
        LearningEvidenceCreate(
            user_id=user.id,
            concept_id=concept.id,
            evaluation_id=eval_2.id,
            evidence_type="ASSESSMENT_SCORE",
            score_delta=60.0,
            observed_score=95.0,
            summary="Mastered diagonalization proof on second attempt.",
        )
    )
    assert evidence.evaluation_id == eval_2.id

    # 11. ConceptProgress
    progress = session_svc.create_or_get_concept_progress(
        ConceptProgressCreate(
            user_id=user.id,
            course_id=course.id,
            concept_id=concept.id,
        )
    )
    progress = session_svc.update_concept_progress(
        progress.id,
        ConceptProgressUpdate(
            mastery_score=82.0,
            mastery_status="MASTERED",
            attempts_count=2,
            correct_attempts_count=1,
            last_score=95.0,
        ),
    )
    assert progress.mastery_status == "MASTERED"
    assert progress.mastery_score == 82.0

    # 12. RevisionTask
    rev_task = session_svc.create_revision_task(
        RevisionTaskCreate(
            user_id=user.id,
            course_id=course.id,
            concept_id=concept.id,
            source_evaluation_id=eval_1.id,
            title="Review Diagonalization Construction",
            reason="Missed self-referential machine construction on Attempt 1.",
            priority="HIGH",
        )
    )
    rev_task = session_svc.update_revision_task(
        rev_task.id,
        RevisionTaskUpdate(status="COMPLETED"),
    )
    assert rev_task.status == "COMPLETED"
    assert rev_task.completed_at is not None

    # Ownership violation check in service layer
    other_user = user_svc.create_user(
        UserCreate(
            email="other@cambridge.edu",
            full_name="Other User",
            password="Password123!",
        )
    )
    with pytest.raises(OwnershipViolationError):
        course_svc.get_course(course.id, requesting_user_id=other_user.id)
