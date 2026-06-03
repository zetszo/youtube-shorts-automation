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
from moviepy.video.fx import Resize
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

# ─── visual ───
FONT_SIZE = 260
STROKE_W = 18
PAD_X = 60
PAD_Y = 50
WORD_GAP = 24
LINE_SPACE = int(FONT_SIZE * 0.25)
BG_ALPHA = 160
RADIUS = 32
MAX_W = int(VIDEO_WIDTH * 0.90)
CENTER_Y = int(VIDEO_HEIGHT * 0.48)
GROUP_MIN = 2
GROUP_MAX = 3

_GOLD = (255, 215, 0)
_WHITE = (255, 255, 255)

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
    (os.path.join(tempfile.gettempdir(), "NotoSansArabic-Bold.ttf"),
     "https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/fonts/NotoSansArabic/googlefonts/ttf/NotoSansArabic-Bold.ttf"),
    (os.path.join(tempfile.gettempdir(), "Cairo-Bold.ttf"),
     "https://raw.githubusercontent.com/Gue3bara/Cairo/main/fonts/Cairo-Bold.ttf"),
]

def log(msg):
    print(f"[VIDEO] {msg}", file=sys.stderr)

# ─── font ───

def _find_font():
    for p in FONT_CANDIDATES:
        if os.path.isfile(p) and os.path.getsize(p) > 1000:
            log(f"font found: {p}")
            return p
    try:
        out = subprocess.check_output(["fc-list", ":lang=ar", "-f", "%{file}\n"], stderr=subprocess.DEVNULL, timeout=5, encoding="utf-8")
        for line in out.strip().splitlines():
            f = line.strip()
            if f and os.path.isfile(f) and os.path.getsize(f) > 1000:
                log(f"font from fc-list: {f}")
                return f
    except Exception:
        pass
    for path, url in CDN_FONTS:
        if os.path.isfile(path) and os.path.getsize(path) > 1000:
            log(f"font cached: {path}")
            return path
        try:
            log(f"downloading {os.path.basename(path)}...")
            urllib.request.urlretrieve(url, path)
            if os.path.getsize(path) > 1000:
                log(f"font downloaded: {path}")
                return path
        except Exception as e:
            log(f"download failed: {e}")
    log("NO ARABIC FONT!")
    return None

def get_font():
    global _FONT_CACHE
    if _FONT_CACHE is None:
        _FONT_CACHE = _find_font()
    if _FONT_CACHE:
        try:
            return ImageFont.truetype(_FONT_CACHE, FONT_SIZE)
        except Exception as e:
            log(f"font load error: {e}")
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

def _measure(r):
    font = get_font()
    m = Image.new("L", (1, 1), 0)
    d = ImageDraw.Draw(m)
    bb = d.textbbox((0, 0), r, font=font, stroke_width=STROKE_W)
    return bb[2] - bb[0], bb[3] - bb[1], bb[0], bb[1]

# ─── word rendering ───

def _render_word(text, color):
    key = (text, color)
    if key in _WORD_CACHE:
        return _WORD_CACHE[key]
    r = reshape(text)
    if not r.strip():
        _WORD_CACHE[key] = None
        return None
    cw, ch, ox, oy = _measure(r)
    if cw < 4 or ch < 4:
        _WORD_CACHE[key] = None
        return None
    iw = int(cw + STROKE_W * 6)
    ih = int(ch + STROKE_W * 6)
    img = Image.new("RGBA", (iw, ih), (0, 0, 0, 0))
    sh = Image.new("RGBA", (iw, ih), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.text((STROKE_W * 2 - ox + 4, STROKE_W * 2 - oy + 4), r, font=get_font(), fill=(0, 0, 0, 70), stroke_width=STROKE_W, stroke_fill=(0, 0, 0, 70))
    img = Image.alpha_composite(img, sh)
    wd = ImageDraw.Draw(img)
    wd.text((STROKE_W * 2 - ox, STROKE_W * 2 - oy), r, font=get_font(), fill=color + (255,), stroke_width=STROKE_W, stroke_fill=(0, 0, 0, 255))
    _WORD_CACHE[key] = img
    return img

# ─── layout ───

def _layout(words):
    items = []
    for w in words:
        r = reshape(w)
        if not r.strip():
            items.append((w, 0, 0))
            continue
        cw, ch, _, _ = _measure(r)
        items.append((w, cw + STROKE_W * 4, ch + STROKE_W * 4))
    total_w = sum(it[1] for it in items) + WORD_GAP * (len(items) - 1)
    line_h = max((it[2] for it in items), default=0)
    if total_w <= MAX_W:
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

# ─── render subtitle box and full frame ───

def render_box(words, active_idx):
    """Return (bg_image, screen_x, screen_y) — tight box at screen position."""
    pos = _layout(words)
    if not pos:
        return None, 0, 0
    min_x = min(x for _, x, _, _, _ in pos)
    max_x = max(x + w for _, x, _, w, _ in pos)
    max_y = max(y + h for _, _, y, _, h in pos)
    bw = int(max_x - min_x + PAD_X * 2)
    bh = int(max_y + PAD_Y * 2)
    if bw < 40 or bh < 40:
        return None, 0, 0
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
        return None, 0, 0
    sx = (VIDEO_WIDTH - bw) // 2
    sy = CENTER_Y - bh // 2
    return bg, sx, sy

def render_frame(words, active_idx):
    """Full 1080x1920 canvas with subtitle at exact center."""
    box, sx, sy = render_box(words, active_idx)
    if box is None:
        return None
    canvas = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    canvas.paste(box, (sx, sy), box)
    return canvas

# ─── timestamp pipeline ───

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

def build_segment_clips(seg, total_dur):
    words = seg["words"]
    times = seg["times"]
    clips = []
    for i in range(len(words)):
        st = times[i][0]
        dur = (times[i + 1][0] - st) if i < len(words) - 1 else (seg["end"] - st)
        if dur < 0.1:
            continue
        box, sx, sy = render_box(words, i)
        if box is None:
            continue
        clip = ImageClip(np.array(box)).with_duration(dur).with_start(st).with_position((sx, sy))
        def pop(t):
            return 1.12 - 0.12 * min(t / 0.2, 1.0)
        clip = Resize(pop)(clip)
        clips.append(clip)
    final_st = times[-1][1] if times else seg["end"]
    final_dur = max(total_dur - final_st, 0.2)
    box, sx, sy = render_box(words, active_idx=len(words))
    if box is not None:
        clips.append(ImageClip(np.array(box)).with_duration(final_dur).with_start(final_st).with_position((sx, sy)))
    return clips

# ─── main ───

def create_video(script_data, footage_clips):
    import random
    story = script_data["story"]
    audio = AudioFileClip(script_data["audio_file"])
    total = min(audio.duration, 60)
    log(f"audio: {audio.duration:.1f}s | {len(story.split())} words | font={FONT_SIZE}px")

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
        bg = concatenate_videoclips(clips, method="compose") if clips else ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 30, 50)).with_duration(total)

    timestamps = build_word_timestamps(story, script_data.get("word_timings", []))
    log(f"timestamps: {len(timestamps)}")
    overlays = []
    if timestamps:
        segs = group_segments(timestamps)
        log(f"segments: {len(segs)}")
        for seg in segs:
            overlays.extend(build_segment_clips(seg, total))
    else:
        log("NO TIMESTAMPS")

    # Verify at least one overlay has content
    if overlays:
        log(f"total overlay clips: {len(overlays)}")
    else:
        log("WARNING: zero overlays")

    dark = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(0, 0, 0)).with_duration(total).with_opacity(0.3)
    final = CompositeVideoClip([bg, dark] + overlays, size=(VIDEO_WIDTH, VIDEO_HEIGHT))
    final = final.with_audio(audio).with_duration(total)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(FINAL_DIR, f"shorts_{ts}_ar.mp4")
    log(f"rendering {out}")
    final.write_videofile(out, fps=EXPORT_FPS, codec="libx264", audio_codec="aac", bitrate=EXPORT_BITRATE, threads=2, preset="medium", logger=None)
    audio.close()
    final.close()
    script_data["video_file"] = out
    return out
