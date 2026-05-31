import asyncio
import edge_tts
import json
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
        communicate = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE)
        words = []
        with open(path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    offset = chunk.get("offset", 0)
                    duration = chunk.get("duration", 0)
                    wtext = chunk.get("text", "").strip()
                    if wtext:
                        words.append({
                            "text": wtext,
                            "start": offset / 10000000,
                            "end": (offset + duration) / 10000000,
                        })
        script_data["word_timings"] = words
        script_data["audio_file"] = path

    asyncio.run(_run())
    return path
