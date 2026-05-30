import asyncio
import edge_tts
import os
from datetime import datetime
from config import TTS_VOICE_ARABIC, TTS_VOICE_ENGLISH, TTS_RATE

AUDIO_DIR = "output/audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

def generate_voiceover(script_data: dict) -> str:
    lang = script_data["language"]
    text = script_data["story"]
    voice = TTS_VOICE_ARABIC if lang == "ar" else TTS_VOICE_ENGLISH

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(AUDIO_DIR, f"audio_{ts}_{lang}.mp3")

    async def _run():
        c = edge_tts.Communicate(text, voice, rate=TTS_RATE)
        await c.save(path)

    asyncio.run(_run())
    script_data["audio_file"] = path
    return path
