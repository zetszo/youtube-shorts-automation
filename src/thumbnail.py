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
    """Extract a single frame from a video at given time. Returns PIL Image or None."""
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

def _draw_gradient_overlay(draw, top_alpha=180, bottom_alpha=220):
    """Draw top and bottom gradient overlays for text readability."""
    for y in range(H):
        # Top gradient (dark at top, fading down)
        if y < H // 2:
            a = int(top_alpha * (1 - y / (H // 2)))
            draw.line([(0, y), (W, y)], fill=(0, 0, 0, min(a, 220)))
        # Bottom gradient (dark at bottom, fading up)
        if y > H // 3:
            a = int(bottom_alpha * ((y - H // 3) / (H * 2 // 3)))
            draw.line([(0, y), (W, y)], fill=(0, 0, 0, min(a, 220)))

def _render_text_with_shadow(draw, text, font, x, y, color, shadow=(0, 0, 0, 200), shadow_offset=3):
    """Render text with a shadow for readability."""
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=color)

def _draw_cta_button(draw):
    """Draw a click-attracting CTA button at the bottom."""
    btn_text = "شاهد القصة كاملة ▶"
    font = _get_font(42)
    bb = draw.textbbox((0, 0), btn_text, font=font)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    btn_w = tw + 60
    btn_h = th + 30
    btn_x = (W - btn_w) // 2
    btn_y = H - btn_h - 30
    # Pill-shaped button
    draw.rounded_rectangle([(btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h)], radius=btn_h // 2, fill=(255, 215, 0, 230))
    # Shadow
    draw.rounded_rectangle([(btn_x + 3, btn_y + 3), (btn_x + btn_w + 3, btn_y + btn_h + 3)], radius=btn_h // 2, fill=(0, 0, 0, 100))
    draw.rounded_rectangle([(btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h)], radius=btn_h // 2, fill=(255, 215, 0, 240))
    tx = (W - tw) // 2
    ty = btn_y + (btn_h - th) // 2 - 2
    draw.text((tx + 1, ty + 1), btn_text, font=font, fill=(0, 0, 0, 100))
    draw.text((tx, ty), btn_text, font=font, fill=(30, 30, 30))

def _draw_title(draw, topic):
    """Draw the topic title centered with large font. Returns True if drawn."""
    if not topic:
        return False
    words = topic.split()
    font_main = _get_font(72)
    font_sub = _get_font(52)
    lines = []
    current = ""
    for w in words:
        test = current + " " + w if current else w
        bb = draw.textbbox((0, 0), test, font=font_main)
        if bb[2] - bb[0] < W - 160:
            current = test
        else:
            lines.append(current)
            current = w
    if current:
        lines.append(current)

    if not lines:
        return False

    # Calculate total height
    total_h = 0
    for i, line in enumerate(lines[:4]):
        font = font_main if i == 0 else font_sub
        bb = draw.textbbox((0, 0), line, font=font)
        total_h += (bb[3] - bb[1]) + 15

    start_y = max(60, (H // 2) - total_h // 2 - 40)
    y = start_y

    for i, line in enumerate(lines[:4]):
        font = font_main if i == 0 else font_sub
        sz = font_main if i == 0 else font_sub
        font = _get_font(72 if i == 0 else 52)
        bb = draw.textbbox((0, 0), line, font=font)
        tw = bb[2] - bb[0]
        x = (W - tw) // 2

        if i == 0:
            shadow_color = (0, 0, 0, 220)
            text_color = (255, 215, 0)
            offset = 4
        else:
            shadow_color = (0, 0, 0, 180)
            text_color = (255, 255, 255)
            offset = 3

        draw.text((x + offset, y + offset), line, font=font, fill=shadow_color)
        draw.text((x, y), line, font=font, fill=text_color)

        y += bb[3] - bb[1] + 15

    return True

def _draw_season_badge(draw, season_name=""):
    """Draw season/episode badge in top-right corner."""
    if not season_name:
        return
    font = _get_font(28)
    text = season_name[:25]
    bb = draw.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    pad = 14
    bx = W - tw - pad * 3
    by = 20
    bw = tw + pad * 2
    bh = th + pad * 2
    draw.rounded_rectangle([(bx, by), (bx + bw, by + bh)], radius=bh // 2, fill=(0, 0, 0, 180))
    draw.text((bx + pad, by + pad - 2), text, font=font, fill=(255, 215, 0))

def _draw_decorative_accent(draw):
    """Draw subtle decorative elements."""
    # Thin gold line at top
    for x in range(W // 4, W * 3 // 4):
        draw.point((x, 15), fill=(255, 215, 0, 120))
    # Thin gold line at bottom
    for x in range(W // 4, W * 3 // 4):
        draw.point((x, H - 15), fill=(255, 215, 0, 120))

def generate_thumbnail(topic, output_path=None, season_name="", video_path=None):
    """Generate a click-worthy thumbnail with footage background."""
    try:
        img = None
        # Try to use a frame from the video
        if video_path and os.path.exists(video_path):
            frame = _extract_frame(video_path, time_sec=2.0)
            if frame is not None:
                img = frame.resize((W, H), Image.LANCZOS)
        # Try footage files if video not available
        if img is None:
            for root, dirs, files in os.walk("output/footage"):
                for f in sorted(files, key=lambda x: os.path.getmtime(os.path.join(root, x)), reverse=True):
                    if f.endswith(".mp4"):
                        frame = _extract_frame(os.path.join(root, f), time_sec=1.0)
                        if frame is not None:
                            img = frame.resize((W, H), Image.LANCZOS)
                            break
        # Fallback: gradient
        if img is None:
            img = Image.new("RGB", (W, H), (20, 30, 50))
            draw = ImageDraw.Draw(img)
            for y in range(H):
                r = int(20 + (y / H) * 40)
                g = int(30 + (y / H) * 50)
                b = int(50 + (y / H) * 80)
                draw.line([(0, y), (W, y)], fill=(r, g, b))
        # Apply subtle blur for background
        img = img.filter(ImageFilter.GaussianBlur(radius=2))
        # Composite with overlay
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        _draw_gradient_overlay(overlay_draw)
        img_rgba = img.convert("RGBA")
        img_rgba = Image.alpha_composite(img_rgba, overlay)
        draw = ImageDraw.Draw(img_rgba)
        # Decorative accents
        _draw_decorative_accent(draw)
        # Season badge
        if season_name:
            _draw_season_badge(draw, season_name)
        # Title
        _draw_title(draw, topic)
        # CTA button
        _draw_cta_button(draw)
        # Save
        if output_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(THUMB_DIR, f"thumb_{ts}.jpg")
        img_rgba.convert("RGB").save(output_path, quality=95)
        return output_path
    except Exception as e:
        print(f"  ⚠ فشل الصورة المصغرة: {e}")
        # Ultimate fallback
        if output_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(THUMB_DIR, f"thumb_{ts}.jpg")
        img = Image.new("RGB", (W, H), (20, 30, 50))
        img.save(output_path, quality=85)
        return output_path
