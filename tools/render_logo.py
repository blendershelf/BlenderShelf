"""Render the approved BlenderShelf monogram (dark badge, orange "B",
three squares with an accented middle) to PNG at several sizes, plus a
multi-size favicon.ico. Supersamples 4x and downscales for clean edges.

Run: python tools/render_logo.py
Output: site/assets/logo/blendershelf-icon-<size>.png, favicon.ico

EasyShelf variant (same badge, "E" instead of "B"):
     python tools/render_logo.py --letter E --prefix easyshelf --out easyshelf/logo
"""
import argparse
import os
from PIL import Image, ImageDraw, ImageFont

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_PATH = os.path.join(REPO_DIR, "guide", "fonts", "IBMPlexSans-Bold.ttf")
OUT_DIR = os.path.join(REPO_DIR, "site", "assets", "logo")

DARK = (13, 11, 10)
ORANGE = (245, 121, 42)
DIM_SQUARE = (106, 55, 23)  # ORANGE at 40% opacity flattened over DARK

SUPERSAMPLE = 4
SIZES = [512, 256, 180, 128, 64, 48, 32, 16]


LETTER = "B"


def render(size):
    S = size * SUPERSAMPLE
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    radius = round(0.22 * S)
    draw.rounded_rectangle([0, 0, S - 1, S - 1], radius=radius, fill=DARK + (255,))

    font_size = round(0.54 * S)
    font = ImageFont.truetype(FONT_PATH, font_size)
    bbox = draw.textbbox((0, 0), LETTER, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    sq = max(2, round(0.115 * S))
    sq_radius = round(0.02 * S)
    sq_gap = max(1, round(0.035 * S))
    row_w = 3 * sq + 2 * sq_gap
    gap_v = max(2, round(0.05 * S))

    total_h = text_h + gap_v + sq
    top = (S - total_h) / 2

    text_x = (S - text_w) / 2 - bbox[0]
    text_y = top - bbox[1]
    draw.text((text_x, text_y), LETTER, font=font, fill=ORANGE + (255,))

    row_y = top + text_h + gap_v
    row_x = (S - row_w) / 2
    colors = [DIM_SQUARE, ORANGE, DIM_SQUARE]
    for i, color in enumerate(colors):
        x0 = row_x + i * (sq + sq_gap)
        draw.rounded_rectangle([x0, row_y, x0 + sq, row_y + sq], radius=sq_radius, fill=color + (255,))

    return img.resize((size, size), Image.LANCZOS)


def main():
    global LETTER
    ap = argparse.ArgumentParser()
    ap.add_argument("--letter", default="B")
    ap.add_argument("--prefix", default="blendershelf")
    ap.add_argument("--out", default=OUT_DIR)
    args = ap.parse_args()
    LETTER, out_dir = args.letter, os.path.join(REPO_DIR, args.out) if not os.path.isabs(args.out) else args.out
    os.makedirs(out_dir, exist_ok=True)
    rendered = {}
    for size in SIZES:
        img = render(size)
        rendered[size] = img
        path = os.path.join(out_dir, f"{args.prefix}-icon-{size}.png")
        img.save(path)
        print("wrote", path)

    favicon_path = os.path.join(out_dir, "favicon.ico")
    favicon_sizes = [16, 32, 48]
    rendered[max(favicon_sizes)].save(
        favicon_path,
        sizes=[(s, s) for s in favicon_sizes],
    )
    print("wrote", favicon_path)


if __name__ == "__main__":
    main()
