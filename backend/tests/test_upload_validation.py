import asyncio
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from starlette.datastructures import UploadFile

from services import upload_service


class UploadValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.upload_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _upload(self, data: bytes, content_type: str = "image/png"):
        return UploadFile(io.BytesIO(data), filename="claimed.jpg", headers={"content-type": content_type})

    def test_valid_png_is_saved_with_opaque_extension(self):
        from PIL import Image

        stream = io.BytesIO()
        Image.new("RGB", (16, 16), "white").save(stream, format="PNG")
        path = asyncio.run(upload_service.save_image_upload(self._upload(stream.getvalue()), self.upload_dir))
        self.assertTrue(Path(path).exists())
        self.assertEqual(Path(path).suffix, ".upload")

    def test_invalid_bytes_are_rejected_and_removed(self):
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(upload_service.save_image_upload(self._upload(b"not-an-image"), self.upload_dir))
        self.assertEqual(ctx.exception.status_code, 415)
        self.assertEqual(list(self.upload_dir.iterdir()), [])

    def test_non_image_content_type_is_rejected_before_write(self):
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(upload_service.save_image_upload(self._upload(b"x", "text/plain"), self.upload_dir))
        self.assertEqual(ctx.exception.status_code, 415)
        self.assertEqual(list(self.upload_dir.iterdir()), [])

    def test_pixel_limit_is_enforced(self):
        from PIL import Image

        stream = io.BytesIO()
        Image.new("RGB", (20, 20), "white").save(stream, format="PNG")
        with patch("services.upload_service.MAX_IMAGE_PIXELS", 100):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(upload_service.save_image_upload(self._upload(stream.getvalue()), self.upload_dir))
        self.assertEqual(ctx.exception.status_code, 413)
        self.assertEqual(list(self.upload_dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
