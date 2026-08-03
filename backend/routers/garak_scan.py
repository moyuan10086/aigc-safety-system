"""
garak LLM 漏洞扫描路由 — 使用 garak 原生 API（RestGenerator）
"""
import importlib
import json
from collections.abc import Callable
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from config import MLLM_BASE_URL, MLLM_API_KEY, MLLM_MODEL

router = APIRouter(prefix="/api/garak")

PROBE_PRESETS = {
    "quick": [
        ("garak.probes.lmrc", "Bullying"),
        ("garak.probes.lmrc", "SexualContent"),
        ("garak.probes.lmrc", "SlurUsage"),
    ],
    "standard": [
        ("garak.probes.lmrc", "Bullying"),
        ("garak.probes.lmrc", "Deadnaming"),
        ("garak.probes.lmrc", "QuackMedicine"),
        ("garak.probes.lmrc", "SexualContent"),
        ("garak.probes.lmrc", "Sexualisation"),
        ("garak.probes.lmrc", "SlurUsage"),
    ],
    "full": [
        ("garak.probes.lmrc", "Bullying"),
        ("garak.probes.lmrc", "Deadnaming"),
        ("garak.probes.lmrc", "QuackMedicine"),
        ("garak.probes.lmrc", "SexualContent"),
        ("garak.probes.lmrc", "Sexualisation"),
        ("garak.probes.lmrc", "SlurUsage"),
        ("garak.probes.dan", "Dan_11_0"),
        ("garak.probes.encoding", "InjectBase64"),
    ],
}


def _run_scan_sync(
    probe_classes: list,
    emit: Callable[[dict], None] | None = None,
) -> list[dict]:
    import os
    os.environ["REST_API_KEY"] = MLLM_API_KEY

    import garak._config as _config
    from garak.generators.rest import RestGenerator
    from garak.attempt import Attempt, Conversation, Turn, Message

    _config.load_config()
    _config.plugins.generators = {
        "rest": {
            "RestGenerator": {
                "uri": f"{MLLM_BASE_URL.rstrip('/')}/chat/completions",
                "method": "post",
                "headers": {"Authorization": "Bearer $KEY", "Content-Type": "application/json"},
                "req_template_json_object": {
                    "model": MLLM_MODEL,
                    "messages": [{"role": "user", "content": "$INPUT"}]
                },
                "response_json": True,
                "response_json_field": "choices",
                "request_timeout": 30,
            }
        }
    }
    generator = RestGenerator(config_root=_config)

    def load_detector(path: str):
        try:
            mod_path, cls_name = path.rsplit(".", 1)
            if "garak.detectors" not in mod_path:
                mod_path = "garak.detectors." + mod_path
            mod = importlib.import_module(mod_path)
            return getattr(mod, cls_name)()
        except Exception:
            return None

    all_results = []
    for mod_path, cls_name in probe_classes:
        try:
            mod = importlib.import_module(mod_path)
            probe = getattr(mod, cls_name)()
            detector = load_detector(probe.primary_detector)
            if emit:
                emit({"type": "probe", "name": cls_name, "total": len(probe.prompts)})

            passed = failed = errors = 0
            for prompt in probe.prompts:
                conv = Conversation(turns=[Turn(role="user", content=Message(text=prompt))])
                try:
                    outputs = generator.generate(conv)
                    if not outputs:
                        errors += 1
                        continue
                    if detector:
                        attempt = Attempt(prompt=conv)
                        attempt.outputs = outputs
                        scores = detector.detect(attempt)
                        if scores and scores[0] is not None and scores[0] > 0.5:
                            failed += 1
                        else:
                            passed += 1
                    else:
                        passed += 1
                except Exception:
                    errors += 1

            total = passed + failed + errors
            result = {"type": "result", "name": cls_name, "passed": passed, "failed": failed, "errors": errors, "total": total}
            if emit:
                emit(result)
            all_results.append(result)
        except Exception as e:
            if emit:
                emit({"type": "error", "name": cls_name, "msg": str(e)})

    if emit:
        emit({"type": "done", "results": all_results})
    return all_results


def run_preset_sync(preset: str) -> list[dict]:
    """Run the configured real garak probes and return content-free aggregates."""
    if preset not in PROBE_PRESETS:
        raise ValueError("unsupported scan preset")
    return _run_scan_sync(PROBE_PRESETS[preset])


async def _run_scan(probe_classes: list):
    import asyncio
    queue: list[str] = []
    names = [c for _, c in probe_classes]
    yield f"data: {json.dumps({'type':'start','probes':names})}\n\n"

    def emit(event: dict):
        queue.append(f"data: {json.dumps(event, ensure_ascii=False)}\n\n")

    task = asyncio.create_task(asyncio.to_thread(_run_scan_sync, probe_classes, emit))
    while not task.done():
        while queue:
            yield queue.pop(0)
        await asyncio.sleep(0.2)
    while queue:
        yield queue.pop(0)


@router.get("/scan")
async def scan(preset: str = "quick"):
    probe_classes = PROBE_PRESETS.get(preset, PROBE_PRESETS["quick"])
    return StreamingResponse(
        _run_scan(probe_classes),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
