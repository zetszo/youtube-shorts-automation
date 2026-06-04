import os
import random
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
THUMB_DIR = "output/thumbnails"
os.makedirs(THUMB_DIR, exist_ok=True)

OVERLAY_COLOR = (0, 0, 0, 180)

def _get_font(size=60):
    paths = [
        "/usr/share/fonts/truetype/cairo/Cairo-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
        "/usr/share/fonts/truetype/tajawal/Tajawal-Bold.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansArabic-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in paths:
        if os.path.isfile(p) and os.path.getsize(p) > 1000:
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    try:
        import subprocess
        out = subprocess.check_output(["fc-list", ":lang=ar", "-f", "%{file}\n"], stderr=subprocess.DEVNULL, timeout=5, encoding="utf-8")
        for line in out.strip().splitlines():
            f = line.strip()
            if f and os.path.isfile(f) and os.path.getsize(f) > 1000:
                return ImageFont.truetype(f, size)
    except Exception:
        pass
    return ImageFont.load_default()

def _draw_gradient(draw):
    for y in range(H):
        r = int(20 + (y / H) * 30)
        g = int(30 + (y / H) * 50)
        b = int(50 + (y / H) * 80)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

def generate_thumbnail(topic, output_path=None):
    img = Image.new("RGBA", (W, H), (20, 30, 50))
    draw = ImageDraw.Draw(img)
    _draw_gradient(draw)

    # Overlay bar
    bar_h = 200
    bar_y = H - bar_h - 60
    draw.rounded_rectangle([(40, bar_y), (W - 40, bar_y + bar_h)], radius=20, fill=OVERLAY_COLOR)

    # Title text
    lines = []
    font_large = _get_font(64)
    font_small = _get_font(48)
    words = topic.split()
    current = ""
    for w in words:
        test = current + " " + w if current else w
        bb = draw.textbbox((0, 0), test, font=font_large)
        if bb[2] - bb[0] < W - 120:
            current = test
        else:
            lines.append(current)
            current = w
    if current:
        lines.append(current)

    # Draw text
    y = bar_y + 30
    for i, line in enumerate(lines[:3]):
        font = font_large if i == 0 else font_small
        color = (255, 215, 0) if i == 0 else (255, 255, 255)
        bb = draw.textbbox((0, 0), line, font=font)
        tw = bb[2] - bb[0]
        x = (W - tw) // 2
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 180))
        draw.text((x, y), line, font=font, fill=color)
        y += bb[3] - bb[1] + 10

    # Subtitle
    sub = "\u0634\u0627\u0647\u062f \u0627\u0644\u0642\u0635\u0629 \u0627\u0644\u0643\u0627\u0645\u0644\u0629 \u25b6"
    bb = draw.textbbox((0, 0), sub, font=_get_font(32))
    x = (W - (bb[2] - bb[0])) // 2
    draw.text((x, H - 40), sub, font=_get_font(32), fill=(200, 200, 200))

    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(THUMB_DIR, f"thumb_{ts}.jpg")

    img.convert("RGB").save(output_path, quality=92)
    return output_path
