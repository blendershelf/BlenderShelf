"""Build the BlenderShelf user guide as a themed PDF.

Reusable by design: content_<lang>.json holds all guide text (structure is
language-agnostic), theme_palette.json holds the Blender-theme colors, and
screenshots/ holds the images both language versions share. To produce an
English version later: translate content_ru.json into content_en.json
(same keys/shape) and run this script against it -- no code changes needed.

Usage: python build_guide.py [content_ru.json] [output.pdf]
"""
import json
import os
import sys

from PIL import Image as PILImage
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import Color
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    KeepTogether, NextPageTemplate, PageTemplate, Frame, BaseDocTemplate,
)
from reportlab.pdfgen import canvas as canvas_mod

HERE = os.path.dirname(os.path.abspath(__file__))

# IBM Plex Sans/Mono -- same family the website loads from Google Fonts
# (site/index.html), so the guide reads as the same product. Full Cyrillic
# coverage confirmed (fontTools cmap check) before adopting it here.
FONT_DIR = os.path.join(HERE, "fonts")
pdfmetrics.registerFont(TTFont("Body", os.path.join(FONT_DIR, "IBMPlexSans-Regular.ttf")))
pdfmetrics.registerFont(TTFont("Body-Bold", os.path.join(FONT_DIR, "IBMPlexSans-SemiBold.ttf")))
pdfmetrics.registerFont(TTFont("Body-Italic", os.path.join(FONT_DIR, "IBMPlexSans-Italic.ttf")))


def rgb(vals):
    return Color(vals[0] / 255.0, vals[1] / 255.0, vals[2] / 255.0)


def load_palette():
    with open(os.path.join(HERE, "theme_palette.json"), encoding="utf-8") as f:
        p = json.load(f)
    return {k: rgb(v) for k, v in p.items() if isinstance(v, list)}


PAGE_W, PAGE_H = A4
MARGIN = 44
CONTENT_W = PAGE_W - 2 * MARGIN
# Prose measure: images/headings keep the full content width, but a body
# paragraph set at full width runs ~95-100 characters/line at this font size
# -- well past the ~65-75ch comfortable reading measure. 360pt keeps body
# text around 70ch while everything else stays full-bleed.
TEXT_W = 360


MAX_UPSCALE = 1.8  # cap upscaling small screenshot crops so they don't turn blocky


def fit(path, max_w, max_h):
    im = PILImage.open(path)
    w, h = im.size
    scale = min(max_w / w, max_h / h, MAX_UPSCALE)
    return w * scale, h * scale


def build_styles(pal):
    styles = {}
    styles["title"] = ParagraphStyle(
        "title", fontName="Body-Bold", fontSize=30, leading=34,
        textColor=pal["accent_orange"], alignment=TA_LEFT, spaceAfter=6,
    )
    styles["subtitle"] = ParagraphStyle(
        "subtitle", fontName="Body", fontSize=13, leading=17,
        textColor=pal["text_primary"], alignment=TA_LEFT, spaceAfter=18,
    )
    styles["h2"] = ParagraphStyle(
        "h2", fontName="Body-Bold", fontSize=13, leading=16,
        textColor=pal["text_bright"], alignment=TA_LEFT,
        spaceBefore=0, spaceAfter=0, leftIndent=10,
    )
    styles["body"] = ParagraphStyle(
        "body", fontName="Body", fontSize=10.3, leading=14.5,
        textColor=pal["text_primary"], alignment=TA_LEFT, spaceAfter=8,
    )
    styles["caption"] = ParagraphStyle(
        "caption", fontName="Body-Italic", fontSize=8.5, leading=11,
        textColor=pal["text_muted"], alignment=TA_CENTER, spaceBefore=4, spaceAfter=2,
    )
    return styles


def narrow(paragraph, width=TEXT_W):
    # Constrains a Paragraph to a comfortable reading measure without
    # centering or otherwise touching its own alignment/style. A Paragraph's
    # own spaceAfter doesn't carry through once it's the sole content of a
    # Table cell, so BOTTOMPADDING restores the gap between paragraphs that
    # styles["body"]'s spaceAfter=8 gave them when they were bare flowables.
    t = Table([[paragraph]], colWidths=[width])
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
    ]))
    return t


def section_heading(text, pal, styles):
    p = Paragraph(text, styles["h2"])
    t = Table([[p]], colWidths=[CONTENT_W], rowHeights=[24])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), pal["bg_panel"]),
        ("LINEBEFORE", (0, 0), (0, -1), 3, pal["accent_orange"]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def framed_image(path, pal, max_w, max_h, pad=10):
    w, h = fit(path, max_w - 2 * pad, max_h - 2 * pad)
    img = Image(path, width=w, height=h)
    t = Table([[img]], colWidths=[w + 2 * pad], rowHeights=[h + 2 * pad])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), pal["bg_box"]),
        ("BOX", (0, 0), (-1, -1), 1, pal["border"]),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    wrap = Table([[t]], colWidths=[CONTENT_W])
    wrap.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return wrap


def framed_image_row(paths, pal, total_w, max_h, gap=10, pad=8):
    n = len(paths)
    col_w = (total_w - gap * (n - 1)) / n
    cells = []
    for p in paths:
        w, h = fit(p, col_w - 2 * pad, max_h - 2 * pad)
        img = Image(p, width=w, height=h)
        inner = Table([[img]], colWidths=[col_w])
        inner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), pal["bg_box"]),
            ("BOX", (0, 0), (-1, -1), 1, pal["border"]),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), pad),
            ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
        ]))
        cells.append(inner)
    row = Table([cells], colWidths=[col_w] * n, spaceBefore=0)
    row.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0 if n == 1 else gap / 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0 if n == 1 else gap / 2),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
    ]))
    return row


def make_background(pal, footer_text, brand="BlenderShelf"):
    def draw(c: canvas_mod.Canvas, doc):
        c.setFillColor(pal["bg_darkest"])
        c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        # top strip
        c.setFillColor(pal["bg_panel"])
        c.rect(0, PAGE_H - 26, PAGE_W, 26, fill=1, stroke=0)
        c.setFillColor(pal["accent_orange"])
        c.rect(0, PAGE_H - 27, PAGE_W, 1.4, fill=1, stroke=0)
        c.setFillColor(pal["text_muted"])
        c.setFont("Body", 8)
        c.drawString(MARGIN, PAGE_H - 18, brand)
        # footer
        c.setStrokeColor(pal["border"])
        c.setLineWidth(0.6)
        c.line(MARGIN, 34, PAGE_W - MARGIN, 34)
        c.setFillColor(pal["text_muted"])
        c.setFont("Body", 8)
        c.drawString(MARGIN, 22, footer_text)
        c.drawRightString(PAGE_W - MARGIN, 22, str(c.getPageNumber()))
    return draw


def build(content_path, out_path):
    with open(content_path, encoding="utf-8") as f:
        content = json.load(f)
    pal = load_palette()
    styles = build_styles(pal)

    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=54, bottomMargin=46,
        title=content["title"], author=content.get("brand", "BlenderShelf"),
    )

    story = []

    # Title block
    story.append(Spacer(1, 10))
    story.append(Paragraph(content["title"], styles["title"]))
    story.append(Paragraph(content["subtitle"], styles["subtitle"]))
    hero = content.get("hero_image")
    if hero:
        story.append(framed_image(os.path.join(HERE, hero), pal, CONTENT_W, 260))
    story.append(Spacer(1, 16))

    for sec in content["sections"]:
        # Screenshot before its explanation, not after -- reading the
        # picture first gives the paragraph below something concrete to
        # refer back to, instead of describing a screen the reader hasn't
        # seen yet.
        block = [section_heading(sec["heading"], pal, styles), Spacer(1, 8)]
        img = sec.get("image")
        row = sec.get("image_row")
        if img or row:
            if img:
                block.append(framed_image(os.path.join(HERE, img), pal, CONTENT_W, sec.get("image_max_h", 230)))
            else:
                block.append(framed_image_row([os.path.join(HERE, p) for p in row], pal, CONTENT_W, 260))
            cap = sec.get("image_caption")
            if cap:
                block.append(Paragraph(cap, styles["caption"]))
            block.append(Spacer(1, 10))
            # keep heading+image(+caption) together so the heading never
            # sits alone at the bottom of a page with its screenshot pushed
            # to the next one
            head_group_len = len(block)
            for para in sec.get("paragraphs", []):
                block.append(narrow(Paragraph(para, styles["body"])))
        else:
            for para in sec.get("paragraphs", []):
                block.append(narrow(Paragraph(para, styles["body"])))
            # text-only section: glue heading to at least its first paragraph
            head_group_len = min(len(block), 3)
        block.append(Spacer(1, 14))
        story.append(KeepTogether(block[:head_group_len]))
        story.extend(block[head_group_len:])

    bg = make_background(pal, content.get("footer_text", ""), content.get("brand", "BlenderShelf"))
    doc.build(story, onFirstPage=bg, onLaterPages=bg)
    print("built:", out_path)


if __name__ == "__main__":
    content_arg = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "content_ru.json")
    out_arg = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "BlenderShelf_Guide_RU.pdf")
    build(content_arg, out_arg)
