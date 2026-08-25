"""Create lightly watermarked competition-material PDFs without modifying originals."""

from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT.parent / "信安赛材料"
OUTPUT_DIR = ROOT / "docs" / "competition-materials"
FONT_PATH = Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf")
WATERMARK = "github.com/moyuan10086/aigc-safety-system  |  2572045628@qq.com"
FOOTER = "github.com/moyuan10086/aigc-safety-system  |  2572045628@qq.com"


def make_overlay(width: float, height: float, target: Path) -> PdfReader:
    pdfmetrics.registerFont(TTFont("NotoSansSC", str(FONT_PATH)))
    c = canvas.Canvas(str(target), pagesize=(width, height))
    c.saveState()
    c.translate(width / 2, height / 2)
    c.rotate(32)
    c.setFillColorRGB(0.55, 0.55, 0.55, alpha=0.13)
    c.setFont("NotoSansSC", min(28, max(16, width / 28)))
    c.drawCentredString(0, 0, WATERMARK)
    c.restoreState()
    c.saveState()
    c.setFillColorRGB(0.35, 0.35, 0.35, alpha=0.55)
    c.setFont("NotoSansSC", 7.5)
    c.drawRightString(width - 18, 12, FOOTER)
    c.restoreState()
    c.save()
    return PdfReader(str(target))


def watermark(source: Path, output: Path) -> None:
    reader = PdfReader(str(source))
    writer = PdfWriter()
    overlay_cache: dict[tuple[float, float], PdfReader] = {}
    temp_dir = output.parent / ".watermark-temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        for index, page in enumerate(reader.pages):
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
            key = (width, height)
            if key not in overlay_cache:
                overlay_cache[key] = make_overlay(
                    width,
                    height,
                    temp_dir / f"overlay-{index}-{int(width)}x{int(height)}.pdf",
                )
            page.merge_page(overlay_cache[key].pages[0])
            writer.add_page(page)
        writer.add_metadata({
            "/Title": f"{source.stem} - 获奖分享版",
            "/Subject": "带获奖及仅供学习交流水印的项目材料",
            "/Author": "AIGC Safety System",
        })
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as handle:
            writer.write(handle)
    finally:
        for item in temp_dir.glob("*.pdf"):
            item.unlink(missing_ok=True)
        temp_dir.rmdir()


def main() -> None:
    jobs = [
        (
            SOURCE_DIR / "面向 AIGC 伪造的跨域泛化检测与可解释性防御平台(2).pdf",
            OUTPUT_DIR / "项目演示文稿-获奖分享版.pdf",
        ),
        (
            SOURCE_DIR / "面向 AIGC 伪造的跨域泛化检测与可解释性防御平台-作品报告.pdf",
            OUTPUT_DIR / "项目作品报告-获奖分享版.pdf",
        ),
    ]
    for source, output in jobs:
        if not source.is_file():
            raise FileNotFoundError(source)
        watermark(source, output)
        print(f"created {output} ({len(PdfReader(str(output)).pages)} pages)")


if __name__ == "__main__":
    main()
