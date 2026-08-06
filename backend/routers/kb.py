"""
知识库路由 — /api/kb/*
"""
import asyncio
import os
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from services import kb_service

router = APIRouter(prefix="/api/kb")
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


async def _save_upload(file: UploadFile) -> str:
    ext = Path(file.filename).suffix
    path = UPLOAD_DIR / f"{uuid.uuid4()}{ext}"
    async with aiofiles.open(path, "wb") as f:
        await f.write(await file.read())
    return str(path)


@router.post("/files")
async def upload_file(file: UploadFile = File(...), category: str = Form("默认")):
    path = await _save_upload(file)
    try:
        result = await asyncio.to_thread(kb_service.add_file, path, file.filename, category)
    finally:
        os.unlink(path)
    return result


@router.get("/files")
async def get_files(category: str = None):
    return await asyncio.to_thread(kb_service.list_files, category)


@router.get("/stats")
async def get_stats():
    return await asyncio.to_thread(kb_service.stats)


@router.post("/search")
async def search_knowledge(
    question: str = Form(...), top_k: int = Form(5),
    category: str | None = Form(None), score_threshold: float = Form(0.32),
):
    return await asyncio.to_thread(
        kb_service.search, question, top_k, category or None, score_threshold,
    )


@router.get("/files/{file_id}/chunks")
async def get_chunks(file_id: str):
    return await asyncio.to_thread(kb_service.list_chunks, file_id)


@router.delete("/files/{file_id}")
async def delete_file(file_id: str):
    await asyncio.to_thread(kb_service.delete_file, file_id)
    return {"status": "deleted"}


@router.post("/chat")
async def chat(question: str = Form(...)):
    def gen():
        for token in kb_service.query_stream(question):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
