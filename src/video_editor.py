import os
import random
from datetime import datetime
from moviepy import (
    VideoFileClip, AudioFileClip, CompositeVideoClip,
    TextClip, concatenate_videoclips, ColorClip
)
from config import VIDEO_WIDTH, VIDEO_HEIGHT

FINAL_DIR = "output/final_videos"
os.makedirs(FINAL_DIR, exist_ok=True)

FONT_PATH = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"
FONT_FALLBACK = "DejaVu-Sans"

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

    overlay = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(0, 0, 0)).with_duration(target).with_opacity(0.15)

    bar = ColorClip(size=(VIDEO_WIDTH, 600), color=(0, 0, 0)).with_duration(target).with_opacity(0.6)
    bar = bar.with_position(("center", VIDEO_HEIGHT - 600))

    lines = _split_text(story, target)
    seg_dur = target / max(len(lines), 1)
    font = FONT_PATH if os.path.exists(FONT_PATH) else FONT_FALLBACK

    texts = []
    for idx, line in enumerate(lines):
        try:
            txt = TextClip(
                text=line,
                font=font,
                font_size=70,
                color="white",
                stroke_color="black",
                stroke_width=1,
                method="caption",
                size=(VIDEO_WIDTH - 120, None),
                text_align="center",
            )
        except Exception:
            txt = TextClip(
                text=line,
                font=FONT_FALLBACK,
                font_size=62,
                color="white",
                stroke_color="black",
                stroke_width=1,
                method="label",
            )
        txt_y = VIDEO_HEIGHT - 350
        txt = txt.with_position(("center", txt_y)).with_duration(seg_dur).with_start(idx * seg_dur)
        texts.append(txt)

    final = CompositeVideoClip(
        [background, overlay, bar] + texts,
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

def _split_text(text: str, total: float, chars: int = 90) -> list:
    words = text.split()
    lines, cur, cur_len = [], [], 0
    for w in words:
        if cur_len + len(w) + 1 > chars and cur:
            lines.append(" ".join(cur))
            cur, cur_len = [w], len(w)
        else:
            cur.append(w)
            cur_len += len(w) + 1
    if cur:
        lines.append(" ".join(cur))
    mins = max(int(total / 3), 2)
    while len(lines) < mins:
        new = []
        for l in lines:
            if len(l) > chars // 2:
                mid = len(l) // 2
                sp = l.rfind(" ", 0, mid)
                new.extend([l[:sp], l[sp + 1:]] if sp > 0 else [l])
            else:
                new.append(l)
        if len(new) == len(lines):
            break
        lines = new
    return lines
