import os
import re
import sys
import subprocess
import tempfile
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
    print("WARNING: arabic_reshaper / python-bidi not installed", file=sys.stderr)

FINAL_DIR = "output/final_videos"
os.makedirs(FINAL_DIR, exist_ok=True)

_FONT_SIZE = 82
_STROKE = 6
_PAD = 28
_GOLD = (255, 215, 0)
_WHITE = (255, 255, 255)

EXPORT_FPS = 30
EXPORT_BITRATE = "8000k"

_WORD_CACHE = {}
_FONT_CACHE = None

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
    (os.path.join(tempfile.gettempdir(), "Cairo-Bold.ttf"),
     "https://raw.githubusercontent.com/Gue3bara/Cairo/main/fonts/Cairo-Bold.ttf"),
    (os.path.join(tempfile.gettempdir(), "NotoSansArabic-Bold.ttf"),
     "https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/fonts/NotoSansArabic/googlefonts/ttf/NotoSansArabic-Bold.ttf"),
]

def log(msg):
    print(f"[VIDEO] {msg}", file=sys.stderr)

# ───────── font detection ─────────

def _find_arabic_font():
    for p in FONT_CANDIDATES:
        if os.path.isfile(p) and os.path.getsize(p) > 1000:
            log(f"font found: {p}")
            return p

    # Try fc-list on Linux
    try:
        out = subprocess.check_output(
            ["fc-list", ":lang=ar", "-f", "%{file}\n"],
            stderr=subprocess.DEVNULL, timeout=5, encoding="utf-8"
        )
        for line in out.strip().splitlines():
            f = line.strip()
            if f and os.path.isfile(f) and os.path.getsize(f) > 1000:
                log(f"font from fc-list: {f}")
                return f
    except Exception:
        pass

    # Try downloading
    for path, url in CDN_FONTS:
        if os.path.isfile(path) and os.path.getsize(path) > 1000:
            log(f"font from cache: {path}")
            return path
        try:
            log(f"downloading font: {url[:60]}...")
            urllib.request.urlretrieve(url, path)
            if os.path.getsize(path) > 1000:
                log(f"font downloaded: {path}")
                return path
        except Exception as e:
            log(f"download failed: {e}")

    log("NO ARABIC FONT FOUND — text will be invisible!")
    return None

def load_font(size):
    global _FONT_CACHE
    if _FONT_CACHE is None:
        _FONT_CACHE = _find_arabic_font()
    if _FONT_CACHE:
        try:
            return ImageFont.truetype(_FONT_CACHE, size)
        except Exception as e:
            log(f"failed to load {_FONT_CACHE}: {e}")
    return ImageFont.load_default()

# ───────── text shaping ─────────

def reshape(text):
    if not _CAN_REShAPE:
        return text
    try:
        return get_display(arabic_reshaper.reshape(text), base_direction='R')
    except Exception:
        return text

def clean_diac(text):
    return re.sub(r'[ًٌٍَُِّْ]', '', text)

# ───────── word rendering ─────────

def _render_word(text, color):
    key = (text, color)
    if key in _WORD_CACHE:
        return _WORD_CACHE[key]

    font = load_font(_FONT_SIZE)
    r = reshape(text)
    if not r.strip():
        _WORD_CACHE[key] = None
        return None

    m = Image.new("L", (1, 1), 0)
    d = ImageDraw.Draw(m)
    bb = d.textbbox((0, 0), r, font=font, stroke_width=_STROKE)
    cw, ch = bb[2] - bb[0], bb[3] - bb[1]

    if cw < 4 or ch < 4:
        _WORD_CACHE[key] = None
        return None

    iw = int(cw + _STROKE * 5)
    ih = int(ch + _STROKE * 5)
    img = Image.new("RGBA", (iw, ih), (0, 0, 0, 0))

    shadow = Image.new("RGBA", (iw, ih), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.text(
        (_STROKE * 2 - bb[0] + 3, _STROKE * 2 - bb[1] + 3),
        r, font=font, fill=(0, 0, 0, 60),
        stroke_width=_STROKE, stroke_fill=(0, 0, 0, 60),
    )
    img = Image.alpha_composite(img, shadow)

    wd = ImageDraw.Draw(img)
    wd.text(
        (_STROKE * 2 - bb[0], _STROKE * 2 - bb[1]),
        r, font=font, fill=color + (255,),
        stroke_width=_STROKE, stroke_fill=(0, 0, 0, 255),
    )
    _WORD_CACHE[key] = img
    return img

# ───────── subtitle layout & render ─────────

def _layout(words):
    gap = 14
    max_w = int(VIDEO_WIDTH * 0.82)
    font = load_font(_FONT_SIZE)

    items = []
    for w in words:
        r = reshape(w)
        if not r.strip():
            items.append((w, 0, 0))
            continue
        m = Image.new("L", (1, 1), 0)
        d = ImageDraw.Draw(m)
        bb = d.textbbox((0, 0), r, font=font, stroke_width=_STROKE)
        iw = bb[2] - bb[0] + _STROKE * 4
        ih = bb[3] - bb[1] + _STROKE * 4
        items.append((w, iw, ih))

    total_w = sum(it[1] for it in items) + gap * (len(items) - 1)
    line_h = max((it[2] for it in items), default=0)

    if total_w <= max_w:
        x = total_w
        out = []
        for w, iw, ih in items:
            x -= iw
            out.append((w, x, 0, iw, ih))
            x -= gap
        return out

    half = max(len(words) // 2, 1)
    ls = int(_FONT_SIZE * 0.25)
    out = []
    for row, start in enumerate([0, half]):
        line = items[start:start + half]
        if not line:
            continue
        tw = sum(it[1] for it in line) + gap * (len(line) - 1)
        x = tw
        for w, iw, ih in line:
            x -= iw
            out.append((w, x, row * (line_h + ls), iw, ih))
            x -= gap
    return out

def render_subtitle(words, active_idx):
    pos = _layout(words)
    if not pos:
        log("render_subtitle: empty layout")
        return None

    min_x = min(x for _, x, _, _, _ in pos)
    max_x = max(x + w for _, x, _, w, _ in pos)
    max_y = max(y + h for _, _, y, _, h in pos)
    bw = int(max(max_x - min_x + _PAD * 2, 40))
    bh = int(max(max_y + _PAD * 2, 40))

    bg = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    bgd = ImageDraw.Draw(bg)
    bgd.rounded_rectangle([(0, 0), (bw - 1, bh - 1)], radius=16, fill=(0, 0, 0, 140))

    painted = 0
    for i, (w, x, y, _, _) in enumerate(pos):
        if i > active_idx:
            continue
        color = _GOLD if i == active_idx else _WHITE
        img = _render_word(w, color)
        if img is None:
            continue
        px = int(x - min_x + _PAD)
        py = int(y + _PAD)
        bg.paste(img, (px, py), img)
        painted += 1

    if painted == 0:
        log(f"render_subtitle: 0 words painted for {len(words)} words")
        return None
    return bg

# ───────── timestamp pipeline ─────────

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
    if not timestamps:
        return []
    import random
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

def build_segment_clips(seg, total_dur):
    words = seg["words"]
    times = seg["times"]
    clips = []

    for i in range(len(words)):
        st = times[i][0]
        dur = (times[i + 1][0] - st) if i < len(words) - 1 else (seg["end"] - st)
        if dur < 0.08:
            continue
        img = render_subtitle(words, active_idx=i)
        if img is None:
            continue
        bh = img.size[1]
        y = int(0.42 * VIDEO_HEIGHT - bh / 2)
        y = max(int(0.08 * VIDEO_HEIGHT), min(y, int(0.75 * VIDEO_HEIGHT)))
        clips.append(ImageClip(np.array(img)).with_duration(dur).with_start(st).with_position(("center", y)))

    # final quiet frame: all white
    final_st = times[-1][1] if times else seg["end"]
    final_dur = max(total_dur - final_st, 0.2)
    img = render_subtitle(words, active_idx=len(words))
    if img is not None:
        bh = img.size[1]
        y = int(0.42 * VIDEO_HEIGHT - bh / 2)
        y = max(int(0.08 * VIDEO_HEIGHT), min(y, int(0.75 * VIDEO_HEIGHT)))
        clips.append(ImageClip(np.array(img)).with_duration(final_dur).with_start(final_st).with_position(("center", y)))
    return clips

# ───────── main montage ─────────

def create_video(script_data, footage_clips):
    import random
    story = script_data["story"]
    audio = AudioFileClip(script_data["audio_file"])
    total = min(audio.duration, 60)

    log(f"audio duration: {audio.duration:.2f}s, capped: {total:.2f}s")
    log(f"story length: {len(story.split())} words")

    parts = []
    for c in footage_clips:
        try:
            clip = VideoFileClip(c["path"]).resized(new_size=(VIDEO_WIDTH, VIDEO_HEIGHT))
            parts.append(clip)
        except Exception as e:
            log(f"footage skip: {e}")

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
    log(f"word timestamps: {len(timestamps)}")

    overlays = []
    if timestamps:
        segs = group_segments(timestamps)
        log(f"segments: {len(segs)}")
        for seg in segs:
            clips = build_segment_clips(seg, total)
            log(f"  seg {' '.join(seg['words'][:3])}... -> {len(clips)} clips")
            overlays.extend(clips)
    else:
        log("NO TIMESTAMPS — no subtitle overlays")

    if not overlays:
        log("WARNING: no overlay clips — subtitles will be INVISIBLE")

    final = CompositeVideoClip([bg] + overlays, size=(VIDEO_WIDTH, VIDEO_HEIGHT))
    final = final.with_audio(audio).with_duration(total)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(FINAL_DIR, f"shorts_{ts}_ar.mp4")
    log(f"rendering: {out}")
    final.write_videofile(out, fps=EXPORT_FPS, codec="libx264", audio_codec="aac", bitrate=EXPORT_BITRATE, threads=2, preset="medium", logger=None)
    audio.close()
    final.close()
    script_data["video_file"] = out
    log("done")
    return out
