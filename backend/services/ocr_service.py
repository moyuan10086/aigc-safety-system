"""
OCR 服务 — pypdf 提取失败时 fallback 到 PaddleOCR，
并可调用 MLLM 对图片页面做内容分析
"""
import re

_ocr = None


def _get_ocr():
    global _ocr
    if _ocr is None:
        from paddleocr import PaddleOCR
        _ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    return _ocr


def is_garbled(text: str, threshold: float = 0.3) -> bool:
    """检测文本是否乱码：非中英文字符比例超过阈值"""
    if not text or len(text.strip()) < 10:
        return True
    valid = len(re.findall(r'[\u4e00-\u9fff\u0020-\u007e]', text))
    return valid / len(text) < (1 - threshold)


def ocr_pdf(pdf_path: str) -> str:
    """用 PaddleOCR 识别 PDF（转图片后识别）"""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return ""

    try:
        ocr = _get_ocr()
    except (ImportError, ModuleNotFoundError):
        return ""
    doc = fitz.open(pdf_path)
    texts = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        import numpy as np
        import cv2
        img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        result = ocr.ocr(img, cls=True)
        if result and result[0]:
            texts.append(" ".join(line[1][0] for line in result[0] if line[1]))
    return "\n".join(texts)


def ocr_image(image_path: str) -> str:
    """用 PaddleOCR 识别图片中的文字"""
    try:
        ocr = _get_ocr()
    except (ImportError, ModuleNotFoundError):
        return ""
    result = ocr.ocr(image_path, cls=True)
    if not result or not result[0]:
        return ""
    return " ".join(line[1][0] for line in result[0] if line[1])


def analyze_image_content(image_path: str) -> dict:
    """
    综合分析图片内容：
    1. OCR 提取文字
    2. RAG 内容审核
    3. MLLM 判断是否 AI 生成
    4. 视觉大模型执行多标签内容安全审核
    """
    from services import rag_service, mllm_service

    ocr_text = ocr_image(image_path)
    rag_result = rag_service.check_content(ocr_text) if ocr_text.strip() else None
    mllm_result = mllm_service.analyze(image_path)
    content_safety = mllm_service.analyze_content_safety(image_path)

    return {
        "ocr_text": ocr_text,
        "rag": rag_result,
        "mllm": mllm_result,
        "content_safety": content_safety,
    }
