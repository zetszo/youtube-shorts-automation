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
BG_PAD = 30
BG_OPACITY = 0.50
SAFE_Y = 0.42

def _reshape(text: str) -> str:
    if not _HAS_RESHAPER:
        return text
    try:
        return get_display(arabic_reshaper.reshape(text))
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

def _render_segment_pil(text: str, font_size: int, is_hook: bool = False):
    words = [w for w in text.split() if w.strip()]
    if not words:
        return None

    font = _load_font(font_size)
    pad = BG_PAD

    word_data = []
    for i, w in enumerate(words):
        reshaped = _reshape(w)
        if not reshaped.strip():
            continue
        color = (255, 215, 0) if i == 0 else (255, 255, 255)
        mask = Image.new("L", (1, 1), 0)
        draw = ImageDraw.Draw(mask)
        bbox = draw.textbbox((0, 0), reshaped, font=font, stroke_width=STROKE_WIDTH)
        cw = bbox[2] - bbox[0]
        ch = bbox[3] - bbox[1]
        if cw < 4 or ch < 4:
            continue
        off_x = bbox[0]
        off_y = bbox[1]
        word_data.append((reshaped, color, cw, ch, off_x, off_y))

    if not word_data:
        return None

    spacing = 10
    total_w = sum(d[2] for d in word_data) + (len(word_data) - 1) * spacing
    max_h = max(d[3] for d in word_data)
    total_w = max(total_w, 10)
    max_h = max(max_h, 10)

    bw = int(total_w + pad * 2)
    bh = int(max_h + pad * 2)

    bg = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg)
    bg_color = (180, 140, 20, 153) if is_hook else (0, 0, 0, 128)
    bg_draw.rounded_rectangle([(0, 0), (bw - 1, bh - 1)], radius=12, fill=bg_color)

    cx = bw // 2
    x = cx + total_w // 2
    for reshaped, color, cw, ch, off_x, off_y in word_data:
        img_w = cw + STROKE_WIDTH * 2
        img_h = ch + STROKE_WIDTH * 2
        word_img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        wdraw = ImageDraw.Draw(word_img)
        wdraw.text(
            (STROKE_WIDTH - off_x, STROKE_WIDTH - off_y),
            reshaped, font=font, fill=color + (255,),
            stroke_width=STROKE_WIDTH, stroke_fill=(0, 0, 0, 255),
        )
        x -= cw
        paste_x = int(x + pad - (cx - total_w // 2))
        paste_y = int((bh - ch) // 2 - off_y)
        bg.paste(word_img, (paste_x, paste_y), word_img)

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
        fs = 88 if wc <= 2 else 80 if wc == 3 else 72
        seg = _render_segment_pil(text, fs, is_hook=(idx == 0))
        if seg is None:
            continue
        sh = seg.size[1]
        y_pos = int(SAFE_Y * VIDEO_HEIGHT - sh / 2)
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
    if len(words) <= 3:
        return [(text, 0, total_duration)]

    chunks = []
    i = 0
    while i < len(words):
        n = 2 if random.random() < 0.4 else 3
        if i + n > len(words):
            n = len(words) - i
        chunks.append(" ".join(words[i:i + n]))
        i += n

    total_words = len(words)
    result = []
    current = 0
    for chunk in chunks:
        wc = len(chunk.split())
        dur = max(2.0, (wc / total_words) * total_duration)
        if current + dur > total_duration:
            dur = total_duration - current
        if dur > 0.8:
            result.append((chunk, current, dur))
            current += dur

    if not result:
        result = [(text, 0, total_duration)]
    return result
