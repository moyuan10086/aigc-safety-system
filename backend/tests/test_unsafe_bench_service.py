from services import unsafe_bench_service as service


def test_unsafe_bench_is_fail_closed_when_not_configured(tmp_path, monkeypatch):
    image = tmp_path / "sample.jpg"
    image.write_bytes(b"fixture")
    monkeypatch.setattr(service, "UNSAFE_BENCH_ENABLED", False)

    result = service.analyze(str(image))

    assert result["status"] == "not_configured"
    assert result["error_code"] == "disabled"


def test_unsafe_bench_provider_error_is_inconclusive(tmp_path, monkeypatch):
    image = tmp_path / "sample.jpg"
    image.write_bytes(b"fixture")
    monkeypatch.setattr(service, "UNSAFE_BENCH_ENABLED", True)
    monkeypatch.setattr(service, "UNSAFE_BENCH_ENDPOINT", "http://127.0.0.1:9/infer")

    result = service.analyze(str(image))

    assert result["status"] == "inconclusive"
    assert result["privacy"]["external_upload"] is True


def test_unsafe_bench_normalizes_provider_categories():
    assert service.UNSAFEBENCH_ALIASES["violent"] == "violence"
    assert service.UNSAFEBENCH_ALIASES["disturbing"] == "shocking"
    assert service._status_from_payload({"verdict": "unsafe"}, 0.1) == "detected"
    assert service._status_from_payload({"verdict": "safe"}, 0.1) == "not_detected"
    assert service._status_from_payload({}, None) == "inconclusive"
