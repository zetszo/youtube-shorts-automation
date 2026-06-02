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
_TEXT_CACHE = {}

_STROKE = 6
_PAD = 40
_SAFE_Y = 0.42
_GOLD = (255, 215, 0)
_WHITE = (255, 255, 255)

FONT_SIZE_LARGE = 90
FONT_SIZE_MEDIUM = 84
FONT_SIZE_SMALL = 76

EXPORT_FPS = 30
EXPORT_BITRATE = "8000k"
SEGMENT_GAP = 0.1

# ───────────────────────── helpers ─────────────────────────

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

# ───────────────────────── text rendering ─────────────────────────

def wrap_lines(words):
    n = len(words)
    if n <= 2:
        return [words]
    if n == 3:
        return [words[:2], words[2:]]
    if n == 4:
        return [words[:2], words[2:]]
    half = (n + 1) // 2
    return [words[:half], words[half:]]

def render_word(text, color, font, font_size):
    key = (text, color, font_size)
    if key in _TEXT_CACHE:
        return _TEXT_CACHE[key]

    r = reshape(text)
    if not r.strip():
        _TEXT_CACHE[key] = (None, 0, 0)
        return None, 0, 0
    cw, ch, ox, oy = text_bbox(r, font)
    if cw < 4 or ch < 4:
        _TEXT_CACHE[key] = (None, 0, 0)
        return None, 0, 0

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

    _TEXT_CACHE[key] = (img, cw, ch)
    return img, cw, ch

def render_line(words, font, first_gold, font_size):
    items = []
    tw = 0
    mh = 0
    for i, w in enumerate(words):
        c = _GOLD if (i == 0 and first_gold) else _WHITE
        img, cw, ch = render_word(w, c, font, font_size)
        if img is None:
            continue
        items.append((img, cw, ch))
        tw += cw + 10
        mh = max(mh, ch)
    if not items:
        return None, 0, 0

    tw -= 10
    tw = max(tw, 10)
    mh = max(mh, 10)

    lw = int(tw + _STROKE * 6)
    lh = int(mh + _STROKE * 6)
    line = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))

    x = lw // 2 + tw // 2
    for img, cw, ch in items:
        x -= cw
        px = int(x + _STROKE * 2 - (lw // 2 - tw // 2))
        py = int((lh - ch) // 2)
        line.paste(img, (px, py), img)
    return line, lw, lh

def render_block(text, font_size, is_hook):
    words = [w for w in text.split() if w.strip()]
    if not words:
        return None

    font = load_font(font_size)
    lines = wrap_lines(words)

    images = []
    for i, ln in enumerate(lines):
        img, w, h = render_line(ln, font, first_gold=(i == 0), font_size=font_size)
        if img is not None:
            images.append((img, w, h))

    if not images:
        return None

    ls = int(font_size * 0.25)
    mw = max(w for _, w, _ in images)
    th = sum(h for _, _, h in images) + (len(images) - 1) * ls

    bw = int(mw + _PAD * 2)
    bh = int(th + _PAD * 2)

    bg = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    bgd = ImageDraw.Draw(bg)
    if is_hook:
        bgd.rounded_rectangle([(0, 0), (bw - 1, bh - 1)], radius=14, fill=(180, 140, 20, 160))
    else:
        bgd.rounded_rectangle([(0, 0), (bw - 1, bh - 1)], radius=14, fill=(0, 0, 0, 140))

    cy = (bh - th) // 2
    for img, w, h in images:
        cx = (bw - w) // 2
        bg.paste(img, (cx, cy), img)
        cy += h + ls

    return ImageClip(np.array(bg)).with_duration(1)

# ───────────────────────── sync: edge-tts word timestamps ─────────────────────────

def _split_phrases(text):
    parts = re.split(r'[،\.!\?؟—:;\n]+', text)
    parts = [p.strip() for p in parts if p.strip()]
    out = []
    for part in parts:
        words = part.split()
        if not words:
            continue
        if len(words) <= 4:
            out.append(" ".join(words))
        else:
            for i in range(0, len(words), 3):
                chunk = words[i:i+3]
                if chunk:
                    out.append(" ".join(chunk))
    return out

def build_segments(text, word_timings, total_dur):
    phrases = _split_phrases(text)
    if not phrases:
        return [(text, 0, total_dur)]

    total = sum(len(p.split()) for p in phrases)
    if total == 0:
        return [(text, 0, total_dur)]

    segs = []
    acc = 0
    for phrase in phrases:
        n = len(phrase.split())
        start = (acc / total) * total_dur
        end = ((acc + n) / total) * total_dur
        dur = end - start
        if dur > 0.3:
            segs.append((phrase, start, dur))
        acc += n

    last_end = 0
    out = []
    for txt, st, dur in segs:
        st = max(st, last_end + SEGMENT_GAP)
        if st + dur > total_dur:
            dur = total_dur - st
        if dur > 0.3:
            out.append((txt, st, dur))
            last_end = st + dur
    return out or [(text, 0, total_dur)]

# ───────────────────────── main montage ─────────────────────────

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

    segments = build_segments(story, script_data.get("word_timings", []), total)
    overlays = []
    for idx, (txt, start, dur) in enumerate(segments):
        wc = len(txt.split())
        fs = FONT_SIZE_LARGE if wc <= 2 else FONT_SIZE_MEDIUM if wc == 3 else FONT_SIZE_SMALL
        clip = render_block(txt, fs, is_hook=(idx == 0))
        if clip is None:
            continue
        sh = clip.size[1]
        y = int(_SAFE_Y * VIDEO_HEIGHT - sh / 2)
        y = max(int(0.08 * VIDEO_HEIGHT), min(y, int(0.75 * VIDEO_HEIGHT)))
        overlays.append(clip.with_position(("center", y)).with_duration(dur).with_start(start))

    final = CompositeVideoClip([bg] + overlays, size=(VIDEO_WIDTH, VIDEO_HEIGHT))
    final = final.with_audio(audio).with_duration(total)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(FINAL_DIR, f"shorts_{ts}_ar.mp4")
    final.write_videofile(out, fps=EXPORT_FPS, codec="libx264", audio_codec="aac", bitrate=EXPORT_BITRATE, threads=2, preset="medium", logger=None)
    audio.close()
    final.close()
    script_data["video_file"] = out
    return out
