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

FINAL_DIR = "output/final_videos"
os.makedirs(FINAL_DIR, exist_ok=True)

EXPORT_FPS = 30
EXPORT_BITRATE = "8000k"

# ─── visual constants ───
_SCALE = min(VIDEO_WIDTH / 1080, VIDEO_HEIGHT / 1920)
FONT_SIZE = int(110 * _SCALE)
STROKE_W = 8
PAD_X = int(36 * _SCALE)
PAD_Y = int(28 * _SCALE)
WORD_GAP = int(14 * _SCALE)
LINE_SPACE = int(FONT_SIZE * 0.3)
SAFE_Y = 0.45
MAX_WIDTH_RATIO = 0.78
BG_ALPHA = 140
RADIUS = int(20 * _SCALE)
POP_SCALE = 1.08
POP_DUR = 0.25
GROUP_MIN = 3
GROUP_MAX = 5

_GOLD = (255, 215, 0)
_WHITE = (255, 255, 255)

_WORD_CACHE = {}
_FONT_CACHE = None
_MAX_W = int(VIDEO_WIDTH * MAX_WIDTH_RATIO)

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

# ─── font ───

def _find_font():
    for p in FONT_CANDIDATES:
        if os.path.isfile(p) and os.path.getsize(p) > 1000:
            log(f"font: {p}")
            return p
    try:
        out = subprocess.check_output(["fc-list", ":lang=ar", "-f", "%{file}\n"], stderr=subprocess.DEVNULL, timeout=5, encoding="utf-8")
        for line in out.strip().splitlines():
            f = line.strip()
            if f and os.path.isfile(f) and os.path.getsize(f) > 1000:
                log(f"font: {f}")
                return f
    except Exception:
        pass
    for path, url in CDN_FONTS:
        if os.path.isfile(path) and os.path.getsize(path) > 1000:
            log(f"font cached: {path}")
            return path
        try:
            log(f"downloading font...")
            urllib.request.urlretrieve(url, path)
            if os.path.getsize(path) > 1000:
                log(f"font downloaded: {path}")
                return path
        except Exception as e:
            log(f"download fail: {e}")
    log("NO ARABIC FONT!")
    return None

def get_font(size=None):
    global _FONT_CACHE
    if _FONT_CACHE is None:
        _FONT_CACHE = _find_font()
    p = _FONT_CACHE
    s = size or FONT_SIZE
    if p:
        try:
            return ImageFont.truetype(p, s)
        except Exception:
            pass
    return ImageFont.load_default()

# ─── text shaping ───

def reshape(text):
    if not _CAN_REShAPE:
        return text
    try:
        return get_display(arabic_reshaper.reshape(text), base_direction='R')
    except Exception:
        return text

def clean_diac(text):
    return re.sub(r'[ًٌٍَُِّْ]', '', text)

# ─── measure ───

def _measure(r, font):
    m = Image.new("L", (1, 1), 0)
    d = ImageDraw.Draw(m)
    bb = d.textbbox((0, 0), r, font=font, stroke_width=STROKE_W)
    return bb[2] - bb[0], bb[3] - bb[1], bb[0], bb[1]

# ─── word rendering ───

def _render_word(text, color):
    key = (text, color)
    if key in _WORD_CACHE:
        return _WORD_CACHE[key]
    font = get_font()
    r = reshape(text)
    if not r.strip():
        _WORD_CACHE[key] = None
        return None
    cw, ch, ox, oy = _measure(r, font)
    if cw < 4 or ch < 4:
        _WORD_CACHE[key] = None
        return None
    iw = int(cw + STROKE_W * 6)
    ih = int(ch + STROKE_W * 6)
    img = Image.new("RGBA", (iw, ih), (0, 0, 0, 0))
    # shadow
    sh = Image.new("RGBA", (iw, ih), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.text((STROKE_W * 2 - ox + 3, STROKE_W * 2 - oy + 3), r, font=font, fill=(0, 0, 0, 60), stroke_width=STROKE_W, stroke_fill=(0, 0, 0, 60))
    img = Image.alpha_composite(img, sh)
    # main
    wd = ImageDraw.Draw(img)
    wd.text((STROKE_W * 2 - ox, STROKE_W * 2 - oy), r, font=font, fill=color + (255,), stroke_width=STROKE_W, stroke_fill=(0, 0, 0, 255))
    _WORD_CACHE[key] = img
    return img

# ─── layout ───

def _layout(words):
    font = get_font()
    items = []
    for w in words:
        r = reshape(w)
        if not r.strip():
            items.append((w, 0, 0))
            continue
        cw, ch, _, _ = _measure(r, font)
        iw = cw + STROKE_W * 4
        ih = ch + STROKE_W * 4
        items.append((w, iw, ih))

    total_w = sum(it[1] for it in items) + WORD_GAP * (len(items) - 1)
    line_h = max((it[2] for it in items), default=0)

    if total_w <= _MAX_W:
        x = total_w
        out = []
        for w, iw, ih in items:
            x -= iw
            out.append((w, x, 0, iw, ih))
            x -= WORD_GAP
        return out

    half = max(len(words) // 2, 1)
    out = []
    for row, start in enumerate([0, half]):
        line = items[start:start + half]
        if not line:
            continue
        tw = sum(it[1] for it in line) + WORD_GAP * (len(line) - 1)
        x = tw
        for w, iw, ih in line:
            x -= iw
            out.append((w, x, row * (line_h + LINE_SPACE), iw, ih))
            x -= WORD_GAP
    return out

# ─── render subtitle frame ───

def render_subtitle(words, active_idx):
    pos = _layout(words)
    if not pos:
        return None

    min_x = min(x for _, x, _, _, _ in pos)
    bw = int(max(x + w for _, x, _, w, _ in pos) - min_x + PAD_X * 2)
    bh = int(max(y + h for _, _, y, _, h in pos) + PAD_Y * 2)
    bw = max(bw, 40)
    bh = max(bh, 40)

    bg = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    bgd = ImageDraw.Draw(bg)
    bgd.rounded_rectangle([(0, 0), (bw - 1, bh - 1)], radius=RADIUS, fill=(0, 0, 0, BG_ALPHA))

    painted = 0
    for i, (w, x, y, _, _) in enumerate(pos):
        if i > active_idx:
            continue
        color = _GOLD if i == active_idx else _WHITE
        img = _render_word(w, color)
        if img is None:
            continue
        px = int(x - min_x + PAD_X)
        py = int(y + PAD_Y)
        bg.paste(img, (px, py), img)
        painted += 1

    if painted == 0:
        return None
    return bg

# ─── segment building ───

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
        n = min(random.randint(GROUP_MIN, GROUP_MAX), len(timestamps) - i)
        group = timestamps[i:i+n]
        segs.append({
            "words": [t["word"] for t in group],
            "times": [(t["start"], t["end"]) for t in group],
            "start": group[0]["start"],
            "end": group[-1]["end"],
        })
        i += n
    return segs

def _make_clip(words, active_idx, st, dur, y_pos):
    img = render_subtitle(words, active_idx)
    if img is None:
        return None
    clip = ImageClip(np.array(img)).with_duration(dur).with_start(st).with_position(("center", y_pos))

    def pop(t):
        if t < POP_DUR:
            return 1 + (POP_SCALE - 1) * max(0, 1 - t / POP_DUR)
        return 1.0

    return clip.resized(pop)

def build_segment_clips(seg, total_dur):
    words = seg["words"]
    times = seg["times"]
    clips = []

    # determine y position from a sample render
    sample = render_subtitle(words, 0)
    if sample is None:
        return clips
    bh = sample.size[1]
    y = int(SAFE_Y * VIDEO_HEIGHT - bh / 2)
    y = max(int(0.08 * VIDEO_HEIGHT), min(y, int(0.75 * VIDEO_HEIGHT)))

    for i in range(len(words)):
        st = times[i][0]
        dur = (times[i + 1][0] - st) if i < len(words) - 1 else (seg["end"] - st)
        if dur < 0.1:
            continue
        clip = _make_clip(words, i, st, dur, y)
        if clip:
            clips.append(clip)

    # final all-white frame
    final_st = times[-1][1] if times else seg["end"]
    final_dur = max(total_dur - final_st, 0.2)
    final = render_subtitle(words, active_idx=len(words))
    if final is not None:
        fc = ImageClip(np.array(final)).with_duration(final_dur).with_start(final_st).with_position(("center", y))
        clips.append(fc)

    return clips

# ─── main montage ───

def create_video(script_data, footage_clips):
    import random
    story = script_data["story"]
    audio = AudioFileClip(script_data["audio_file"])
    total = min(audio.duration, 60)

    log(f"audio: {audio.duration:.1f}s, capped: {total:.1f}s, words: {len(story.split())}")
    log(f"font_size={FONT_SIZE}, stroke={STROKE_W}, max_w={_MAX_W}")

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
    log(f"timestamps: {len(timestamps)}")

    overlays = []
    if timestamps:
        segs = group_segments(timestamps)
        log(f"segments: {len(segs)}")
        for seg in segs:
            cl = build_segment_clips(seg, total)
            overlays.extend(cl)
    else:
        log("NO TIMESTAMPS — no subtitles")

    if not overlays:
        log("WARNING: no overlays")

    final = CompositeVideoClip([bg] + overlays, size=(VIDEO_WIDTH, VIDEO_HEIGHT))
    final = final.with_audio(audio).with_duration(total)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(FINAL_DIR, f"shorts_{ts}_ar.mp4")
    log(f"rendering {out}")
    final.write_videofile(out, fps=EXPORT_FPS, codec="libx264", audio_codec="aac", bitrate=EXPORT_BITRATE, threads=2, preset="medium", logger=None)
    audio.close()
    final.close()
    script_data["video_file"] = out
    return out
