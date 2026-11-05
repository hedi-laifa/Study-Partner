"""Course CRUD, Document Upload, Re-indexing, and Grounded AI Tutor Ask API routes."""
import uuid

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.db.session import get_db
from app.models.course import Course
from app.retrieval.retriever import RetrievalService
from app.schemas.course import (
    ConceptCreate,
    ConceptRead,
    CourseCreate,
    CourseRead,
    CourseUpdate,
    DocumentRead,
)
from app.schemas.session import InteractiveSessionDetail
from app.schemas.tutor import TutorAskRequest, TutorAskResponse
from app.services.course_service import CourseService
from app.services.ingestion_service import IngestionService
from app.services.study_session_service import StudySessionService
from app.tutor.service import TutorService

router = APIRouter(prefix="/courses", tags=["Courses"])


def _serialize_course(course: Course) -> CourseRead:
    return CourseRead(
        id=course.id,
        user_id=course.user_id,
        title=course.title,
        code=course.code,
        description=course.description,
        document_count=len(course.documents) if course.documents is not None else 0,
        created_at=course.created_at,
        updated_at=course.updated_at,
    )


@router.post(
    "",
    response_model=CourseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new course",
)
def create_course(payload: CourseCreate, db: Session = Depends(get_db)) -> CourseRead:
    """Create a course owned by a user."""
    service = CourseService(db)
    course = service.create_course(payload)
    return _serialize_course(course)


@router.get(
    "",
    response_model=list[CourseRead],
    summary="List courses for a user",
)
def list_courses(
    user_id: uuid.UUID = Query(..., description="Owner user UUID"),
    db: Session = Depends(get_db),
) -> list[CourseRead]:
    """List all courses belonging to the specified user."""
    service = CourseService(db)
    courses = service.list_courses_for_user(user_id)
    return [_serialize_course(c) for c in courses]


@router.get(
    "/{course_id}",
    response_model=CourseRead,
    summary="Get course by ID",
)
def get_course(
    course_id: uuid.UUID,
    user_id: uuid.UUID | None = Query(
        default=None, description="Optional owner user UUID check"
    ),
    db: Session = Depends(get_db),
) -> CourseRead:
    """Retrieve a course by UUID, enforcing ownership when user_id is supplied."""
    service = CourseService(db)
    course = service.get_course(course_id, requesting_user_id=user_id)
    return _serialize_course(course)


@router.patch(
    "/{course_id}",
    response_model=CourseRead,
    summary="Update course",
)
def update_course(
    course_id: uuid.UUID,
    payload: CourseUpdate,
    user_id: uuid.UUID | None = Query(
        default=None, description="Optional owner user UUID check"
    ),
    db: Session = Depends(get_db),
) -> CourseRead:
    """Update course details after verifying ownership."""
    service = CourseService(db)
    course = service.update_course(course_id, payload, requesting_user_id=user_id)
    return _serialize_course(course)


@router.delete(
    "/{course_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete course",
)
def delete_course(
    course_id: uuid.UUID,
    user_id: uuid.UUID | None = Query(
        default=None, description="Optional owner user UUID check"
    ),
    db: Session = Depends(get_db),
) -> Response:
    """Delete a course after verifying ownership."""
    service = CourseService(db)
    service.delete_course(course_id, requesting_user_id=user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{course_id}/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a PDF document into a course",
)
async def upload_course_document(
    course_id: uuid.UUID,
    file: UploadFile = File(..., description="Course PDF file to upload and ingest"),
    user_id: uuid.UUID | None = Query(
        default=None, description="Owner user UUID (query parameter)"
    ),
    form_user_id: uuid.UUID | None = Form(
        default=None, alias="user_id", description="Owner user UUID (form field)"
    ),
    db: Session = Depends(get_db),
) -> DocumentRead:
    """Validate, store, extract text, chunk, and index an uploaded course PDF."""
    resolved_user_id = user_id or form_user_id
    if resolved_user_id is None:
        raise AppException(
            detail="user_id is required to upload a document.",
            error_code="MISSING_USER_ID",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    file_bytes = await file.read()
    ingestion_service = IngestionService(db)
    document = ingestion_service.ingest_pdf(
        course_id=course_id,
        user_id=resolved_user_id,
        filename=file.filename,
        content_type=file.content_type,
        file_bytes=file_bytes,
    )
    return DocumentRead.model_validate(document)


@router.get(
    "/{course_id}/documents",
    response_model=list[DocumentRead],
    summary="List documents uploaded to a course",
)
def list_course_documents(
    course_id: uuid.UUID,
    user_id: uuid.UUID | None = Query(
        default=None, description="Owner user UUID check"
    ),
    db: Session = Depends(get_db),
) -> list[DocumentRead]:
    """List all documents and processing statuses for a course."""
    ingestion_service = IngestionService(db)
    documents = ingestion_service.list_course_documents(
        course_id, requesting_user_id=user_id
    )
    return [DocumentRead.model_validate(d) for d in documents]


@router.post(
    "/{course_id}/reindex",
    summary="Re-index all READY document chunks for a course in ChromaDB",
)
def reindex_course_chunks(
    course_id: uuid.UUID,
    user_id: uuid.UUID | None = Query(
        default=None, description="Owner user UUID check"
    ),
    db: Session = Depends(get_db),
) -> dict[str, int | str]:
    """Rebuild ChromaDB vector embeddings for all READY documents in the course."""
    retrieval_service = RetrievalService(db)
    indexed_count = retrieval_service.reindex_course(
        course_id, requesting_user_id=user_id
    )
    return {
        "course_id": str(course_id),
        "indexed_chunks": indexed_count,
        "status": "reindexed",
    }


@router.post(
    "/{course_id}/ask",
    response_model=TutorAskResponse,
    summary="Ask the AI Tutor a question grounded in uploaded course PDFs",
)
def ask_course_tutor(
    course_id: uuid.UUID,
    payload: TutorAskRequest,
    user_id: uuid.UUID | None = Query(
        default=None, description="Optional owner user UUID check"
    ),
    db: Session = Depends(get_db),
) -> TutorAskResponse:
    """Retrieve top-k relevant course passages and generate a grounded Tutor explanation with citations."""
    tutor_service = TutorService(db)
    return tutor_service.ask_question(
        course_id=course_id,
        payload=payload,
        requesting_user_id=user_id or payload.user_id,
    )


@router.get(
    "/{course_id}/concepts",
    response_model=list[ConceptRead],
    summary="List or auto-extract concepts for a course",
)
def list_course_concepts(
    course_id: uuid.UUID,
    user_id: uuid.UUID | None = Query(
        default=None, description="Optional owner user UUID check"
    ),
    db: Session = Depends(get_db),
) -> list[ConceptRead]:
    """List concepts for a course, auto-extracting concepts from READY PDF sections when needed."""
    session_service = StudySessionService(db)
    concepts = session_service.list_or_extract_course_concepts(
        course_id=course_id, requesting_user_id=user_id
    )
    return [ConceptRead.model_validate(c) for c in concepts]


@router.post(
    "/{course_id}/concepts",
    response_model=ConceptRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a concept in a course",
)
def create_course_concept(
    course_id: uuid.UUID,
    payload: ConceptCreate,
    user_id: uuid.UUID | None = Query(
        default=None, description="Optional owner user UUID check"
    ),
    db: Session = Depends(get_db),
) -> ConceptRead:
    """Create a custom academic concept within a course."""
    course_service = CourseService(db)
    course_service.get_course(course_id, requesting_user_id=user_id)
    if payload.course_id != course_id:
        payload = payload.model_copy(update={"course_id": course_id})
    concept = course_service.create_concept(payload)
    return ConceptRead.model_validate(concept)


@router.get(
    "/{course_id}/sessions",
    response_model=list[InteractiveSessionDetail],
    summary="List interactive study sessions for a course",
)
def list_course_sessions(
    course_id: uuid.UUID,
    user_id: uuid.UUID | None = Query(
        default=None, description="Optional owner user UUID check"
    ),
    db: Session = Depends(get_db),
) -> list[InteractiveSessionDetail]:
    """List all interactive study sessions (active and completed) for a course."""
    session_service = StudySessionService(db)
    return session_service.list_course_sessions(
        course_id=course_id, requesting_user_id=user_id
    )

