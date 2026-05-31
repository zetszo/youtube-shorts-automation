import os
import re
import random
import urllib.request
from datetime import datetime
from moviepy import (
    VideoFileClip, AudioFileClip, CompositeVideoClip,
    TextClip, concatenate_videoclips, ColorClip
)
from config import VIDEO_WIDTH, VIDEO_HEIGHT

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _HAS_ARABIC_RESHAPER = True
except ImportError:
    _HAS_ARABIC_RESHAPER = False

FINAL_DIR = "output/final_videos"
os.makedirs(FINAL_DIR, exist_ok=True)

FONT_PATHS = [
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
    "/usr/share/fonts/truetype/tajawal/Tajawal-Bold.ttf",
    "/usr/share/fonts/truetype/cairo/Cairo-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
]
FONT_FALLBACK = "DejaVu-Sans"
_FONT_CACHE = None

STROKE_WIDTH = 6
BG_PAD = 30
BG_OPACITY = 0.50
SAFE_Y = 0.42
MAX_WORDS_PER_SEGMENT = 3

def _reshape(text: str) -> str:
    if not _HAS_ARABIC_RESHAPER:
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
            "https://fonts.google.com/download?family=Noto+Sans+Arabic",
        ]
        for url in urls:
            try:
                urllib.request.urlretrieve(url, local)
                if os.path.exists(local):
                    break
            except Exception:
                continue
    _FONT_CACHE = local if os.path.exists(local) else FONT_FALLBACK
    return _FONT_CACHE

def _make_word_clip(word: str, font: str, size: int, color: str):
    t = _reshape(word)
    if not t.strip():
        return None, 0, 0
    try:
        clip = TextClip(
            text=t,
            font=font,
            font_size=size,
            color=color,
            stroke_color="black",
            stroke_width=STROKE_WIDTH,
            method="label",
        )
        w, h = clip.size
        if w < 2 or h < 2:
            return None, 0, 0
        return clip, w, h
    except Exception:
        return None, 0, 0

def _render_segment(text: str, font: str, font_size: int, is_hook: bool = False):
    words = [w for w in text.split() if w.strip()]
    if not words:
        return None, 0, 0

    clips = []
    total_w = 0
    max_h = 0
    for i, w in enumerate(words):
        color = "#FFD700" if i == 0 else "white"
        clip, cw, ch = _make_word_clip(w, font, font_size, color)
        if clip is None:
            continue
        clips.append((clip, cw, ch))
        total_w += cw + 10
        max_h = max(max_h, ch)

    if not clips:
        return None, 0, 0

    total_w -= 10
    total_w = max(total_w, 10)
    max_h = max(max_h, 10)
    pad = BG_PAD

    cx = VIDEO_WIDTH // 2
    x = cx + total_w // 2
    layer_clips = []
    for clip, cw, ch in clips:
        x -= cw
        layer_clips.append(clip.with_position((int(x), 0)))
        x -= 10

    bw = int(total_w + pad * 2)
    bh = int(max_h + pad * 2)
    bg_color = (180, 140, 20) if is_hook else (0, 0, 0)
    bg_op = 0.60 if is_hook else BG_OPACITY
    bg = ColorClip(size=(bw, bh), color=bg_color)
    bg = bg.with_opacity(bg_op).with_position((int(cx - total_w / 2 - pad), 0))

    seg = CompositeVideoClip([bg] + layer_clips)
    return seg, bw, bh

def create_video(script_data: dict, footage_clips: list) -> str:
    story = script_data["story"]
    audio_path = script_data["audio_file"]

    audio = AudioFileClip(audio_path)
    target = audio.duration

    bg = []
    for c in footage_clips:
        try:
            clip = VideoFileClip(c["path"]).resized(new_size=(VIDEO_WIDTH, VIDEO_HEIGHT))
            bg.append(clip)
        except Exception:
            pass

    if not bg:
        bg = [ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 30, 50)).with_duration(target)]
        background = bg[0]
    else:
        random.shuffle(bg)
        parts = []
        remaining = target
        i = 0
        while remaining > 0.5 and bg:
            clip = bg[i % len(bg)]
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
    font = _ensure_font()

    layers = []
    for idx, (text, start, dur) in enumerate(segments):
        wc = len(text.split())
        fs = 88 if wc <= 2 else 80 if wc == 3 else 72
        is_hook = idx == 0
        seg, sw, sh = _render_segment(text, font, fs, is_hook)
        if seg is None or sh < 2:
            continue
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
    if len(words) <= MAX_WORDS_PER_SEGMENT:
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
