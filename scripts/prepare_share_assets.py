"""Prepare watermarked screenshot and demo-video sharing assets."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "文档截图" / "20260814"
OUTPUT = ROOT / "docs" / "competition-materials" / "screenshots-20260814"
LABEL = "github.com/moyuan10086/aigc-safety-system  |  2572045628@qq.com"
FONT = Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf")


def watermark_image(source: Path, output: Path) -> None:
    image = Image.open(source).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    size = max(14, round(image.width / 110))
    font = ImageFont.truetype(str(FONT), size)
    margin = max(12, round(image.width / 100))
    bbox = draw.textbbox((0, 0), LABEL, font=font)
    x = image.width - (bbox[2] - bbox[0]) - margin
    y = image.height - (bbox[3] - bbox[1]) - margin
    draw.rounded_rectangle(
        (x - 9, y - 5, image.width - margin + 5, image.height - margin + 5),
        radius=5,
        fill=(255, 255, 255, 180),
    )
    draw.text((x, y), LABEL, font=font, fill=(65, 65, 65, 205))
    image = Image.alpha_composite(image, overlay).convert("RGB")
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, quality=94)


def main() -> None:
    if not SOURCE.is_dir():
        raise FileNotFoundError(SOURCE)
    for source in sorted(SOURCE.iterdir()):
        if source.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            continue
        watermark_image(source, OUTPUT / source.name)
        print(f"created {OUTPUT / source.name}")


if __name__ == "__main__":
    main()
