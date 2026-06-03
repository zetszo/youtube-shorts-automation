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
    _CAN_REShAPE = True
except ImportError:
    _CAN_REShAPE = False

FINAL_DIR = "output/final_videos"
os.makedirs(FINAL_DIR, exist_ok=True)

_FONT_PATHS = [
    "/usr/share/fonts/truetype/cairo/Cairo-Bold.ttf",
    "/usr/share/fonts/truetype/tajawal/Tajawal-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansArabic-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

_FONT_CACHE = None
_WORD_CACHE = {}

_FONT_SIZE = 86
_STROKE = 6
_PAD = 30
_GOLD = (255, 215, 0)
_WHITE = (255, 255, 255)
_SEG_GAP = 0.08

EXPORT_FPS = 30
EXPORT_BITRATE = "8000k"

# ───────── helpers ─────────

def reshape(text):
    if not _CAN_REShAPE:
        return text
    try:
        return get_display(arabic_reshaper.reshape(text), base_direction='R')
    except Exception:
        return text

def load_font(size):
    global _FONT_CACHE
    if _FONT_CACHE is None:
        for p in _FONT_PATHS:
            if os.path.exists(p):
                _FONT_CACHE = p
                break
        if _FONT_CACHE is None:
            for path, url in [
                ("/tmp/Cairo-Bold.ttf", "https://cdn.jsdelivr.net/gh/Gue3bara/Cairo@main/fonts/Cairo-Bold.ttf"),
                ("/tmp/NotoSansArabic-Bold.ttf", "https://cdn.jsdelivr.net/gh/notofonts/notofonts.github.io@main/fonts/NotoSansArabic/googlefonts/ttf/NotoSansArabic-Bold.ttf"),
            ]:
                if os.path.exists(path) and os.path.getsize(path) > 1000:
                    _FONT_CACHE = path
                    break
                try:
                    urllib.request.urlretrieve(url, path)
                    if os.path.getsize(path) > 1000:
                        _FONT_CACHE = path
                        break
                except Exception:
                    continue
    if _FONT_CACHE:
        try:
            return ImageFont.truetype(_FONT_CACHE, size)
        except Exception:
            pass
    return ImageFont.load_default()

def text_bbox(text, font):
    m = Image.new("L", (1, 1), 0)
    d = ImageDraw.Draw(m)
    b = d.textbbox((0, 0), text, font=font, stroke_width=_STROKE)
    return b[2] - b[0], b[3] - b[1], b[0], b[1]

def clean_diac(text):
    return re.sub(r'[ًٌٍَُِّْ]', '', text)

# ───────── word rendering ─────────

def render_word_img(text, color, font):
    r = reshape(text)
    if not r.strip():
        return None
    cw, ch, ox, oy = text_bbox(r, font)
    if cw < 4 or ch < 4:
        return None

    iw = int(cw + _STROKE * 5)
    ih = int(ch + _STROKE * 5)
    img = Image.new("RGBA", (iw, ih), (0, 0, 0, 0))

    sh = Image.new("RGBA", (iw, ih), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.text(
        (_STROKE * 2 - ox + 3, _STROKE * 2 - oy + 3),
        r, font=font, fill=(0, 0, 0, 60),
        stroke_width=_STROKE, stroke_fill=(0, 0, 0, 60),
    )
    img = Image.alpha_composite(img, sh)

    wd = ImageDraw.Draw(img)
    wd.text(
        (_STROKE * 2 - ox, _STROKE * 2 - oy),
        r, font=font, fill=color + (255,),
        stroke_width=_STROKE, stroke_fill=(0, 0, 0, 255),
    )
    return img

def get_word_img(word, color):
    key = (word, color)
    if key in _WORD_CACHE:
        return _WORD_CACHE[key]
    font = load_font(_FONT_SIZE)
    img = render_word_img(word, color, font)
    _WORD_CACHE[key] = img
    return img

# ───────── layout: position words in a subtitle block ─────────

def measure_word(word):
    img = get_word_img(word, _WHITE)
    if img is None:
        return 0, 0
    return img.width, img.height

def layout_segment(words):
    """Return list of (word, x, y, w, h) positioned RTL, wrapping to 2 lines max."""
    gap = 12
    max_w = int(VIDEO_WIDTH * 0.85)
    line_h = 0
    positions = []

    cx = max_w
    cy = 0
    for w in reversed(words):
        iw, ih = measure_word(w)
        if iw <= 0:
            positions.append((w, 0, 0, 0, 0))
            continue
        if cx - gap - iw < 0:
            cx = max_w
            cy += line_h + int(_FONT_SIZE * 0.3)
            line_h = 0
        cx -= iw
        positions.append((w, cx, cy, iw, ih))
        cx -= gap
        line_h = max(line_h, ih)

    return [(w, x, abs(y)) for w, x, y, iw, ih in positions]

# ───────── render subtitle state ─────────

def render_subtitle(words, active_idx):
    font = load_font(_FONT_SIZE)
    pos = layout_segment(words)
    if not pos:
        return None

    box_w = max(x + w for _, x, _, w in pos) + _PAD * 2
    box_h = max(y + h for _, _, y, _, h in pos) + _PAD * 2
    box_w = max(box_w, 60)
    box_h = max(box_h, 60)

    bg = Image.new("RGBA", (int(box_w), int(box_h)), (0, 0, 0, 0))
    bgd = ImageDraw.Draw(bg)
    bgd.rounded_rectangle([(0, 0), (box_w - 1, box_h - 1)], radius=16, fill=(0, 0, 0, 140))

    for i, (w, x, y, _, _) in enumerate(pos):
        if i > active_idx:
            continue
        color = _GOLD if i == active_idx else _WHITE
        img = get_word_img(w, color)
        if img is None:
            continue
        px = int(x + _PAD - box_w // 2 + VIDEO_WIDTH * 0.425)
        py = int(y + _PAD)
        bg.paste(img, (px, py), img)

    return bg

# ───────── build word timestamps ─────────

def build_word_timestamps(text, word_timings):
    tw = [w for w in (word_timings or []) if w["text"].strip() and any(c.isalpha() for c in w["text"])]
    if not tw:
        return []
    out = []
    for w in tw:
        cleaned = clean_diac(w["text"])
        if cleaned:
            out.append({"word": cleaned, "start": w["start"], "end": w["end"]})
    return out

def group_segments(timestamps):
    """Group word timestamps into segments of 4-6 words at natural breaks."""
    if not timestamps:
        return []
    segs = []
    i = 0
    while i < len(timestamps):
        n = min(random.randint(4, 6), len(timestamps) - i)
        group = timestamps[i:i+n]
        segs.append({
            "words": [t["word"] for t in group],
            "times": [(t["start"], t["end"]) for t in group],
            "start": group[0]["start"],
            "end": group[-1]["end"],
        })
        i += n
    return segs

# ───────── build clips for one segment ─────────

def build_segment_clips(seg, total_dur):
    words = seg["words"]
    times = seg["times"]
    clips = []

    for i in range(len(words)):
        st = times[i][0]
        if i < len(words) - 1:
            dur = times[i + 1][0] - st
        else:
            dur = seg["end"] - st
        if dur < 0.08:
            continue

        img = render_subtitle(words, active_idx=i)
        if img is None:
            continue
        bw, bh = img.size
        y = int(0.42 * VIDEO_HEIGHT - bh / 2)
        y = max(int(0.08 * VIDEO_HEIGHT), min(y, int(0.75 * VIDEO_HEIGHT)))

        clip = ImageClip(np.array(img)).with_duration(dur).with_start(st)
        clip = clip.with_position(("center", y))
        clips.append(clip)

    # final state: all words white
    final_st = times[-1][1] if times else seg["end"]
    final_dur = max(total_dur - final_st, 0.2)
    img = render_subtitle(words, active_idx=len(words))
    if img is not None:
        bw, bh = img.size
        y = int(0.42 * VIDEO_HEIGHT - bh / 2)
        y = max(int(0.08 * VIDEO_HEIGHT), min(y, int(0.75 * VIDEO_HEIGHT)))
        clip = ImageClip(np.array(img)).with_duration(final_dur).with_start(final_st)
        clip = clip.with_position(("center", y))
        clips.append(clip)

    return clips

# ───────── main ─────────

def create_video(script_data, footage_clips):
    import random
    story = script_data["story"]
    audio = AudioFileClip(script_data["audio_file"])
    total = min(audio.duration, 60)

    parts = []
    for c in footage_clips:
        try:
            clip = VideoFileClip(c["path"]).resized(new_size=(VIDEO_WIDTH, VIDEO_HEIGHT))
            parts.append(clip)
        except Exception:
            pass

    if not parts:
        bg = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 30, 50)).with_duration(total)
    else:
        random.shuffle(parts)
        clips = []
        remain = total
        i = 0
        while remain > 0.5 and parts:
            clip = parts[i % len(parts)]
            dur = min(clip.duration, remain)
            sub = clip.subclipped(0, dur).resized(new_size=(VIDEO_WIDTH, VIDEO_HEIGHT))
            if sub.duration < 1.0:
                i += 1
                continue
            clips.append(sub)
            remain -= dur
            i += 1
        bg = concatenate_videoclips(clips, method="compose") if clips else \
            ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 30, 50)).with_duration(total)

    timestamps = build_word_timestamps(story, script_data.get("word_timings", []))
    if timestamps:
        segs = group_segments(timestamps)
        overlays = []
        for seg in segs:
            overlays.extend(build_segment_clips(seg, total))
    else:
        overlays = []

    final = CompositeVideoClip([bg] + overlays, size=(VIDEO_WIDTH, VIDEO_HEIGHT))
    final = final.with_audio(audio).with_duration(total)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(FINAL_DIR, f"shorts_{ts}_ar.mp4")
    final.write_videofile(out, fps=EXPORT_FPS, codec="libx264", audio_codec="aac", bitrate=EXPORT_BITRATE, threads=2, preset="medium", logger=None)
    audio.close()
    final.close()
    script_data["video_file"] = out
    return out
