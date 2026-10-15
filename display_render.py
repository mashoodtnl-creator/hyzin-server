"""Rasterize the reply for ST7735: 128x40, one-bit, MSB-first bitmap."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import quran

WIDTH, HEIGHT = 128, 40
FONT_DIR = Path(__file__).resolve().parent / "fonts"


def render_reply(text: str, language: str) -> bytes:
    if language == "ml-IN":
        font = ImageFont.truetype(FONT_DIR / "NotoSansMalayalam.ttf", 12)
    elif language == "ta-IN":
        font = ImageFont.truetype(FONT_DIR / "NotoSansTamil.ttf", 12)
    else:
        font = ImageFont.load_default(size=12)
    image = Image.new("1", (WIDTH, HEIGHT), 0)
    draw = ImageDraw.Draw(image)
    lines = []
    current = ""
    for word in text.split():
        candidate = (current + " " + word).strip()
        if draw.textlength(candidate, font=font) <= WIDTH - 4:
            current = candidate
        else:
            if current:
                lines.append(current)
                current = word
            else:
                # Clip very long words in the drawing window rather than overflow memory.
                lines.append(word)
                current = ""
        if len(lines) == 2:
            break
    if current and len(lines) < 2:
        lines.append(current)
    for i, line in enumerate(lines[:2]):
        draw.text((2, i * 19), line, fill=1, font=font)
    return image.tobytes()


def render_ayah(verse, wrong_indices=()) -> bytes:
    """128x160 RGB565 LE full-screen preview; full text remains server-side."""
    import arabic_reshaper
    from bidi.algorithm import get_display

    canvas = Image.new("RGB", (128, 160), (0, 0, 8))
    draw = ImageDraw.Draw(canvas)
    arabic_font = ImageFont.truetype(FONT_DIR / "NotoNaskhArabic.ttf", 16)
    ml_font = ImageFont.truetype(FONT_DIR / "NotoSansMalayalam.ttf", 10)
    draw.text((3, 2), f"Surah {verse.surah} : {verse.number}", fill=(0, 215, 255))
    draw.line((0, 17, 127, 17), fill=(45, 90, 120))
    words = [word for word in verse.arabic.split() if quran.normalize_arabic(word)]
    y, x = 24, 126
    for index, word in enumerate(words):
        shaped = get_display(arabic_reshaper.reshape(word))
        width = draw.textlength(shaped, font=arabic_font)
        if x - width < 1:
            y += 22
            x = 126
        if y > 99:
            draw.text((111, 94), "...", fill="white")
            break
        draw.text((x - width, y), shaped,
                  fill=(255, 65, 65) if index in wrong_indices else (255, 255, 255),
                  font=arabic_font)
        x -= width + 5
    draw.line((0, 119, 127, 119), fill=(45, 90, 120))
    y, line = 123, ""
    for word in verse.malayalam.split():
        attempt = f"{line} {word}".strip()
        if draw.textlength(attempt, font=ml_font) > 124 and line:
            draw.text((2, y), line, fill=(190, 240, 255), font=ml_font)
            y += 14
            line = word
        else:
            line = attempt
        if y > 148:
            break
    if line and y <= 148:
        draw.text((2, y), line, fill=(190, 240, 255), font=ml_font)
    # Adafruit drawRGBBitmap consumes uint16_t[] in host little-endian RGB565.
    from array import array
    import sys
    pixels = array("H", [((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
                         for r, g, b in canvas.getdata()])
    if sys.byteorder != "little":
        pixels.byteswap()
    return pixels.tobytes()
