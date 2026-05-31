import os
import re
import random
import urllib.request
import numpy as np
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from moviepy import (
    VideoFileClip, AudioFileClip, CompositeVideoClip,
    ImageClip, concatenate_videoclips, ColorClip
)
from config import VIDEO_WIDTH, VIDEO_HEIGHT

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _HAS_RESHAPER = True
except ImportError:
    _HAS_RESHAPER = False

FINAL_DIR = "output/final_videos"
os.makedirs(FINAL_DIR, exist_ok=True)

FONT_PATHS = [
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
    "/usr/share/fonts/truetype/tajawal/Tajawal-Bold.ttf",
    "/usr/share/fonts/truetype/cairo/Cairo-Bold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansArabic-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
_FONT_CACHE = None

STROKE_WIDTH = 6
BG_PAD = 40
BG_OPACITY = 0.55
SAFE_Y = 0.42

def _reshape(text: str) -> str:
    if not _HAS_RESHAPER:
        return text
    try:
        return get_display(arabic_reshaper.reshape(text), base_direction='R')
    except Exception:
        return text

def _ensure_font():
    global _FONT_CACHE
    if _FONT_CACHE:
        return _FONT_CACHE
    for p in FONT_PATHS:
        if os.path.exists(p):
            _FONT_CACHE = p
            return p
    local = "/tmp/NotoSansArabic-Bold.ttf"
    if not os.path.exists(local):
        urls = [
            "https://cdn.jsdelivr.net/gh/notofonts/notofonts.github.io@main/fonts/NotoSansArabic/googlefonts/ttf/NotoSansArabic-Bold.ttf",
        ]
        for url in urls:
            try:
                urllib.request.urlretrieve(url, local)
                if os.path.getsize(local) > 1000:
                    break
            except Exception:
                continue
    if os.path.exists(local) and os.path.getsize(local) > 1000:
        _FONT_CACHE = local
        return _FONT_CACHE
    _FONT_CACHE = None
    return None

def _load_font(size: int):
    path = _ensure_font()
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()

def _measure(text: str, font):
    m = Image.new("L", (1, 1), 0)
    d = ImageDraw.Draw(m)
    b = d.textbbox((0, 0), text, font=font, stroke_width=STROKE_WIDTH)
    return b[2] - b[0], b[3] - b[1], b[0], b[1]

def _wrap_lines(words):
    n = len(words)
    if n <= 2:
        return [words]
    if n == 3:
        split = 1 if random.random() < 0.5 else 2
        return [words[:split], words[split:]]
    if n == 4:
        return [words[:2], words[2:]]
    half = (n + 1) // 2
    return [words[:half], words[half:]]

def _render_line(line_words, font, fs, make_first_gold):
    reshaped = []
    offsets = []
    total_w = 0
    max_h = 0
    for i, w in enumerate(line_words):
        r = _reshape(w)
        if not r.strip():
            continue
        cw, ch, ox, oy = _measure(r, font)
        if cw < 4 or ch < 4:
            continue
        color = (255, 215, 0) if (i == 0 and make_first_gold) else (255, 255, 255)
        reshaped.append((r, color, cw, ch, ox, oy))
        total_w += cw + 10
        max_h = max(max_h, ch)

    if not reshaped:
        return None, 0, 0

    total_w -= 10
    total_w = max(total_w, 10)
    max_h = max(max_h, 10)

    line_img = Image.new("RGBA", (int(total_w + STROKE_WIDTH * 4), int(max_h + STROKE_WIDTH * 4)), (0, 0, 0, 0))
    li_w = total_w + STROKE_WIDTH * 4
    li_h = max_h + STROKE_WIDTH * 4

    x = li_w // 2 + total_w // 2
    for r_text, color, cw, ch, ox, oy in reshaped:
        word_img = Image.new("RGBA", (int(cw + STROKE_WIDTH * 2), int(ch + STROKE_WIDTH * 2)), (0, 0, 0, 0))
        wd = ImageDraw.Draw(word_img)
        wd.text(
            (STROKE_WIDTH - ox, STROKE_WIDTH - oy),
            r_text, font=font, fill=color + (255,),
            stroke_width=STROKE_WIDTH, stroke_fill=(0, 0, 0, 255),
        )
        x -= cw
        px = int(x + STROKE_WIDTH * 2 - (li_w // 2 - total_w // 2))
        py = int((li_h - ch) // 2 - oy)
        line_img.paste(word_img, (px, py), word_img)

    return line_img, li_w, li_h

def _render_segment_pil(text: str, font_size: int, is_hook: bool = False):
    words = [w for w in text.split() if w.strip()]
    if not words:
        return None

    font = _load_font(font_size)
    lines = _wrap_lines(words)

    rendered_lines = []
    line_widths = []
    line_heights = []

    for li, lw in enumerate(lines):
        img, w, h = _render_line(lw, font, font_size, make_first_gold=(li == 0))
        if img is None:
            continue
        rendered_lines.append(img)
        line_widths.append(w)
        line_heights.append(h)

    if not rendered_lines:
        return None

    ls = int(font_size * 0.25)
    max_w = max(line_widths)
    total_h = sum(line_heights) + (len(rendered_lines) - 1) * ls
    pad = BG_PAD

    bw = int(max_w + pad * 2)
    bh = int(total_h + pad * 2)

    bg = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg)
    bg_color = (180, 140, 20, 160) if is_hook else (0, 0, 0, 140)
    bg_draw.rounded_rectangle([(0, 0), (bw - 1, bh - 1)], radius=14, fill=bg_color)

    cy = (bh - total_h) // 2
    for i, (img, w, h) in enumerate(zip(rendered_lines, line_widths, line_heights)):
        cx = (bw - w) // 2
        bg.paste(img, (cx, cy), img)
        cy += h + LINE_SPACING

    return ImageClip(np.array(bg)).with_duration(1)

def create_video(script_data: dict, footage_clips: list) -> str:
    story = script_data["story"]
    audio_path = script_data["audio_file"]

    audio = AudioFileClip(audio_path)
    target = audio.duration

    bg_clips = []
    for c in footage_clips:
        try:
            clip = VideoFileClip(c["path"]).resized(new_size=(VIDEO_WIDTH, VIDEO_HEIGHT))
            bg_clips.append(clip)
        except Exception:
            pass

    if not bg_clips:
        background = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 30, 50)).with_duration(target)
    else:
        random.shuffle(bg_clips)
        parts = []
        remaining = target
        i = 0
        while remaining > 0.5 and bg_clips:
            clip = bg_clips[i % len(bg_clips)]
            dur = min(clip.duration, remaining)
            sub = clip.subclipped(0, dur).resized(new_size=(VIDEO_WIDTH, VIDEO_HEIGHT))
            if sub.duration < 1.0:
                i += 1
                continue
            parts.append(sub)
            remaining -= dur
            i += 1
        if not parts:
            parts = [ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 30, 50)).with_duration(target)]
        background = concatenate_videoclips(parts, method="compose")

    segments = _split_words(story, target)
    layers = []
    for idx, (text, start, dur) in enumerate(segments):
        wc = len(text.split())
        fs = 90 if wc <= 2 else 84 if wc <= 3 else 76
        seg = _render_segment_pil(text, fs, is_hook=(idx == 0))
        if seg is None:
            continue
        sh = seg.size[1]
        y_min = int(0.08 * VIDEO_HEIGHT)
        y_max = int(0.75 * VIDEO_HEIGHT)
        y_pos = int(SAFE_Y * VIDEO_HEIGHT - sh / 2)
        y_pos = max(y_min, min(y_pos, y_max))
        seg = seg.with_position(("center", y_pos)).with_duration(dur).with_start(start)
        layers.append(seg)

    final = CompositeVideoClip([background] + layers, size=(VIDEO_WIDTH, VIDEO_HEIGHT))
    final = final.with_audio(audio).with_duration(target)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(FINAL_DIR, f"shorts_{ts}_ar.mp4")
    final.write_videofile(out, fps=30, codec="libx264", audio_codec="aac", threads=2, preset="medium", logger=None)
    audio.close()
    final.close()

    script_data["video_file"] = out
    return out

def _split_words(text: str, total_duration: float) -> list:
    words = text.split()
    if len(words) <= 4:
        return [(text, 0, total_duration)]

    chunks = []
    i = 0
    while i < len(words):
        n = random.choices([3, 4], weights=[0.4, 0.6])[0]
        if i + n > len(words):
            n = len(words) - i
        chunks.append(" ".join(words[i:i + n]))
        i += n

    total_words = len(words)
    result = []
    current = 0
    for chunk in chunks:
        wc = len(chunk.split())
        dur = max(2.5, (wc / total_words) * total_duration)
        if current + dur > total_duration:
            dur = total_duration - current
        if dur > 1.2:
            result.append((chunk, current, dur))
            current += dur + 0.15

    if not result:
        result = [(text, 0, total_duration)]
    return result
