"""Bounded and structurally validated image upload handling."""
from __future__ import annotations

import uuid
from pathlib import Path

import aiofiles
from fastapi import HTTPException, UploadFile

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "GIF", "BMP", "TIFF"}


async def save_image_upload(file: UploadFile, upload_dir: Path) -> str:
    declared = (file.content_type or "").lower()
    if declared and declared not in {"application/octet-stream"} and not declared.startswith("image/"):
        raise HTTPException(status_code=415, detail="仅支持图片文件")
    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / f"{uuid.uuid4()}.upload"
    total = 0
    valid = False
    try:
        async with aiofiles.open(path, "wb") as target:
            while True:
                chunk = await file.read(UPLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="图片大小不能超过 12 MB")
                await target.write(chunk)
        if total == 0:
            raise HTTPException(status_code=422, detail="图片内容为空")
        from PIL import Image

        with Image.open(path) as image:
            image.verify()
            if image.format not in ALLOWED_IMAGE_FORMATS:
                raise HTTPException(status_code=415, detail="图片格式不受支持")
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise HTTPException(status_code=413, detail="图片像素数量超过安全上限")
        valid = True
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=415, detail="图片内容无效") from exc
    finally:
        if path.exists() and not valid:
            path.unlink(missing_ok=True)
        await file.close()
    return str(path)
