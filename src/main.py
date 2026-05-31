import sys
import json
import random
import time
import os
from datetime import datetime
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
    lang = "ar"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] بدء: {lang}")

    try:
        sd = generate_script(lang)
        print(f"  ✓ قصة ({len(sd['story'].split())} كلمة)")

        generate_voiceover(sd)
        print(f"  ✓ صوت")

        footage = download_footage(sd)
        print(f"  ✓ {len(footage)} فيديوهات")

        create_video(sd, footage)
        print(f"  ✓ فيديو")

        if os.environ.get("UPLOAD_TO_YOUTUBE", "").lower() == "true":
            url = upload_video(sd)
            print(f"  ✓ رفع: {url}")
            log_event({
                "ts": ts, "lang": lang, "topic": sd["topic"],
                "youtube_url": url, "seconds": round(time.time() - start, 1),
                "status": "ok",
            })
        else:
            log_event({
                "ts": ts, "lang": lang, "topic": sd["topic"],
                "video_file": sd.get("video_file"),
                "seconds": round(time.time() - start, 1),
                "status": "preview",
            })
        return True
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log_event({"ts": ts, "lang": lang, "error": str(e), "traceback": tb, "status": "fail"})
        print(f"  ✗ {e}")
        print(tb)
        return False

def daily() -> bool:
    return run_one()

if __name__ == "__main__":
    if sys.argv[1:2] == ["daily"]:
        ok = daily()
    elif sys.argv[1:2]:
        ok = run_one(sys.argv[1])
    else:
        ok = run_one()
    sys.exit(0 if ok else 1)
