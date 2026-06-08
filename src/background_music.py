import os
import urllib.request
import tempfile
import numpy as np

MUSIC_DIR = "assets"
os.makedirs(MUSIC_DIR, exist_ok=True)

# Free ambient tracks from reliable CDN
_FALLBACK_URLS = [
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-4.mp3",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-5.mp3",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-6.mp3",
]

_LOCAL_FILE = os.path.join(MUSIC_DIR, "background_music.mp3")

def _download_track(url, dest):
    try:
        urllib.request.urlretrieve(url, dest)
        return os.path.getsize(dest) > 10000
    except Exception:
        return False

def ensure_music():
    """Download a background music track if not present locally."""
    if os.path.exists(_LOCAL_FILE) and os.path.getsize(_LOCAL_FILE) > 10000:
        return _LOCAL_FILE
    for url in _FALLBACK_URLS:
        if _download_track(url, _LOCAL_FILE):
            return _LOCAL_FILE
    return None

def get_background_audio(duration):
    """Return a low-volume background music AudioFileClip or None."""
    path = ensure_music()
    if path is None:
        return None
    try:
        from moviepy import AudioFileClip, concatenate_audioclips
        from moviepy.audio.fx import AudioFadeIn, AudioFadeOut
        music = AudioFileClip(path)
        # Loop to match video duration
        if music.duration < duration:
            n_loops = int(np.ceil(duration / music.duration))
            music = concatenate_audioclips([music] * n_loops)
        music = music.subclipped(0, duration)
        # Lower volume to 15%
        music = music.with_volume_scaled(0.15)
        # Fade in/out
        fade = min(3.0, duration * 0.1)
        music = music.with_effects([AudioFadeIn(fade), AudioFadeOut(fade)])
        return music
    except Exception:
        return None
