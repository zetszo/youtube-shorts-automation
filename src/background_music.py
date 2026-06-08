import os
import random
import re
import numpy as np

MUSIC_DIR = "output/music"
_TRACK_CACHE = None

# Mood keywords in filenames (lowercase)
_SAD_WORDS = ["sad", "emotional", "heart", "tear", "cry", "dark", "so sad"]
_CALM_WORDS = ["calm", "peace", "cool", "love", "traditional", "happy"]

# Arabic story keywords that suggest mood
_SAD_STORY_WORDS = [
    "وفاة", "مات", "بكى", "يبكي", "بكاء", "استشهاد", "شهيد", "شهداء",
    "حزن", "حزين", "دمعة", "دموع", "ألم", "أوجع", "وجع", "مرض",
    "فقد", "فقدان", "يتيم", "أرمل", "قبر", "دفن", "موت",
    "ابتلاء", "ابتلاه", "محنة", "مصيبة", "جزع",
]

_FALLBACK_SONGS = [
    "Arabian Camel Caravan Background Music __ copyright free __ Islamic background music(M4A_128K).m4a",
    "Islamic Background Music Copyright-Free __ Islamic background music  _nocopyrightmusic _nocopyright(M4A_128K).m4a",
    "nasheed Islamic background sound no copyright __ Islamic Background Music _islamic _viral(M4A_128K).m4a",
]

def _classify_track(fname):
    """Classify a track as 'sad', 'calm', or 'default' based on filename."""
    low = fname.lower()
    for w in _SAD_WORDS:
        if w in low:
            return "sad"
    for w in _CALM_WORDS:
        if w in low:
            return "calm"
    return "default"

def scan_tracks():
    """Return dict: mood -> list of file paths."""
    tracks = {"sad": [], "calm": [], "default": []}
    if not os.path.isdir(MUSIC_DIR):
        return tracks
    for f in os.listdir(MUSIC_DIR):
        if f.endswith((".mp3", ".m4a", ".wav", ".ogg")):
            path = os.path.join(MUSIC_DIR, f)
            mood = _classify_track(f)
            tracks[mood].append(path)
    return tracks

def pick_track(topic=""):
    """Pick the best track for the given story topic."""
    global _TRACK_CACHE
    if _TRACK_CACHE is None:
        _TRACK_CACHE = scan_tracks()

    all_tracks = _TRACK_CACHE["sad"] + _TRACK_CACHE["calm"] + _TRACK_CACHE["default"]
    if not all_tracks:
        return None

    # Determine if story is sad
    is_sad = False
    if topic:
        for w in _SAD_STORY_WORDS:
            if w in topic:
                is_sad = True
                break

    if is_sad and _TRACK_CACHE["sad"]:
        chosen = random.choice(_TRACK_CACHE["sad"])
    elif _TRACK_CACHE["calm"]:
        chosen = random.choice(_TRACK_CACHE["calm"])
    else:
        chosen = random.choice(all_tracks)

    return chosen

def get_background_audio(duration, topic=""):
    """Return a low-volume background music AudioFileClip or None."""
    path = pick_track(topic)
    if path is None:
        return None
    try:
        from moviepy import AudioFileClip, concatenate_audioclips
        from moviepy.audio.fx import AudioFadeIn, AudioFadeOut
        music = AudioFileClip(path)
        if music.duration < duration:
            n_loops = int(np.ceil(duration / music.duration))
            music = concatenate_audioclips([music] * n_loops)
        music = music.subclipped(0, duration)
        music = music.with_volume_scaled(0.15)
        fade = min(3.0, duration * 0.1)
        music = music.with_effects([AudioFadeIn(fade), AudioFadeOut(fade)])
        return music
    except Exception:
        return None
