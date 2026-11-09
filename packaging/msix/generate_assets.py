"""Generate the PNG assets required by the AURIX MSIX package."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw


def make_icon(size: tuple[int, int], destination: Path) -> None:
    width, height = size
    image = Image.new("RGBA", size, (7, 21, 35, 255))
    draw = ImageDraw.Draw(image)
    scale = min(width, height)
    margin = max(2, int(scale * 0.08))
    draw.rounded_rectangle(
        (margin, margin, width - margin - 1, height - margin - 1),
        radius=max(2, int(scale * 0.18)),
        outline=(72, 224, 249, 255),
        width=max(1, int(scale * 0.035)),
    )

    cx = width / 2
    top = height * 0.20
    bottom = height * 0.78
    half = width * 0.27
    stroke = max(2, int(scale * 0.075))
    left = (cx - half, bottom)
    peak = (cx, top)
    right = (cx + half, bottom)
    draw.line((left, peak, right), fill=(200, 253, 255, 255), width=stroke, joint="curve")
    draw.line(
        (cx - half * 0.48, height * 0.59, cx + half * 0.48, height * 0.59),
        fill=(72, 224, 249, 255),
        width=stroke,
    )
    image.save(destination, format="PNG", optimize=True)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Uso: generate_assets.py <pasta-de-staging>")
    assets = Path(sys.argv[1]) / "Assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name, size in {
        "StoreLogo.png": (50, 50),
        "Square44x44Logo.png": (44, 44),
        "Square150x150Logo.png": (150, 150),
        "Wide310x150Logo.png": (310, 150),
        "SplashScreen.png": (620, 300),
    }.items():
        make_icon(size, assets / name)


if __name__ == "__main__":
    main()
