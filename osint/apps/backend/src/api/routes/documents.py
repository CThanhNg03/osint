"""Document management endpoints."""

from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse
from apps.backend.src.api.schemas import documents as schemas
from apps.backend.src.infrastructure.persistence.database import get_db
from apps.backend.src.usecases import upload_document, list_documents, get_document, delete_document, extract_document_kg
from apps.backend.src.common import errors

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=schemas.DocumentOut)
async def upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    result = upload_document.execute(db, file.filename, content)
    return schemas.DocumentOut(**result)


@router.get("/", response_model=list[schemas.DocumentListItem])
async def list_all(db: Session = Depends(get_db)):
    return list_documents.execute(db)


@router.get("/{document_id}")
async def download(document_id: int, db: Session = Depends(get_db)):
    try:
        doc = get_document.execute(db, document_id)
    except Exception as exc:  # noqa: BLE001
        raise errors.http_error_from_exc(exc)
    return FileResponse(doc["path"], filename=doc["filename"]) if doc else {}


@router.delete("/{document_id}")
async def remove(document_id: int, db: Session = Depends(get_db)):
    delete_document.execute(db, document_id)
    return {"status": "deleted"}


@router.post("/{document_id}/extract-kg")
async def extract(document_id: int, db: Session = Depends(get_db)):
    return extract_document_kg.execute(db, document_id)
