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
TRANSITION_DURATION = 0.5  # crossfade duration

def create_video(script_data: dict, footage_clips: list) -> str:
    story = script_data["story"]
    audio_path = script_data["audio_file"]
    lang = script_data["language"]

    audio = AudioFileClip(audio_path)
    target = audio.duration

    # Load footage
    bg = []
    for c in footage_clips:
        try:
            clip = VideoFileClip(c["path"]).resized(new_size=(VIDEO_WIDTH, VIDEO_HEIGHT))
            bg.append(clip)
        except Exception:
            pass

    # Build segments with crossfade transitions
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
            sub = clip.subclipped(0, dur)
            if sub.duration < 1.0:
                i += 1
                continue
            sub = sub.resized(new_size=(VIDEO_WIDTH, VIDEO_HEIGHT))
            parts.append(sub)
            remaining -= dur
            i += 1

        if not parts:
            parts = [ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 30, 50)).with_duration(target)]
            background = parts[0]
        else:
            # Apply crossfade transitions between clips
            for i in range(1, len(parts)):
                parts[i] = parts[i].with_start(parts[i - 1].end - TRANSITION_DURATION).crossfadein(TRANSITION_DURATION)
            background = concatenate_videoclips(parts, method="compose")

    # Semi-transparent overlay gradient (darker at bottom for text)
    overlay = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(0, 0, 0)).with_duration(target).with_opacity(0.25)

    # Bottom gradient bar for text area
    bar = ColorClip(size=(VIDEO_WIDTH, 500), color=(0, 0, 0)).with_duration(target).with_opacity(0.55)
    bar = bar.with_position(("center", VIDEO_HEIGHT - 500))

    # Text lines
    lines = _split_text(story, target)
    seg_dur = target / max(len(lines), 1)
    font = FONT_PATH if os.path.exists(FONT_PATH) else FONT_FALLBACK

    texts = []
    for idx, line in enumerate(lines):
        try:
            txt = TextClip(
                text=line,
                font=font,
                font_size=52,
                color="white",
                stroke_color="black",
                stroke_width=1,
                method="caption",
                size=(VIDEO_WIDTH - 160, None),
                text_align="center",
            )
        except Exception:
            txt = TextClip(
                text=line,
                font=FONT_FALLBACK,
                font_size=48,
                color="white",
                stroke_color="black",
                stroke_width=1,
                method="label",
            )
        # Position text in the lower third area (above the bar)
        txt_y = VIDEO_HEIGHT * 0.62 + random.uniform(-10, 10)
        txt = txt.with_position(("center", txt_y)).with_duration(seg_dur).with_start(idx * seg_dur).crossfadein(0.2)
        texts.append(txt)

    # Title bar at top (subtle)
    title_bar = ColorClip(size=(VIDEO_WIDTH, 80), color=(0, 0, 0)).with_duration(target).with_opacity(0.3)
    title_bar = title_bar.with_position(("center", 0))

    final = CompositeVideoClip(
        [background, overlay, bar, title_bar] + texts,
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

def _split_text(text: str, total: float, chars: int = 70) -> list:
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
    mins = max(int(total / 3.2), 3)
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
