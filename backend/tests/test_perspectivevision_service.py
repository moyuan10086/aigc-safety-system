import httpx
from PIL import Image

from services import perspectivevision_service as service


def _write_image(path):
    Image.new("RGB", (32, 24), color=(20, 40, 60)).save(path, format="JPEG")


def test_perspectivevision_is_disabled_by_default(tmp_path, monkeypatch):
    image = tmp_path / "sample.jpg"
    _write_image(image)
    monkeypatch.setattr(service.config, "PERSPECTIVE_VISION_ENABLED", False)

    result = service.analyze(str(image))

    assert result["status"] == "not_configured"
    assert result["error_code"] == "disabled"


def test_perspectivevision_normalizes_authenticated_response(tmp_path, monkeypatch):
    image = tmp_path / "sample.jpg"
    _write_image(image)
    real_client = httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-API-Key"] == "test-key"
        assert len(request.headers["X-Content-SHA256"]) == 64
        return httpx.Response(200, json={
            "status": "unsafe",
            "category": "Violence",
            "response_sha256": "a" * 64,
            "model_revision": "revision",
        })

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(service.config, "PERSPECTIVE_VISION_ENABLED", True)
    monkeypatch.setattr(service.config, "PERSPECTIVE_VISION_ENDPOINT", "http://gpu.test/infer")
    monkeypatch.setattr(service.config, "PERSPECTIVE_VISION_API_KEY", "test-key")
    monkeypatch.setattr(
        service.httpx,
        "Client",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )

    result = service.analyze(str(image))

    assert result["status"] == "detected"
    assert result["categories"] == ["violence"]
    assert result["response_sha256"] == "a" * 64
    assert result["content_hash"]
    assert result["request_hash"]
    assert result["request_bytes"] > 0


def test_perspectivevision_unparseable_response_is_inconclusive(tmp_path, monkeypatch):
    image = tmp_path / "sample.jpg"
    _write_image(image)
    real_client = httpx.Client
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"status": "unknown"})
    )
    monkeypatch.setattr(service.config, "PERSPECTIVE_VISION_ENABLED", True)
    monkeypatch.setattr(service.config, "PERSPECTIVE_VISION_ENDPOINT", "http://gpu.test/infer")
    monkeypatch.setattr(service.config, "PERSPECTIVE_VISION_API_KEY", "test-key")
    monkeypatch.setattr(
        service.httpx,
        "Client",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )

    result = service.analyze(str(image))

    assert result["status"] == "inconclusive"
    assert result["error_code"] == "inconclusive_output"
