import sys
import json
import random
import time
import os
from datetime import datetime
from config import VIDEOS_PER_DAY
from script_gen import generate_script
from voiceover import generate_voiceover
from footage import download_footage
from video_editor import create_video
from uploader import upload_video

LOG_FILE = "output/log.json"
os.makedirs("output", exist_ok=True)

def log_event(event: dict):
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, encoding="utf-8") as f:
            logs = json.load(f)
    logs.append(event)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

def run_one(language: str = None):
    start = time.time()
    lang = language or random.choice(["ar", "en"])
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] بدء: {lang}")

    try:
        sd = generate_script(lang)
        print(f"  ✓ قصة ({len(sd['story'].split())} كلمة)")

        generate_voiceover(sd)
        print(f"  ✓ صوت")

        footage = download_footage(sd["keywords"])
        print(f"  ✓ {len(footage)} فيديوهات")

        create_video(sd, footage)
        print(f"  ✓ فيديو")

        url = upload_video(sd)
        print(f"  ✓ رفع: {url}")

        log_event({
            "ts": ts, "lang": lang, "topic": sd["topic"],
            "youtube_url": url, "seconds": round(time.time() - start, 1),
            "status": "ok",
        })
        return True
    except Exception as e:
        log_event({"ts": ts, "lang": lang, "error": str(e), "status": "fail"})
        print(f"  ✗ {e}")
        return False

def daily():
    print(f"🔥 {VIDEOS_PER_DAY} فيديوهات اليوم")
    for i in range(VIDEOS_PER_DAY):
        lang = "ar" if i % 2 == 0 else "en"
        print(f"\n--- {i+1}/{VIDEOS_PER_DAY} ({lang}) ---")
        run_one(lang)
        if i < VIDEOS_PER_DAY - 1:
            wait = random.randint(120, 300)
            print(f"⏳ {wait//60} د...")
            time.sleep(wait)

if __name__ == "__main__":
    if sys.argv[1:2] == ["daily"]:
        daily()
    elif sys.argv[1:2]:
        run_one(sys.argv[1])
    else:
        run_one()
