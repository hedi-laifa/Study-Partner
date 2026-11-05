"""Document metadata, chunks inspection, and deletion API routes."""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import EntityNotFoundError
from app.db.session import get_db
from app.schemas.course import ChunkMetadataRead, DocumentRead
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get(
    "/{document_id}",
    response_model=DocumentRead,
    summary="Get document metadata and processing status",
)
def get_document(
    document_id: uuid.UUID,
    user_id: uuid.UUID | None = Query(
        default=None, description="Owner user UUID check"
    ),
    db: Session = Depends(get_db),
) -> DocumentRead:
    """Retrieve document metadata, status, and extraction warnings."""
    service = IngestionService(db)
    document = service.get_document(document_id, requesting_user_id=user_id)
    return DocumentRead.model_validate(document)


@router.get(
    "/{document_id}/chunks",
    response_model=list[ChunkMetadataRead],
    summary="List extracted chunks for a document",
)
def list_document_chunks(
    document_id: uuid.UUID,
    user_id: uuid.UUID | None = Query(
        default=None, description="Owner user UUID check"
    ),
    db: Session = Depends(get_db),
) -> list[ChunkMetadataRead]:
    """Retrieve all extracted text chunks and page-range metadata for a document."""
    service = IngestionService(db)
    chunks = service.list_document_chunks(document_id, requesting_user_id=user_id)
    return [ChunkMetadataRead.model_validate(c) for c in chunks]


@router.get(
    "/{document_id}/file",
    summary="Download the original stored PDF (owner only) for in-app source preview",
    response_class=FileResponse,
)
def get_document_file(
    document_id: uuid.UUID,
    user_id: uuid.UUID | None = Query(
        default=None, description="Owner user UUID check"
    ),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Stream the original PDF after verifying ownership and that the path lies in upload storage."""
    service = IngestionService(db)
    document = service.get_document(document_id, requesting_user_id=user_id)
    path = Path(document.file_path).resolve()
    root = Path(settings.UPLOAD_STORAGE_DIR).resolve()
    if root not in path.parents or not path.is_file():
        raise EntityNotFoundError("Stored PDF file", document_id)
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline", "X-Content-Type-Options": "nosniff"},
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document and its chunks",
)
def delete_document(
    document_id: uuid.UUID,
    user_id: uuid.UUID | None = Query(
        default=None, description="Owner user UUID check"
    ),
    db: Session = Depends(get_db),
) -> Response:
    """Delete a document, its stored PDF file, and its associated ChunkMetadata records."""
    service = IngestionService(db)
    service.delete_document(document_id, requesting_user_id=user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
