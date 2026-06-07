import os
import random
import subprocess
import tempfile
import urllib.request
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1280, 720
THUMB_DIR = "output/thumbnails"
os.makedirs(THUMB_DIR, exist_ok=True)

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/cairo/Cairo-Bold.ttf",
    "/usr/share/fonts/truetype/tajawal/Tajawal-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansArabic-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

CDN_FONTS = [
    (os.path.join(tempfile.gettempdir(), "NotoSansArabic-Bold.ttf"),
     "https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/fonts/NotoSansArabic/googlefonts/ttf/NotoSansArabic-Bold.ttf"),
]

_GOLD = (255, 215, 0)
_ORANGE = (255, 140, 0)
_RED = (220, 40, 40)
_WHITE = (255, 255, 255)

_FONT_CACHE = {}

def _get_font(size):
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    for p in FONT_CANDIDATES:
        if os.path.isfile(p) and os.path.getsize(p) > 1000:
            try:
                _FONT_CACHE[size] = ImageFont.truetype(p, size)
                return _FONT_CACHE[size]
            except Exception:
                pass
    try:
        out = subprocess.check_output(["fc-list", ":lang=ar", "-f", "%{file}\n"], stderr=subprocess.DEVNULL, timeout=5, encoding="utf-8")
        for line in out.strip().splitlines():
            f = line.strip()
            if f and os.path.isfile(f) and os.path.getsize(f) > 1000:
                _FONT_CACHE[size] = ImageFont.truetype(f, size)
                return _FONT_CACHE[size]
    except Exception:
        pass
    for path, url in CDN_FONTS:
        if os.path.isfile(path) and os.path.getsize(path) > 1000:
            try:
                _FONT_CACHE[size] = ImageFont.truetype(path, size)
                return _FONT_CACHE[size]
            except Exception:
                pass
    _FONT_CACHE[size] = ImageFont.load_default()
    return _FONT_CACHE[size]

def _extract_frame(video_path, time_sec=1.0):
    try:
        import subprocess as sp
        import numpy as np
        cmd = [
            "ffmpeg", "-ss", str(time_sec), "-i", video_path,
            "-vframes", "1", "-f", "image2pipe", "-vcodec", "png", "-"
        ]
        raw = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=10)
        return Image.open(Image.frombuffer("RGBA", None, raw, "raw", "RGBA", 0, 1)).convert("RGB")
    except Exception:
        pass
    try:
        from moviepy import VideoFileClip
        clip = VideoFileClip(video_path)
        frame = clip.get_frame(time_sec)
        clip.close()
        return Image.fromarray(frame)
    except Exception:
        return None

def _draw_gradient_overlay(draw, top_alpha=200, bottom_alpha=240):
    for y in range(H):
        if y < H // 2:
            a = int(top_alpha * (1 - y / (H // 2)))
            draw.line([(0, y), (W, y)], fill=(0, 0, 0, min(a, 240)))
        if y > H // 3:
            a = int(bottom_alpha * ((y - H // 3) / (H * 2 // 3)))
            draw.line([(0, y), (W, y)], fill=(0, 0, 0, min(a, 240)))

def _render_text_with_shadow(draw, text, font, x, y, color, shadow=(0, 0, 0, 220), shadow_offset=4):
    for ox, oy in [(shadow_offset, shadow_offset), (-shadow_offset, shadow_offset),
                   (shadow_offset, -shadow_offset), (-shadow_offset, -shadow_offset),
                   (0, shadow_offset), (shadow_offset, 0), (0, -shadow_offset), (-shadow_offset, 0)]:
        draw.text((x + ox, y + oy), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=color)

def _draw_cta_button(draw):
    btn_text = "   شاهد القصة كاملة   "
    font = _get_font(44)
    bb = draw.textbbox((0, 0), btn_text, font=font)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    btn_w = tw + 60
    btn_h = th + 30
    btn_x = (W - btn_w) // 2
    btn_y = H - btn_h - 40
    # Deep shadow under button
    draw.rounded_rectangle([(btn_x + 4, btn_y + 4), (btn_x + btn_w + 4, btn_y + btn_h + 4)], radius=btn_h // 2, fill=(0, 0, 0, 160))
    # Warm gradient-like button (orange-gold)
    draw.rounded_rectangle([(btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h)], radius=btn_h // 2, fill=(230, 160, 20))
    # Inner highlight
    draw.rounded_rectangle([(btn_x + 4, btn_y + 3), (btn_x + btn_w - 4, btn_y + btn_h - 3)], radius=btn_h // 2, fill=(255, 200, 40))
    tx = (W - tw) // 2
    ty = btn_y + (btn_h - th) // 2 - 2
    draw.text((tx + 1, ty + 1), btn_text, font=font, fill=(0, 0, 0, 120))
    draw.text((tx, ty), btn_text, font=font, fill=(20, 20, 20))

def _draw_title(draw, topic):
    if not topic:
        return False
    words = topic.split()
    lines = []
    current = ""
    font_main = _get_font(88)
    font_sub = _get_font(56)
    for w in words:
        test = current + " " + w if current else w
        bb = draw.textbbox((0, 0), test, font=font_main)
        if bb[2] - bb[0] < W - 140:
            current = test
        else:
            lines.append(current)
            current = w
    if current:
        lines.append(current)

    if not lines:
        return False

    total_h = 0
    for i, line in enumerate(lines[:3]):
        font = font_main if i == 0 else font_sub
        bb = draw.textbbox((0, 0), line, font=font)
        total_h += (bb[3] - bb[1]) + 20

    start_y = max(60, (H // 2) - total_h // 2 - 30)
    y = start_y

    for i, line in enumerate(lines[:3]):
        font = font_main if i == 0 else font_sub
        bb = draw.textbbox((0, 0), line, font=font)
        tw = bb[2] - bb[0]
        x = (W - tw) // 2

        if i == 0:
            color = (255, 215, 0)
            offset = 5
        else:
            color = (255, 255, 255)
            offset = 4

        _render_text_with_shadow(draw, line, font, x, y, color, shadow_offset=offset)
        y += bb[3] - bb[1] + 20

    return True

def _draw_curiosity_overlay(draw):
    """Draw a curiosity-gap visual: question mark badge at top-left."""
    qmark = "?"
    font = _get_font(120)
    bb = draw.textbbox((0, 0), qmark, font=font)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    pad = 25
    cx = 40
    cy = 50
    bw = tw + pad * 2
    bh = th + pad * 2
    # Circle behind question mark
    draw.ellipse([(cx + bw//4, cy), (cx + bw//4 + tw + 20, cy + th + 20)], fill=(220, 40, 40, 230))
    draw.text((cx + bw//4 + 10, cy + 8), qmark, font=font, fill=(255, 255, 255))

def _draw_season_badge(draw, season_name=""):
    if not season_name:
        return
    font = _get_font(26)
    text = season_name[:25]
    bb = draw.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    pad = 12
    bx = W - tw - pad * 3
    by = 25
    bw = tw + pad * 2
    bh = th + pad * 2
    draw.rounded_rectangle([(bx, by), (bx + bw, by + bh)], radius=bh // 2, fill=(0, 0, 0, 190))
    draw.text((bx + pad, by + pad - 2), text, font=font, fill=(255, 215, 0))

def _draw_accent_bar(draw):
    """Vibrant accent bar across the top edge."""
    bar_h = 8
    for x in range(W):
        px = x / W
        r = int(220 + px * 35)
        g = int(60 + px * 155)
        b = int(20 + px * (-10))
        for dy in range(bar_h):
            draw.point((x, dy), fill=(min(r, 255), min(g, 255), min(b, 255), 200))

def _sharpen_image(img):
    """Apply a subtle sharpening filter for more pop."""
    return img.filter(ImageFilter.UnsharpMask(radius=1, percent=50, threshold=2))

def generate_thumbnail(topic, output_path=None, season_name="", video_path=None):
    try:
        img = None
        if video_path and os.path.exists(video_path):
            frame = _extract_frame(video_path, time_sec=1.5)
            if frame is not None:
                img = frame.resize((W, H), Image.LANCZOS)
        if img is None:
            for root, dirs, files in os.walk("output/footage"):
                for f in sorted(files, key=lambda x: os.path.getmtime(os.path.join(root, x)), reverse=True):
                    if f.endswith(".mp4"):
                        frame = _extract_frame(os.path.join(root, f), time_sec=1.0)
                        if frame is not None:
                            img = frame.resize((W, H), Image.LANCZOS)
                            break
        if img is None:
            img = Image.new("RGB", (W, H), (20, 30, 50))
            draw = ImageDraw.Draw(img)
            for y in range(H):
                r = int(20 + (y / H) * 60)
                g = int(30 + (y / H) * 70)
                b = int(50 + (y / H) * 100)
                draw.line([(0, y), (W, y)], fill=(r, g, b))

        # Sharpen for more pop
        img = _sharpen_image(img)
        # Subtle blur (less than before - keeps detail visible)
        img = img.filter(ImageFilter.GaussianBlur(radius=1))
        # Increase contrast via curves approximation
        img = img.point(lambda p: min(255, int(p * 1.15)))
        # Composite overlay
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        _draw_gradient_overlay(overlay_draw)
        img_rgba = img.convert("RGBA")
        img_rgba = Image.alpha_composite(img_rgba, overlay)
        draw = ImageDraw.Draw(img_rgba)

        # Accent bar
        _draw_accent_bar(draw)
        # Curiosity question mark
        _draw_curiosity_overlay(draw)
        # Season badge
        if season_name:
            _draw_season_badge(draw, season_name)
        # Title
        _draw_title(draw, topic)
        # CTA button
        _draw_cta_button(draw)

        if output_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(THUMB_DIR, f"thumb_{ts}.jpg")
        img_rgba.convert("RGB").save(output_path, quality=97)
        return output_path
    except Exception as e:
        print(f"  \u26a0 \u0641\u0634\u0644 \u0627\u0644\u0635\u0648\u0631\u0629 \u0627\u0644\u0645\u0635\u063a\u0631\u0629: {e}")
        if output_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(THUMB_DIR, f"thumb_{ts}.jpg")
        img = Image.new("RGB", (W, H), (20, 30, 50))
        img.save(output_path, quality=85)
        return output_path
