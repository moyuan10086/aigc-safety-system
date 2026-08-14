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
from PIL import Image, ImageOps

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse

from services import audit_log_service, audit_watermark_service, auth_service, deepfake_service, face_service, invisible_watermark_service, mllm_service, ocr_service, provenance_service, rag_service, upload_service

router = APIRouter(prefix="/api/detect")
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
_BACKGROUND_TASKS: set[asyncio.Task] = set()


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


@router.post("/ocr")
async def recognize_image_text(image: UploadFile = File(...)):
    """Extract editable text from an uploaded image without retaining it."""
    path = await _save_upload(image)
    try:
        return await asyncio.to_thread(ocr_service.ocr_image_result, path)
    finally:
        if os.path.exists(path):
            os.unlink(path)


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
async def verify_provenance(image: UploadFile = File(...), save_report: bool = Form(False)):
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
        if save_report:
            report = await _finalize_report({
                "filename": image.filename,
                "requested_modules": ["provenance"],
                "provenance": result,
                "_thumbnail_source": path,
            })
            result = {**result, "report_id": report["id"]}
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
                for index, share in enumerate(artifact.get("shares", []), 1):
                    bundle.writestr(f"key-share-{index}.txt", share)
                if artifact.get("shares"):
                    bundle.writestr("README.txt", "门限审计证据包（2-of-3）\n\n审计信息使用 AES-256-GCM 加密，密钥拆为 3 份，任意 2 份可恢复。\n请将 key-share 文件交由不同人员保管。核验时提供 audit-copy.png、audit-sidecar.json 和任意 2 份分片。\n单独图片、旁证或 1 份分片不能恢复审计信息。\n")
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


@router.post("/audit-watermark/decode-archive")
async def decode_audit_watermark_archive(archive: UploadFile = File(...)):
    from fastapi import HTTPException

    suffix = Path(archive.filename or "").suffix.lower()
    if suffix != ".zip":
        raise HTTPException(status_code=422, detail="audit_archive_zip_required")
    raw = await archive.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="audit_archive_too_large")
    with tempfile.TemporaryDirectory() as directory:
        package = Path(directory) / "audit-package.zip"
        package.write_bytes(raw)
        try:
            result = await asyncio.to_thread(audit_watermark_service.decode_archive, package)
        except audit_watermark_service.AuditWatermarkError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    audit_log_service.record_safe(
        event_type="image.audit_watermark_decode",
        module="provenance",
        action="decode",
        outcome="success",
        summary="导入并核验可逆审计证据包",
        metadata={"payload_integrity": result["payload_integrity"]},
    )
    return result


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
                     ocr_text: str = Form(None),
                     ocr_status: str = Form(None),
                     modules: str = Form("deepfake,mllm,rag")):
    """SSE 流式全量审计报告"""
    mod_set = {item.strip() for item in modules.split(",") if item.strip()}

    async def event_stream():
        path = None
        report_results: dict[str, object] = {}
        tasks: list[asyncio.Task] = []

        def degraded_result(name: str, exc: Exception) -> dict:
            common = {
                "status": "degraded",
                "error_code": "module_unavailable",
                "summary": f"{name} 检测暂时不可用，已保留其他模块结果",
                "detail": type(exc).__name__,
            }
            if name == "deepfake":
                return {**common, "label": "review", "score": 0.0, "confidence": 0.0}
            if name == "mllm":
                return {**common, "verdict": "uncertain", "confidence": 0.0, "evidence": []}
            if name == "content_safety":
                return {**common, "verdict": "review", "safe": False, "risk_score": 0.0,
                        "categories": [], "requires_human_review": True}
            if name == "rag":
                return {**common, "safe": False, "risk_level": "unknown", "matched_rules": []}
            if name == "provenance":
                return {**common, "overall_state": "inconclusive"}
            return common

        async def run_module(name: str, function, *args):
            try:
                return name, await asyncio.to_thread(function, *args)
            except Exception as exc:
                return name, degraded_result(name, exc)

        async def run_rag_with_ocr():
            recognized = (ocr_text or "").strip()[:12_000]
            client_ocr_completed = ocr_status in {"completed", "corrected", "empty", "unavailable", "failed"}
            ocr_result = {
                "status": (ocr_status if client_ocr_completed else ("corrected" if recognized else "not_run")),
                "text": recognized,
                "char_count": len(recognized),
                "latency_ms": 0,
                "error_code": None,
            }
            if path and not recognized and not client_ocr_completed:
                ocr_result = await asyncio.to_thread(ocr_service.ocr_image_result, path)
                recognized = str(ocr_result.get("text") or "").strip()[:12_000]
            parts = []
            if recognized:
                parts.append(f"[图片 OCR 文本]\n{recognized}")
            manual_text = (text or "").strip()[:12_000]
            if manual_text:
                parts.append(f"[人工输入文本]\n{manual_text}")
            if not parts:
                rag_result = {
                    "status": "inconclusive", "safe": False, "risk_level": "unknown",
                    "matched_rules": [], "matched_keywords": [],
                    "summary": "图片中未识别到可供红线知识库审核的文字",
                }
            else:
                rag_result = await asyncio.to_thread(rag_service.check_content, "\n\n".join(parts))
            return "ocr_rag", {"ocr": ocr_result, "rag": rag_result}

        try:
            if image:
                path = await _save_upload(image)
                face = None
                has_face = True
                if "face" in mod_set or "deepfake" in mod_set:
                    face = await asyncio.to_thread(_inspect_faces, path)
                    report_results["face"] = face
                    has_face = face.get("face_detected") is not False
                    yield _sse("face", face)

                if "provenance" in mod_set:
                    tasks.append(asyncio.create_task(run_module("provenance", provenance_service.verify, path)))

                if "deepfake" in mod_set:
                    if has_face:
                        tasks.append(asyncio.create_task(run_module("deepfake", deepfake_service.detect, path)))
                    else:
                        df = {"score": 0, "label": "skipped", "confidence": 0, "reason": "no face detected"}
                        report_results["deepfake"] = df
                        yield _sse("deepfake", df)

                if "mllm" in mod_set:
                    tasks.append(asyncio.create_task(run_module("mllm", mllm_service.analyze, path)))

                if "content_safety" in mod_set:
                    tasks.append(asyncio.create_task(run_module(
                        "content_safety", mllm_service.analyze_content_safety, path
                    )))

            if "rag" in mod_set and (path or text or ocr_text):
                tasks.append(asyncio.create_task(run_rag_with_ocr()))

            if tasks:
                yield _sse("step", {
                    "step": "parallel_analysis", "status": "running", "count": len(tasks)
                })
                for completed in asyncio.as_completed(tasks):
                    name, result = await completed
                    if name == "ocr_rag":
                        report_results["ocr_text"] = result["ocr"].get("text", "")
                        report_results["ocr"] = {
                            key: value for key, value in result["ocr"].items() if key != "text"
                        }
                        report_results["rag"] = result["rag"]
                        yield _sse("ocr", result["ocr"])
                        yield _sse("rag", result["rag"])
                        continue
                    if name == "content_safety":
                        _record_content_safety(result)
                    report_results[name] = result
                    yield _sse(name, result)

            yield _sse("step", {"step": "report", "status": "running"})
            report = await _finalize_report({
                **report_results,
                "requested_modules": sorted(mod_set),
                **({"_thumbnail_source": path} if path else {}),
                **({"filename": image.filename} if image and image.filename else {}),
                **({"text": text} if text else {}),
            })
            yield _sse("done", {"status": "completed", "report_id": report["id"]})
        finally:
            pending = [task for task in tasks if not task.done()]
            if pending:
                cleanup_path = path

                async def finish_and_cleanup():
                    await asyncio.gather(*pending, return_exceptions=True)
                    if cleanup_path and os.path.exists(cleanup_path):
                        os.unlink(cleanup_path)

                background = asyncio.create_task(finish_and_cleanup())
                _BACKGROUND_TASKS.add(background)
                background.add_done_callback(_BACKGROUND_TASKS.discard)
                path = None
            if path and os.path.exists(path):
                os.unlink(path)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)


def _report_operator(request: Request) -> dict:
    user = auth_service.verify_session(request.cookies.get("aigc_operator_session"))
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="请先登录审核员账号")
    return user


def _report_thumbnails_dir() -> Path:
    return REPORTS_DIR / "thumbnails"


def _create_report_thumbnail(source_path: str, report_id: str) -> dict:
    """Create a metadata-free review derivative; the original remains ephemeral."""
    thumbnails_dir = _report_thumbnails_dir()
    thumbnails_dir.mkdir(parents=True, exist_ok=True)
    output = thumbnails_dir / f"{report_id}.webp"
    with Image.open(source_path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((480, 480), Image.Resampling.LANCZOS)
        image.save(output, format="WEBP", quality=78, method=6)
        width, height = image.size
    return {"url": f"/api/detect/report/{report_id}/thumbnail", "width": width, "height": height,
            "media_type": "image/webp", "derivative_only": True, "metadata_removed": True}


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


def _report_modules(report: dict) -> list[str]:
    requested = report.get("requested_modules")
    if isinstance(requested, list) and requested:
        return [str(item) for item in requested]
    return [key for key in ("provenance", "face", "deepfake", "mllm", "content_safety", "rag") if report.get(key) is not None]


def _report_title(report: dict) -> str:
    modules = set(_report_modules(report))
    if modules == {"provenance"}:
        return "AI 来源与内容凭证验证报告"
    if modules <= {"face", "deepfake", "mllm"}:
        return "图像真实性检测报告"
    if modules == {"content_safety"}:
        return "视觉内容安全审核报告"
    if modules == {"rag"}:
        return "红线知识库审核报告"
    return "多维图片安全审核报告"


def _call_summary(client, model: str, report: dict) -> str:
    modules = _report_modules(report)
    title = _report_title(report)
    evidence_keys = set(modules) | {"filename", "created_at"}
    if "rag" in modules:
        evidence_keys |= {"ocr", "ocr_text"}
    evidence = {key: value for key, value in report.items() if key in evidence_keys}
    prompt = f"""你是图片安全审计报告撰写员。根据本次实际运行的检测结果生成 Markdown 报告。

报告标题：{title}
本次运行模块：{json.dumps(modules, ensure_ascii=False)}

检测结果：
{json.dumps(evidence, ensure_ascii=False, indent=2)}

要求：
1. 第一行必须是“# {title}”。
2. 只描述本次运行模块，严禁补写未运行的人脸、Deepfake、MLLM、RAG、内容安全或来源维度。
3. 使用“任务结论”“证据说明”“处置建议”三个部分；没有证据时明确写证据不足。
4. 来源凭证不存在不能解释为非 AI；来源凭证有效也不能解释为内容安全。
5. 语言简洁专业，避免重复任务 ID、文件名和哈希，它们由报告页面单独展示。
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
    report["requested_modules"] = _report_modules(report)
    report["report_title"] = _report_title(report)
    thumbnail_source = payload.get("_thumbnail_source")
    if thumbnail_source:
        try:
            report["thumbnail"] = await asyncio.to_thread(_create_report_thumbnail, str(thumbnail_source), report["id"])
        except Exception:
            report["thumbnail"] = {"status": "unavailable", "derivative_only": True}
    report.pop("_thumbnail_source", None)
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
                "report_title": r.get("report_title") or _report_title(r),
                "requested_modules": _report_modules(r),
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


@router.get("/report/{report_id}/thumbnail")
async def get_report_thumbnail(report_id: str):
    try:
        uuid.UUID(report_id)
    except (ValueError, AttributeError) as exc:
        from fastapi import HTTPException
        raise HTTPException(404, "Thumbnail not found") from exc
    path = _report_thumbnails_dir() / f"{report_id}.webp"
    if not path.is_file():
        from fastapi import HTTPException
        raise HTTPException(404, "Thumbnail not found")
    return FileResponse(str(path), media_type="image/webp", headers={"Cache-Control": "private, max-age=3600"})


@router.delete("/report/{report_id}")
async def delete_report(report_id: str, request: Request):
    operator = _report_operator(request)
    try:
        uuid.UUID(report_id)
    except (ValueError, AttributeError) as exc:
        from fastapi import HTTPException
        raise HTTPException(404, "Report not found") from exc
    report_path = REPORTS_DIR / f"{report_id}.json"
    if not report_path.is_file():
        from fastapi import HTTPException
        raise HTTPException(404, "Report not found")
    thumbnail_path = _report_thumbnails_dir() / f"{report_id}.webp"
    await asyncio.to_thread(report_path.unlink)
    if thumbnail_path.is_file():
        await asyncio.to_thread(thumbnail_path.unlink)
    audit_log_service.record_safe(
        event_type="report.delete", module="detect", action="delete_report", outcome="success",
        summary="审核员删除检测报告", metadata={"report_id": report_id, "operator": operator["username"]},
    )
    return {"deleted": True, "report_id": report_id}


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
        f"# {report.get('report_title') or _report_title(report)}\n",
        f"**报告ID**: {report_id}  \n",
        f"**生成时间**: {report.get('created_at','')}\n\n---\n",
    ]
    if report.get("filename"):
        lines.append(f"**检测文件**: {report['filename']}\n\n")
    lines.append(f"**检测范围**: {', '.join(_report_modules(report)) or '未记录'}\n\n")
    if report.get("provenance"):
        provenance = report["provenance"]
        lines.append(
            "## AI 来源与内容凭证\n"
            f"- 来源状态: **{provenance.get('overall_state')}**\n"
            f"- 内容哈希: `{provenance.get('content_hash', '')}`\n\n"
        )
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
        lines.append(f"## 文本与红线内容安全\n- 安全: **{'是' if rag.get('safe') else '否'}**\n- 风险等级: {rag.get('risk_level')}\n")
        if report.get("ocr_text"):
            safe_ocr_text = str(report["ocr_text"]).replace("```", "''' ")
            lines.append(f"- OCR 状态: {report.get('ocr', {}).get('status', 'completed')}\n\n### 图片 OCR 文本\n```text\n{safe_ocr_text}\n```\n")
        matched_rules = rag.get("matched_rules") or []
        matched_keywords = rag.get("matched_keywords") or []
        if matched_rules:
            lines.append(f"- 命中规则: {', '.join(map(str, matched_rules))}\n")
        if matched_keywords:
            lines.append(f"- 命中关键词: {', '.join(map(str, matched_keywords))}\n")
        lines.append("\n")
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
