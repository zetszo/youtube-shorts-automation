import os
import re
import random
from datetime import datetime
from moviepy import (
    VideoFileClip, AudioFileClip, CompositeVideoClip,
    TextClip, concatenate_videoclips, ColorClip
)
from config import VIDEO_WIDTH, VIDEO_HEIGHT

FINAL_DIR = "output/final_videos"
os.makedirs(FINAL_DIR, exist_ok=True)

FONT_PATHS = [
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
]
FONT_FALLBACK = "DejaVu-Sans"

SAFE_Y = 0.42
TEXT_WIDTH = VIDEO_WIDTH - 300
FONT_SIZE = 70
STROKE_WIDTH = 3
BG_PAD = 25
BG_OPACITY = 0.55

def _find_font():
    for p in FONT_PATHS:
        if os.path.exists(p):
            return p
    return FONT_FALLBACK

def create_video(script_data: dict, footage_clips: list) -> str:
    story = script_data["story"]
    audio_path = script_data["audio_file"]
    lang = script_data["language"]

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

    segments = _split_into_segments(story, target)
    font = _find_font()

    layers = []
    for text, start, dur in segments:
        try:
            txt = TextClip(
                text=text,
                font=font,
                font_size=FONT_SIZE,
                color="white",
                stroke_color="black",
                stroke_width=STROKE_WIDTH,
                method="caption",
                size=(TEXT_WIDTH, None),
                text_align="center",
            )
        except Exception:
            txt = TextClip(
                text=text,
                font=FONT_FALLBACK,
                font_size=FONT_SIZE - 8,
                color="white",
                stroke_color="black",
                stroke_width=STROKE_WIDTH,
                method="label",
            )

        try:
            tw, th = txt.size
        except Exception:
            tw, th = TEXT_WIDTH, int(FONT_SIZE * 2.5)

        bg_w = tw + BG_PAD * 2
        bg_h = th + BG_PAD * 2

        txt_bg = (ColorClip(size=(int(bg_w), int(bg_h)), color=(0, 0, 0))
                  .with_opacity(BG_OPACITY))
        txt_layer = txt.with_position(("center", "center"))

        segment = (CompositeVideoClip([txt_bg, txt_layer])
                   .with_position(("center", int(SAFE_Y * VIDEO_HEIGHT - bg_h / 2)))
                   .with_duration(dur)
                   .with_start(start))
        layers.append(segment)

    final = CompositeVideoClip(
        [background] + layers,
        size=(VIDEO_WIDTH, VIDEO_HEIGHT)
    )
    final = final.with_audio(audio).with_duration(target)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(FINAL_DIR, f"shorts_{ts}_{lang}.mp4")
    final.write_videofile(out, fps=30, codec="libx264", audio_codec="aac", threads=2, preset="medium", logger=None)
    audio.close()
    final.close()

    script_data["video_file"] = out
    return out

def _split_into_segments(text: str, total_duration: float) -> list:
    sentences = re.split(r'(?<=[.!?؟!])', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) < 3:
        words = text.split()
        chunk = max(1, len(words) // 3)
        sentences = []
        for i in range(0, len(words), chunk):
            sentences.append(" ".join(words[i:i + chunk]))

    total_words = sum(len(s.split()) for s in sentences)
    if total_words == 0:
        return [(text, 0, total_duration)]

    result = []
    current = 0
    for s in sentences:
        wc = len(s.split())
        dur = max(1.5, (wc / total_words) * total_duration)
        if current + dur > total_duration:
            dur = total_duration - current
        if dur > 0.5:
            result.append((s, current, dur))
            current += dur

    if not result:
        result = [(text, 0, total_duration)]

    return result
