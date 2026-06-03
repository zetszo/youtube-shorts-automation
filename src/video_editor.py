import os
import re
import sys
import subprocess
import tempfile
import urllib.request
import random
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
FONT_SIZE = 200
POP_SIZE = FONT_SIZE + 12
STROKE_W = 8
PAD_X = 80
PAD_Y = 60
WORD_GAP = 32
LINE_GAP = int(FONT_SIZE * 0.35)
BG_ALPHA = 160
RADIUS = 36
MAX_W = int(VIDEO_WIDTH * 0.88)
CENTER_Y = int(VIDEO_HEIGHT * 0.50)
GROUP_MIN = 2
GROUP_MAX = 3

_GOLD = (255, 215, 0)
_WHITE = (255, 255, 255)

_WORD_CACHE = {}
_FONT_CACHE = {}

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

def _get_font(size):
    if size not in _FONT_CACHE:
        path = _find_font()
        if path:
            try:
                _FONT_CACHE[size] = ImageFont.truetype(path, size)
            except Exception as e:
                log(f"font load error: {e}")
                _FONT_CACHE[size] = ImageFont.load_default()
        else:
            _FONT_CACHE[size] = ImageFont.load_default()
    return _FONT_CACHE[size]

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

def _measure(r, font_size):
    font = _get_font(font_size)
    m = Image.new("L", (1, 1), 0)
    d = ImageDraw.Draw(m)
    sw = int(STROKE_W * font_size / FONT_SIZE)
    bb = d.textbbox((0, 0), r, font=font, stroke_width=sw)
    return bb[2] - bb[0], bb[3] - bb[1], bb[0], bb[1]

# ─── word rendering ───

def _render_word(text, color, font_size):
    key = (text, color, font_size)
    if key in _WORD_CACHE:
        return _WORD_CACHE[key]
    r = reshape(text)
    if not r.strip():
        _WORD_CACHE[key] = None
        return None
    sw = int(STROKE_W * font_size / FONT_SIZE)
    cw, ch, ox, oy = _measure(r, font_size)
    if cw < 4 or ch < 4:
        _WORD_CACHE[key] = None
        return None
    pad = sw * 3
    iw = int(cw + pad * 2)
    ih = int(ch + pad * 2)
    img = Image.new("RGBA", (iw, ih), (0, 0, 0, 0))
    bg = Image.new("RGBA", (iw, ih), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bg)
    bd.text((pad - ox + 2, pad - oy + 2), r, font=_get_font(font_size),
            fill=(0, 0, 0, 60), stroke_width=sw, stroke_fill=(0, 0, 0, 60))
    img = Image.alpha_composite(img, bg)
    fd = ImageDraw.Draw(img)
    fd.text((pad - ox, pad - oy), r, font=_get_font(font_size),
            fill=color + (255,), stroke_width=sw, stroke_fill=(0, 0, 0, 220))
    _WORD_CACHE[key] = img
    return img

# ─── layout (word-wrap within MAX_W) ───

def _layout(words, active_idx):
    font_size = FONT_SIZE
    items = []
    for i, w in enumerate(words):
        sz = POP_SIZE if i == active_idx else font_size
        r = reshape(w)
        if not r.strip():
            items.append((w, 0, 0, sz))
            continue
        cw, ch, _, _ = _measure(r, sz)
        pw = cw + int(STROKE_W * sz / font_size) * 4
        ph = ch + int(STROKE_W * sz / font_size) * 4
        items.append((w, pw, ph, sz))
    max_h = max((it[2] for it in items), default=0)
    lines = []
    cur = []
    cur_w = 0
    for it in items:
        gap = WORD_GAP if cur else 0
        need = it[1] + gap
        if cur and cur_w + need > MAX_W:
            lines.append(cur)
            cur = [it]
            cur_w = it[1]
        else:
            cur.append(it)
            cur_w += need
    if cur:
        lines.append(cur)
    out = []
    for row, line in enumerate(lines):
        lw = sum(it[1] for it in line) + WORD_GAP * (len(line) - 1)
        x = lw
        for w, pw, ph, sz in line:
            x -= pw
            out.append((w, x, row * (max_h + LINE_GAP), pw, ph, sz))
            x -= WORD_GAP
    return out

# ─── render subtitle box ───

def render_box(words, active_idx):
    pos = _layout(words, active_idx)
    if not pos:
        return None, 0, 0
    min_x = min(x for _, x, _, _, _, _ in pos)
    max_x = max(x + w for _, x, _, w, _, _ in pos)
    max_y = max(y + h for _, _, y, _, h, _ in pos)
    bw = int(max_x - min_x + PAD_X * 2)
    bh = int(max_y + PAD_Y * 2)
    if bw < 40 or bh < 40:
        return None, 0, 0
    bg = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    bgd = ImageDraw.Draw(bg)
    bgd.rounded_rectangle([(0, 0), (bw - 1, bh - 1)], radius=RADIUS, fill=(0, 0, 0, BG_ALPHA))
    painted = 0
    for i, (w, x, y, _, _, sz) in enumerate(pos):
        if i > active_idx:
            continue
        color = _GOLD if i == active_idx else _WHITE
        img = _render_word(w, color, sz)
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

# ─── timestamp pipeline ───

def build_word_timestamps(text, word_timings):
    tw = [w for w in (word_timings or [])
          if w["text"].strip() and any(c.isalpha() for c in w["text"])]
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
    segs = []
    i = 0
    while i < len(timestamps):
        n = min(random.randint(GROUP_MIN, GROUP_MAX), len(timestamps) - i)
        group = timestamps[i:i + n]
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
        if i < len(words) - 1:
            end = times[i + 1][0]
        else:
            end = times[i][1]
        if end <= st:
            continue
        box, sx, sy = render_box(words, i)
        if box is None:
            continue
        clip = ImageClip(np.array(box)).with_duration(end - st).with_start(st).with_position((sx, sy))
        clips.append(clip)
    final_st = times[-1][1]
    final_dur = max(seg["end"] - final_st, 0)
    if final_dur > 0.1:
        box, sx, sy = render_box(words, len(words))
        if box is not None:
            clips.append(ImageClip(np.array(box)).with_duration(final_dur).with_start(final_st).with_position((sx, sy)))
    return clips

# ─── dark overlay ───

def _make_dark(total_dur):
    return (ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(0, 0, 0))
            .with_duration(total_dur)
            .with_opacity(0.30))

# ─── main ───

def create_video(script_data, footage_clips):
    story = script_data["story"]
    audio = AudioFileClip(script_data["audio_file"])
    total = min(audio.duration, 60)
    log(f"audio: {audio.duration:.1f}s | story: {len(story.split())} words | font={FONT_SIZE}px")

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

    overlays = [_make_dark(total)]
    if timestamps:
        segs = group_segments(timestamps)
        log(f"segments: {len(segs)}")
        for seg in segs:
            overlays.extend(build_segment_clips(seg, total))
    else:
        log("NO TIMESTAMPS — no subtitles")

    log(f"total overlay clips: {len(overlays)}")

    final = CompositeVideoClip([bg] + overlays, size=(VIDEO_WIDTH, VIDEO_HEIGHT))
    final = final.with_audio(audio).with_duration(total)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(FINAL_DIR, f"shorts_{ts}_ar.mp4")
    log(f"rendering {out}")
    final.write_videofile(out, fps=EXPORT_FPS, codec="libx264", audio_codec="aac",
                          bitrate=EXPORT_BITRATE, threads=2, preset="medium", logger=None)
    audio.close()
    final.close()
    script_data["video_file"] = out
    return out
