import os
import re
import sys
import asyncio
import subprocess
import tempfile
import urllib.request
import random
import numpy as np
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from moviepy import (
    VideoFileClip, AudioFileClip, CompositeVideoClip,
    ImageClip, concatenate_videoclips, concatenate_audioclips, ColorClip
)
from moviepy.video.fx import Resize
from config import VIDEO_WIDTH, VIDEO_HEIGHT, TTS_VOICE, TTS_RATE

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _CAN_REShAPE = True
except ImportError:
    _CAN_REShAPE = False

FINAL_DIR = "output/final_videos"
os.makedirs(FINAL_DIR, exist_ok=True)

EXPORT_FPS = 24
EXPORT_BITRATE = "6000k"

# visual
FONT_SIZE = 200
POP_SIZE = FONT_SIZE + 12
STROKE_W = 8
PAD_X = 80
PAD_Y = 60
WORD_GAP = 32
LINE_GAP = int(FONT_SIZE * 0.35)
BG_ALPHA = 140
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

# font

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

# text shaping

def reshape(text):
    if not _CAN_REShAPE:
        return text
    try:
        return get_display(arabic_reshaper.reshape(text), base_direction='R')
    except Exception:
        return text

def clean_diac(text):
    return re.sub(r'[ًٌٍَُِّْ]', '', text)

# measure

def _measure(r, font_size):
    font = _get_font(font_size)
    m = Image.new("L", (1, 1), 0)
    d = ImageDraw.Draw(m)
    sw = int(STROKE_W * font_size / FONT_SIZE)
    bb = d.textbbox((0, 0), r, font=font, stroke_width=sw)
    return bb[2] - bb[0], bb[3] - bb[1], bb[0], bb[1]

# word rendering

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

# layout (word-wrap within MAX_W)

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

# render subtitle box

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

# timestamp pipeline

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

# dark overlay with gradient edges

def _make_dark(total_dur):
    """Bottom-heavy gradient overlay: darker at bottom for text, lighter at top."""
    import numpy as np
    arr = np.zeros((VIDEO_HEIGHT, VIDEO_WIDTH, 4), dtype=np.uint8)
    for y in range(VIDEO_HEIGHT):
        # Bottom (y near height) = darker, Top (y near 0) = lighter
        ratio = y / VIDEO_HEIGHT
        alpha = int(50 + ratio * 160)  # 50 at top, 210 at bottom
        arr[y, :, 3] = min(alpha, 210)
    return (ImageClip(arr).with_duration(total_dur))

# channel watermark

CHANNEL_NAME = "\u0625\u0631\u062b \u0627\u0644\u0625\u064a\u0645\u0627\u0646"

def _make_watermark(total_dur):
    try:
        font = _get_font(32)
        from PIL import Image, ImageDraw
        dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        bb = dummy.textbbox((0, 0), CHANNEL_NAME, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        pad = 16
        img = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([(0, 0), (img.width, img.height)], radius=8, fill=(0, 0, 0, 100))
        tx = (img.width - tw) // 2
        ty = (img.height - th) // 2 - 2
        d.text((tx + 1, ty + 1), CHANNEL_NAME, font=font, fill=(255, 255, 255, 60))
        d.text((tx, ty), CHANNEL_NAME, font=font, fill=(255, 255, 255, 160))
        import numpy as np
        clip = ImageClip(np.array(img)).with_duration(total_dur).with_position((16, 16)).with_opacity(0.7)
        return clip
    except Exception:
        return None

# season accent colors

SEASON_COLORS = {
    1: {"primary": (255, 215, 0), "secondary": (255, 180, 50), "bg": (30, 20, 5)},      # Gold
    2: {"primary": (46, 204, 113), "secondary": (26, 188, 156), "bg": (5, 30, 15)},      # Green
    3: {"primary": (52, 152, 219), "secondary": (41, 128, 185), "bg": (5, 15, 30)},      # Blue
}

def _get_season_colors(script_data):
    sid = script_data.get("season_id", 1)
    return SEASON_COLORS.get(sid, SEASON_COLORS[1])

# ayah card

def _make_ayah_card(total_dur, ayah_text, season_colors):
    if not ayah_text:
        return None
    try:
        font_ayah = _get_font(56)
        font_surah = _get_font(28)
        dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        lines = ayah_text.split(" (")
        ayah_line = lines[0].strip().strip('"').strip("'")
        surah_line = ""
        if len(lines) > 1:
            surah_line = "(" + lines[1]
        wrapped = []
        for w in ayah_line.split():
            if not wrapped:
                wrapped.append(w)
            else:
                test = wrapped[-1] + " " + w
                bb = dummy.textbbox((0, 0), test, font=font_ayah)
                if bb[2] - bb[0] < VIDEO_WIDTH * 0.85:
                    wrapped[-1] = test
                else:
                    wrapped.append(w)
        ayah_display = "\n".join(wrapped)
        bb = dummy.textbbox((0, 0), ayah_display, font=font_ayah)
        aw = bb[2] - bb[0]
        ah = bb[3] - bb[1]
        lines_count = len(wrapped)
        surah_h = 0
        if surah_line:
            sb = dummy.textbbox((0, 0), surah_line, font=font_surah)
            surah_h = sb[3] - sb[1]
        pad_x = 60
        pad_y = 50
        card_w = min(int(aw + pad_x * 2), VIDEO_WIDTH - 40)
        card_h = int(ah + surah_h + pad_y * 2 + 20)
        card = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        d = ImageDraw.Draw(card)
        d.rounded_rectangle([(0, 0), (card_w - 1, card_h - 1)], radius=24,
                            fill=(season_colors["bg"][0], season_colors["bg"][1], season_colors["bg"][2], 220))
        # Gold border
        d.rounded_rectangle([(3, 3), (card_w - 4, card_h - 4)], radius=22,
                            outline=season_colors["primary"] + (180,), width=3)
        y = pad_y
        for line in wrapped:
            lb = d.textbbox((0, 0), line, font=font_ayah)
            lw = lb[2] - lb[0]
            x = (card_w - lw) // 2
            d.text((x + 2, y + 2), line, font=font_ayah, fill=(0, 0, 0, 80))
            d.text((x, y), line, font=font_ayah, fill=season_colors["primary"] + (255,))
            y += lb[3] - lb[1] + 8
        if surah_line:
            y += 10
            sb = d.textbbox((0, 0), surah_line, font=font_surah)
            sw = sb[2] - sb[0]
            sx = (card_w - sw) // 2
            d.text((sx + 1, y + 1), surah_line, font=font_surah, fill=(0, 0, 0, 60))
            d.text((sx, y), surah_line, font=font_surah, fill=(200, 200, 200, 200))
        import numpy as np
        clip = ImageClip(np.array(card)).with_duration(5.0).with_position("center").with_start(0)
        return clip
    except Exception as e:
        log(f"ayah card skip: {e}")
        return None

# lesson card

def _make_lesson_card(total_dur, lesson_text, question_text, season_colors):
    if not lesson_text and not question_text:
        return None
    try:
        font_lesson = _get_font(44)
        font_question = _get_font(36)
        font_label = _get_font(26)
        dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        lines_lesson = []
        if lesson_text:
            for w in lesson_text.split():
                if not lines_lesson:
                    lines_lesson.append(w)
                else:
                    test = lines_lesson[-1] + " " + w
                    bb = dummy.textbbox((0, 0), test, font=font_lesson)
                    if bb[2] - bb[0] < VIDEO_WIDTH * 0.80:
                        lines_lesson[-1] = test
                    else:
                        lines_lesson.append(w)
        lines_question = []
        if question_text:
            for w in question_text.split():
                if not lines_question:
                    lines_question.append(w)
                else:
                    test = lines_question[-1] + " " + w
                    bb = dummy.textbbox((0, 0), test, font=font_question)
                    if bb[2] - bb[0] < VIDEO_WIDTH * 0.80:
                        lines_question[-1] = test
                    else:
                        lines_question.append(w)
        # Measure heights
        lh = 0
        for line in lines_lesson:
            bb = dummy.textbbox((0, 0), line, font=font_lesson)
            lh += bb[3] - bb[1] + 6
        qh = 0
        for line in lines_question:
            bb = dummy.textbbox((0, 0), line, font=font_question)
            qh += bb[3] - bb[1] + 6
        label_h = 30
        pad_x = 50
        pad_y = 40
        total_h = int(pad_y * 2 + label_h + lh + qh + 30)
        card_w = VIDEO_WIDTH - 60
        card = Image.new("RGBA", (card_w, total_h), (0, 0, 0, 0))
        d = ImageDraw.Draw(card)
        d.rounded_rectangle([(0, 0), (card_w - 1, total_h - 1)], radius=20,
                            fill=(0, 0, 0, 200))
        d.rounded_rectangle([(2, 2), (card_w - 3, total_h - 3)], radius=18,
                            outline=season_colors["primary"] + (150,), width=2)
        y = pad_y
        # "عبرة" label
        if lines_lesson:
            lbl = "عبرة من القصة"
            lb = d.textbbox((0, 0), lbl, font=font_label)
            lw = lb[2] - lb[0]
            d.text(((card_w - lw) // 2, y), lbl, font=font_label, fill=season_colors["primary"] + (200,))
            y += label_h
            for line in lines_lesson:
                lb = d.textbbox((0, 0), line, font=font_lesson)
                lw = lb[2] - lb[0]
                x = (card_w - lw) // 2
                d.text((x + 1, y + 1), line, font=font_lesson, fill=(0, 0, 0, 80))
                d.text((x, y), line, font=font_lesson, fill=(255, 255, 255, 230))
                y += lb[3] - lb[1] + 6
        y += 10
        if lines_question:
            lbl = "تفاعل"
            lb = d.textbbox((0, 0), lbl, font=font_label)
            lw = lb[2] - lb[0]
            d.text(((card_w - lw) // 2, y), lbl, font=font_label, fill=season_colors["secondary"] + (200,))
            y += label_h
            for line in lines_question:
                lb = d.textbbox((0, 0), line, font=font_question)
                lw = lb[2] - lb[0]
                x = (card_w - lw) // 2
                d.text((x + 1, y + 1), line, font=font_question, fill=(0, 0, 0, 80))
                d.text((x, y), line, font=font_question, fill=season_colors["secondary"] + (255,))
                y += lb[3] - lb[1] + 6
        import numpy as np
        dur = min(6.0, total_dur * 0.25)
        start = max(0, total_dur - dur)
        clip = ImageClip(np.array(card)).with_duration(dur).with_start(start).with_position("center")
        return clip
    except Exception as e:
        log(f"lesson card skip: {e}")
        return None

# progress bar

def _make_progress_bar(total_dur, color):
    import numpy as np
    bar_h = 6
    def make_frame(t):
        progress = t / total_dur if total_dur > 0 else 0
        w = int(VIDEO_WIDTH * progress)
        arr = np.zeros((bar_h, VIDEO_WIDTH, 4), dtype=np.uint8)
        if w > 0:
            arr[:, :w] = list(color) + [180]
        return arr
    from moviepy import VideoClip
    return VideoClip(make_frame, duration=total_dur).with_position((0, VIDEO_HEIGHT - bar_h))

# intro audio (bismillah)

_INTRO_CACHE = None

def _get_intro_audio():
    global _INTRO_CACHE
    if _INTRO_CACHE is not None:
        return _INTRO_CACHE
    try:
        import edge_tts
        path = os.path.join(tempfile.gettempdir(), "opencode_intro_bismillah.mp3")
        if not os.path.exists(path) or os.path.getsize(path) < 100:
            async def _gen():
                comm = edge_tts.Communicate("\u0628\u0633\u0645 \u0627\u0644\u0644\u0647 \u0627\u0644\u0631\u062d\u0645\u0646 \u0627\u0644\u0631\u062d\u064a\u0645", TTS_VOICE, rate=TTS_RATE)
                await comm.save(path)
            asyncio.run(_gen())
        if os.path.exists(path) and os.path.getsize(path) > 100:
            _INTRO_CACHE = AudioFileClip(path)
            return _INTRO_CACHE
    except Exception as e:
        log(f"intro gen skip: {e}")
    return None

# main

def create_video(script_data, footage_clips):
    story = script_data["story"]
    audio = AudioFileClip(script_data["audio_file"])

    # Prepend intro audio (bismillah)
    intro_dur = 0
    try:
        intro_clip = _get_intro_audio()
        if intro_clip is not None:
            intro_dur = intro_clip.duration
            audio = concatenate_audioclips([intro_clip, audio])
            log(f"intro: {intro_dur:.1f}s")
    except Exception as e:
        log(f"intro skip: {e}")

    total = audio.duration
    offset = intro_dur
    log(f"audio: {total:.1f}s | story: {len(story.split())} words | font={FONT_SIZE}px")

    # Mix background music
    try:
        from background_music import get_background_audio
        bg_music = get_background_audio(total, topic=script_data.get("topic", ""))
        if bg_music is not None:
            audio = CompositeAudioClip([audio, bg_music])
            log(f"bg music mixed")
    except Exception as e:
        log(f"bg music skip: {e}")

    parts = []
    for c in footage_clips:
        try:
            clip = VideoFileClip(c["path"]).resized(new_size=(VIDEO_WIDTH, VIDEO_HEIGHT))
            if clip.duration < 1.0:
                clip.close()
                continue
            parts.append(clip)
        except Exception as e:
            log(f"footage skip: {c.get('path','?')} - {e}")

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
    # Shift timestamps by intro duration
    if offset > 0:
        for ts in timestamps:
            ts["start"] += offset
            ts["end"] += offset

    season_colors = _get_season_colors(script_data)
    overlays = [_make_dark(total)]
    wm = _make_watermark(total)
    if wm is not None:
        overlays.append(wm)

    # Ayah intro card
    ayah_text = script_data.get("ayah_text", "")
    if ayah_text:
        ayah_card = _make_ayah_card(total, ayah_text, season_colors)
        if ayah_card is not None:
            overlays.append(ayah_card)
            log(f"ayah card added")

    # Progress bar
    try:
        pb = _make_progress_bar(total, season_colors["primary"])
        overlays.append(pb)
    except Exception as e:
        log(f"progress bar skip: {e}")

    if timestamps:
        segs = group_segments(timestamps)
        log(f"segments: {len(segs)}")
        for seg in segs:
            overlays.extend(build_segment_clips(seg, total))
    else:
        log("NO TIMESTAMPS — no subtitles")

    # Lesson/question card at end
    lesson_text = script_data.get("lesson_text", "")
    question_text = script_data.get("question_text", "")
    if lesson_text or question_text:
        lesson_card = _make_lesson_card(total, lesson_text, question_text, season_colors)
        if lesson_card is not None:
            overlays.append(lesson_card)
            log(f"lesson card added")

    log(f"total overlay clips: {len(overlays)}")

    final = CompositeVideoClip([bg] + overlays, size=(VIDEO_WIDTH, VIDEO_HEIGHT))
    final = final.with_audio(audio).with_duration(total)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(FINAL_DIR, f"shorts_{ts}_ar.mp4")
    log(f"rendering {out}")
    final.write_videofile(out, fps=EXPORT_FPS, codec="libx264", audio_codec="aac",
                          bitrate=EXPORT_BITRATE, threads=1, preset="veryfast", logger=None)
    audio.close()
    final.close()
    script_data["video_file"] = out
    return out
