import asyncio
import edge_tts
import os
from datetime import datetime
from config import TTS_VOICE, TTS_RATE

AUDIO_DIR = "output/audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

def generate_voiceover(script_data: dict) -> str:
    text = script_data["story"]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(AUDIO_DIR, f"audio_{ts}_ar.mp3")

    async def _run():
        c = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE)
        await c.save(path)

    asyncio.run(_run())
    script_data["audio_file"] = path
    return path
