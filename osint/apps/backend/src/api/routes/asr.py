"""ASR endpoints wiring to transcription use case."""

from fastapi import APIRouter, UploadFile, File
from apps.backend.src.api.schemas import asr as schemas
from apps.backend.src.usecases import transcribe_audio

router = APIRouter(prefix="/asr", tags=["asr"])


@router.post("/transcribe", response_model=schemas.TranscriptionResponse)
async def transcribe(file: UploadFile = File(...)):
    content = await file.read()
    result = transcribe_audio.execute(content)
    return schemas.TranscriptionResponse(**result)


@router.get("/status")
async def status():
    return {"status": "ok"}


@router.get("/config")
async def config():
    return {"provider": "stub"}
