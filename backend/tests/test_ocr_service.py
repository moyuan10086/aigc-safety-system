from unittest.mock import patch

from services import ocr_service


def test_image_ocr_degrades_when_paddle_runtime_is_unavailable():
    with patch.object(ocr_service, "_get_ocr", side_effect=ModuleNotFoundError("paddle")):
        assert ocr_service.ocr_image("unused.png") == ""


def test_pdf_ocr_degrades_when_paddle_runtime_is_unavailable(tmp_path):
    pdf = tmp_path / "unused.pdf"
    pdf.write_bytes(b"not-read-because-ocr-is-unavailable")
    with patch.object(ocr_service, "_get_ocr", side_effect=ModuleNotFoundError("paddle")):
        assert ocr_service.ocr_pdf(str(pdf)) == ""
