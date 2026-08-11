"""
检测路由 — /api/detect/*
"""
import asyncio
import io
import json
import os
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse

from services import audit_log_service, audit_watermark_service, deepfake_service, face_service, invisible_watermark_service, mllm_service, provenance_service, rag_service, upload_service

router = APIRouter(prefix="/api/detect")
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


async def _save_upload(file: UploadFile) -> str:
    return await upload_service.save_image_upload(file, UPLOAD_DIR)


def _record_content_safety(result: dict) -> None:
    verdict = result.get("verdict", "review")
    categories = result.get("categories") or []
    first_code = categories[0].get("code") if categories else result.get("error_code")
    audit_log_service.record_safe(
        event_type="image.content_safety",
        module="image_content_safety",
        action="analyze",
        severity="high" if verdict == "unsafe" else "warning" if verdict == "review" else "info",
        outcome="blocked" if verdict == "unsafe" else "review" if verdict == "review" else "allowed",
        summary=f"图片内容安全审核：{verdict}",
        risk_code=first_code,
        risk_score=result.get("risk_score"),
        content_hash=result.get("content_hash"),
        metadata={
            "category_codes": [item.get("code") for item in categories if item.get("code")],
            "model": result.get("model"),
            "policy_version": result.get("policy_version"),
            "status": result.get("status"),
        },
    )


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
    """Compatibility wrapper for existing route, report and v1 callers."""
    return face_service.inspect(path)


@router.post("/face")
async def inspect_face(image: UploadFile = File(...)):
    path = await _save_upload(image)
    try:
        return await asyncio.to_thread(_inspect_faces, path)
    finally:
        os.unlink(path)


@router.post("/provenance")
async def verify_provenance(image: UploadFile = File(...)):
    """Verify local/source provenance without retaining the uploaded image."""
    path = await _save_upload(image)
    try:
        result = await asyncio.to_thread(provenance_service.verify, path)
        audit_log_service.record_safe(
            event_type="image.provenance_verify", module="provenance", action="verify",
            severity="warning" if result["overall_state"] in {"invalid_or_tampered", "inconclusive"} else "info",
            outcome="success", summary="图片来源证据验证", content_hash=result["content_hash"],
            metadata={"overall_state": result["overall_state"], "format": result["metadata"].get("format"),
                      "marker_status": result["source_evidence"]["local_marker"]["status"]},
        )
        return result
    except provenance_service.ProvenanceError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        if os.path.exists(path):
            os.unlink(path)


@router.post("/audit-watermark/embed")
async def embed_audit_watermark(image: UploadFile = File(...), payload: str = Form(...)):
    path = await _save_upload(image)
    try:
        try:
            body = json.loads(payload)
        except json.JSONDecodeError as exc:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail="payload_json_invalid") from exc
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "audit-copy.png"
            artifact = await asyncio.to_thread(audit_watermark_service.embed, path, output, body)
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
                bundle.write(output, "audit-copy.png")
                bundle.writestr("audit-sidecar.json", json.dumps(artifact["sidecar"], ensure_ascii=False))
            audit_log_service.record_safe(
                event_type="image.audit_watermark_embed", module="provenance", action="embed",
                outcome="success", summary="生成可逆审计副本",
                metadata={"event_id": artifact["payload"].get("event_id")},
            )
            return Response(
                content=archive.getvalue(), media_type="application/zip",
                headers={"Content-Disposition": 'attachment; filename="audit-watermark-artifact.zip"', "Cache-Control": "no-store"},
            )
    except audit_watermark_service.AuditWatermarkError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        if os.path.exists(path):
            os.unlink(path)


@router.post("/invisible-watermark/embed")
async def embed_invisible_watermark(image: UploadFile = File(...), payload: str = Form(...)):
    path = await _save_upload(image)
    try:
        try:
            body = json.loads(payload)
        except json.JSONDecodeError as exc:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail="payload_json_invalid") from exc
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "platform-watermarked.png"
            artifact = await asyncio.to_thread(invisible_watermark_service.embed, path, output, body)
            audit_log_service.record_safe(
                event_type="image.invisible_watermark_embed",
                module="provenance",
                action="embed",
                outcome="success",
                summary="生成平台签名隐形水印图片",
                metadata={"content_id": artifact["payload"].get("content_id")},
            )
            return Response(
                content=output.read_bytes(),
                media_type="image/png",
                headers={
                    "Content-Disposition": 'attachment; filename="platform-watermarked.png"',
                    "Cache-Control": "no-store",
                },
            )
    except invisible_watermark_service.InvisibleWatermarkError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        if os.path.exists(path):
            os.unlink(path)


@router.post("/full")
async def full_audit(image: UploadFile = File(None), text: str = Form(None),
                     modules: str = Form("deepfake,mllm,rag")):
    """SSE 流式全量审计报告"""
    mod_set = set(modules.split(","))

    async def event_stream():
        path = None
        report_results: dict[str, object] = {}
        try:
            if image:
                path = await _save_upload(image)
                face = await asyncio.to_thread(_inspect_faces, path)
                report_results["face"] = face
                has_face = face.get("face_detected") is not False
                if "face" in mod_set or "deepfake" in mod_set:
                    yield _sse("face", face)

                if "deepfake" in mod_set:
                    yield _sse("step", {"step": "deepfake", "status": "running"})
                    if has_face:
                        df = await asyncio.to_thread(deepfake_service.detect, path)
                    else:
                        df = {"score": 0, "label": "skipped", "confidence": 0, "reason": "no face detected"}
                    report_results["deepfake"] = df
                    yield _sse("deepfake", df)

                if "mllm" in mod_set:
                    yield _sse("step", {"step": "mllm", "status": "running"})
                    ml = await asyncio.to_thread(mllm_service.analyze, path)
                    report_results["mllm"] = ml
                    yield _sse("mllm", ml)

                if "content_safety" in mod_set:
                    yield _sse("step", {"step": "content_safety", "status": "running"})
                    content_safety = await asyncio.to_thread(mllm_service.analyze_content_safety, path)
                    _record_content_safety(content_safety)
                    report_results["content_safety"] = content_safety
                    yield _sse("content_safety", content_safety)

            if text and "rag" in mod_set:
                yield _sse("step", {"step": "rag", "status": "running"})
                rag = await asyncio.to_thread(rag_service.check_content, text)
                report_results["rag"] = rag
                yield _sse("rag", rag)

            yield _sse("step", {"step": "report", "status": "running"})
            report = await _finalize_report({
                **report_results,
                **({"filename": image.filename} if image and image.filename else {}),
                **({"text": text} if text else {}),
            })
            yield _sse("done", {"status": "completed", "report_id": report["id"]})
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
    prompt = f"""你是一个多模态真实性与内容安全审计专家。请根据以下检测结果生成一份综合分析报告（Markdown格式）：

检测结果：
{json.dumps(report, ensure_ascii=False, indent=2)}

要求：
1. 用 Markdown 格式输出，包含标题、列表、加粗等
2. 分为"检测概览"、"详细分析"、"风险评估"、"建议措施"四个部分
3. 语言简洁专业，适合技术报告
4. 将真实性与来源结论、内容安全结论分开说明，不把 AI 生成等同于内容违规
5. 如果有 Deepfake/MLLM/C2PA 结果，分析真实性、篡改与来源证据
6. 如果有 RAG 或 content_safety 结果，说明内容安全类别、风险分数和人工复核要求
"""
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
    )
    return resp.choices[0].message.content or "生成失败"


async def _finalize_report(payload: dict) -> dict:
    """Persist one report from results already produced by the active audit run."""
    report = {
        "id": str(payload.get("id") or uuid.uuid4()),
        "created_at": payload.get("created_at") or datetime.now().isoformat(),
        **{key: value for key, value in payload.items() if key not in {"id", "created_at", "summary"}},
    }
    report["summary"] = await asyncio.to_thread(_gen_summary, report)
    report_path = REPORTS_DIR / f"{report['id']}.json"
    await asyncio.to_thread(
        report_path.write_text,
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


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
            report["content_safety"] = await asyncio.to_thread(mllm_service.analyze_content_safety, path)
        if text:
            report["text"] = text
            report["rag"] = await asyncio.to_thread(rag_service.check_content, text)
    finally:
        if path and os.path.exists(path):
            os.unlink(path)

    report = await _finalize_report(report)
    return {"report_id": report["id"], "report": report}


@router.post("/image-content")
async def analyze_image_content(image: UploadFile = File(...)):
    """OCR + RAG + 真实性检测 + 视觉内容安全综合分析"""
    from services.ocr_service import analyze_image_content as _analyze
    path = await _save_upload(image)
    try:
        result = await asyncio.to_thread(_analyze, path)
        _record_content_safety(result["content_safety"])
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
                "content_safety_verdict": r.get("content_safety", {}).get("verdict"),
                "content_safety_risk": r.get("content_safety", {}).get("risk_score"),
                "content_safety_categories": [
                    item.get("code") for item in r.get("content_safety", {}).get("categories", [])
                    if item.get("code")
                ],
            })
        except Exception:
            pass
    total = len(reports)
    fake_count = sum(
        1 for r in reports
        if r["deepfake_label"] == "fake" or r["mllm_verdict"] == "fake"
    )
    risk_count = sum(
        1 for r in reports
        if r["rag_safe"] is False or r["content_safety_verdict"] in {"review", "unsafe"}
    )
    clear_count = sum(
        1 for r in reports
        if r["deepfake_label"] != "fake"
        and r["mllm_verdict"] != "fake"
        and r["rag_safe"] is not False
        and r["content_safety_verdict"] not in {"review", "unsafe"}
        and any(value is not None for value in (
            r["deepfake_label"], r["mllm_verdict"], r["rag_safe"], r["content_safety_verdict"]
        ))
    )
    return {
        "total": total,
        "fake_count": fake_count,
        "risk_count": risk_count,
        "clear_count": clear_count,
        "reports": reports,
    }


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
    lines = [
        "# 多模态内容安全与真实性审计报告\n",
        f"**报告ID**: {report_id}  \n",
        f"**生成时间**: {report.get('created_at','')}\n\n---\n",
    ]
    if report.get("filename"):
        lines.append(f"**检测文件**: {report['filename']}\n\n")
    if report.get("deepfake"):
        df = report["deepfake"]
        lines.append(f"## 真实性与来源\n### Deepfake 检测\n- 结果: **{df.get('label')}**\n- 伪造得分: {df.get('score')}\n- 置信度: {df.get('confidence')}\n\n")
    if report.get("mllm"):
        mllm = report["mllm"]
        lines.append(f"### MLLM 真实性分析\n- 结果: **{mllm.get('verdict')}**\n- 置信度: {mllm.get('confidence')}\n\n")
    if report.get("content_safety"):
        content = report["content_safety"]
        lines.append(
            "## 视觉内容安全\n"
            f"- 处置: **{content.get('verdict')}**\n"
            f"- 综合风险: {content.get('risk_score')}\n"
            f"- 模型: {content.get('model')}\n"
        )
        categories = content.get("categories") or []
        if categories:
            lines.append("- 命中类别:\n")
            for item in categories:
                label = item.get("label") or item.get("code") or "unknown"
                lines.append(f"  - {label}: {item.get('confidence')} ({item.get('severity')})\n")
        lines.append("\n")
    if report.get("rag"):
        rag = report["rag"]
        lines.append(f"## 文本与红线内容安全\n- 安全: **{'是' if rag.get('safe') else '否'}**\n- 风险等级: {rag.get('risk_level')}\n\n")
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
