"""
检测路由 — /api/detect/*
"""
import asyncio
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import aiofiles
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from services import deepfake_service, mllm_service, rag_service

router = APIRouter(prefix="/api/detect")
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


async def _save_upload(file: UploadFile) -> str:
    ext = Path(file.filename).suffix
    path = UPLOAD_DIR / f"{uuid.uuid4()}{ext}"
    async with aiofiles.open(path, "wb") as f:
        await f.write(await file.read())
    return str(path)


@router.post("/deepfake")
async def detect_deepfake(image: UploadFile = File(...)):
    path = await _save_upload(image)
    try:
        result = await asyncio.to_thread(deepfake_service.detect, path)
    finally:
        os.unlink(path)
    return result


@router.post("/mllm")
async def detect_mllm(image: UploadFile = File(...)):
    path = await _save_upload(image)
    try:
        result = await asyncio.to_thread(mllm_service.analyze, path)
    finally:
        os.unlink(path)
    return result


@router.post("/content")
async def check_content(text: str = Form(...)):
    result = await asyncio.to_thread(rag_service.check_content, text)
    return result


def _inspect_faces(path: str) -> dict:
    """Return non-identifying face and image-quality evidence for audit reports."""
    try:
        import cv2
        img = cv2.imread(path)
        if img is None:
            return {"status": "unavailable", "face_detected": False, "face_count": 0, "reason": "image_decode_failed"}
        height, width = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        xml = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        if not Path(xml).exists():
            return {"status": "unavailable", "face_detected": None, "face_count": None, "reason": "face_detector_missing", "image_width": width, "image_height": height}
        cascade = cv2.CascadeClassifier(xml)
        min_size = max(24, min(width, height) // 12)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(min_size, min_size))
        boxes = [{"x": int(x), "y": int(y), "width": int(w), "height": int(h)} for x, y, w, h in faces]
        largest_ratio = max((w * h) / (width * height) for _, _, w, h in faces) if len(faces) else 0.0
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness = float(gray.mean())
        quality_flags = []
        if min(width, height) < 480:
            quality_flags.append("low_resolution")
        if sharpness < 80:
            quality_flags.append("blurred")
        if brightness < 45:
            quality_flags.append("underexposed")
        elif brightness > 215:
            quality_flags.append("overexposed")
        return {
            "status": "detected" if len(faces) else "not_detected",
            "face_detected": bool(len(faces)),
            "face_count": len(faces),
            "boxes": boxes,
            "image_width": width,
            "image_height": height,
            "largest_face_ratio": round(largest_ratio, 4),
            "sharpness": round(sharpness, 1),
            "brightness": round(brightness, 1),
            "quality": "good" if not quality_flags else "review",
            "quality_flags": quality_flags,
            "detector": "OpenCV Haar Cascade",
        }
    except Exception as exc:
        return {"status": "unavailable", "face_detected": None, "face_count": None, "reason": type(exc).__name__}


@router.post("/face")
async def inspect_face(image: UploadFile = File(...)):
    path = await _save_upload(image)
    try:
        return await asyncio.to_thread(_inspect_faces, path)
    finally:
        os.unlink(path)


@router.post("/full")
async def full_audit(image: UploadFile = File(None), text: str = Form(None),
                     modules: str = Form("deepfake,mllm,rag")):
    """SSE 流式全量审计报告"""
    mod_set = set(modules.split(","))

    async def event_stream():
        path = None
        try:
            if image:
                path = await _save_upload(image)
                face = await asyncio.to_thread(_inspect_faces, path)
                has_face = face.get("face_detected") is not False
                if "face" in mod_set or "deepfake" in mod_set:
                    yield _sse("face", face)

                if "deepfake" in mod_set:
                    yield _sse("step", {"step": "deepfake", "status": "running"})
                    if has_face:
                        df = await asyncio.to_thread(deepfake_service.detect, path)
                    else:
                        df = {"score": 0, "label": "skipped", "confidence": 0, "reason": "no face detected"}
                    yield _sse("deepfake", df)

                if "mllm" in mod_set:
                    yield _sse("step", {"step": "mllm", "status": "running"})
                    ml = await asyncio.to_thread(mllm_service.analyze, path)
                    yield _sse("mllm", ml)

            if text and "rag" in mod_set:
                yield _sse("step", {"step": "rag", "status": "running"})
                rag = await asyncio.to_thread(rag_service.check_content, text)
                yield _sse("rag", rag)

            yield _sse("done", {"status": "completed"})
        finally:
            if path and os.path.exists(path):
                os.unlink(path)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)


def _gen_summary(report: dict) -> str:
    """调用 MLLM 生成 Markdown 格式的综合分析报告"""
    from openai import OpenAI
    from config import MLLM_API_KEY, MLLM_BASE_URL, MLLM_MODEL, PROXY_URL
    import httpx

    try:
        if PROXY_URL:
            with httpx.Client(proxy=PROXY_URL, timeout=60) as http_client:
                client = OpenAI(api_key=MLLM_API_KEY, base_url=MLLM_BASE_URL, http_client=http_client)
                return _call_summary(client, MLLM_MODEL, report)
        else:
            client = OpenAI(api_key=MLLM_API_KEY, base_url=MLLM_BASE_URL)
            return _call_summary(client, MLLM_MODEL, report)
    except Exception as e:
        return f"综合分析生成失败：{e}"


def _call_summary(client, model: str, report: dict) -> str:
    prompt = f"""你是一个AIGC内容安全审计专家。请根据以下检测结果生成一份综合分析报告（Markdown格式）：

检测结果：
{json.dumps(report, ensure_ascii=False, indent=2)}

要求：
1. 用 Markdown 格式输出，包含标题、列表、加粗等
2. 分为"检测概览"、"详细分析"、"风险评估"、"建议措施"四个部分
3. 语言简洁专业，适合技术报告
4. 如果有 Deepfake/MLLM 结果，重点分析伪造证据
5. 如果有 RAG 结果，说明内容安全风险
"""
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
    )
    return resp.choices[0].message.content or "生成失败"


@router.post("/report")
async def save_report(
    image: UploadFile = File(None),
    text: str = Form(None),
):
    """运行全量检测并保存 JSON 报告，返回报告 ID"""
    report = {"id": str(uuid.uuid4()), "created_at": datetime.now().isoformat()}
    path = None
    try:
        if image:
            path = await _save_upload(image)
            report["filename"] = image.filename
            report["face"] = await asyncio.to_thread(_inspect_faces, path)
            if report["face"].get("face_detected") is False:
                report["deepfake"] = {"score": 0, "label": "skipped", "confidence": 0, "reason": "no face detected"}
            else:
                report["deepfake"] = await asyncio.to_thread(deepfake_service.detect, path)
            report["mllm"] = await asyncio.to_thread(mllm_service.analyze, path)
        if text:
            report["text"] = text
            report["rag"] = await asyncio.to_thread(rag_service.check_content, text)
    finally:
        if path and os.path.exists(path):
            os.unlink(path)

    report_path = REPORTS_DIR / f"{report['id']}.json"

    # MLLM 综合分析（Markdown 格式）
    report["summary"] = await asyncio.to_thread(_gen_summary, report)

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"report_id": report["id"], "report": report}


@router.post("/image-content")
async def analyze_image_content(image: UploadFile = File(...)):
    """OCR + RAG + MLLM 综合图片内容分析"""
    from services.ocr_service import analyze_image_content as _analyze
    path = await _save_upload(image)
    try:
        result = await asyncio.to_thread(_analyze, path)
    finally:
        os.unlink(path)
    return result


@router.post("/batch")
async def batch_check(texts: list[str]):
    """并发批量 RAG 审核"""
    results = await asyncio.gather(*[
        asyncio.to_thread(rag_service.check_content, t) for t in texts
    ])
    return [{"text": t, **r} for t, r in zip(texts, results)]


@router.get("/history")
async def get_history():
    """返回所有报告摘要 + 统计"""
    reports = []
    for p in sorted(REPORTS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
            reports.append({
                "id": r["id"],
                "created_at": r.get("created_at"),
                "filename": r.get("filename"),
                "face_count": r.get("face", {}).get("face_count"),
                "deepfake_label": r.get("deepfake", {}).get("label"),
                "deepfake_score": r.get("deepfake", {}).get("score"),
                "mllm_verdict": r.get("mllm", {}).get("verdict"),
                "rag_safe": r.get("rag", {}).get("safe"),
                "rag_risk": r.get("rag", {}).get("risk_level"),
            })
        except Exception:
            pass
    total = len(reports)
    fake_count = sum(1 for r in reports if r["deepfake_label"] == "fake")
    risk_count = sum(1 for r in reports if r["rag_safe"] is False)
    return {"total": total, "fake_count": fake_count, "risk_count": risk_count, "reports": reports}


@router.get("/report/{report_id}")
async def get_report(report_id: str):
    p = REPORTS_DIR / f"{report_id}.json"
    if not p.exists():
        from fastapi import HTTPException
        raise HTTPException(404, "Report not found")
    return json.loads(p.read_text(encoding="utf-8"))


@router.get("/report/{report_id}/download/md")
async def download_report_md(report_id: str):
    p = REPORTS_DIR / f"{report_id}.json"
    if not p.exists():
        from fastapi import HTTPException
        raise HTTPException(404, "Report not found")
    report = json.loads(p.read_text(encoding="utf-8"))
    summary = report.get("summary", "")
    # 生成完整 Markdown 文档
    lines = [f"# AIGC 内容安全审计报告\n", f"**报告ID**: {report_id}  \n",
             f"**生成时间**: {report.get('created_at','')}\n\n---\n"]
    if report.get("filename"):
        lines.append(f"**检测文件**: {report['filename']}\n\n")
    if report.get("deepfake"):
        df = report["deepfake"]
        lines.append(f"## Deepfake 检测\n- 结果: **{df.get('label')}**\n- 伪造得分: {df.get('score')}\n- 置信度: {df.get('confidence')}\n\n")
    if report.get("rag"):
        rag = report["rag"]
        lines.append(f"## RAG 内容审核\n- 安全: **{'是' if rag.get('safe') else '否'}**\n- 风险等级: {rag.get('risk_level')}\n\n")
    if summary:
        lines.append(f"---\n\n{summary}\n")
    md_content = "".join(lines)
    from fastapi.responses import Response
    return Response(content=md_content.encode("utf-8"), media_type="text/markdown",
                    headers={"Content-Disposition": f"attachment; filename=report_{report_id}.md"})


@router.get("/report/{report_id}/download")
async def download_report_json(report_id: str):
    p = REPORTS_DIR / f"{report_id}.json"
    if not p.exists():
        from fastapi import HTTPException
        raise HTTPException(404, "Report not found")
    return FileResponse(str(p), media_type="application/json",
                        filename=f"report_{report_id}.json")
