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
from thumbnail import generate_thumbnail
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
    print(f"[{ts}] \u0628\u062f\u0621: {lang}")

    try:
        sd = generate_script(lang)
        ep = sd.get("episode_id", sd.get("topic_id", ""))
        season_info = ""
        if "season_name" in sd:
            season_info = f" | {sd['season_name']} \u0627\u0644\u062d\u0644\u0642\u0629 {sd.get('episode_num', '?')}/{sd.get('total_eps', '?')}"
        print(f"  \u2713 {ep}{season_info} ({len(sd['story'].split())} \u0643\u0644\u0645\u0629)")

        generate_voiceover(sd)
        print(f"  \u2713 \u0635\u0648\u062a ({len(sd.get('word_timings',[]))} \u0643\u0644\u0645\u0629 \u0645\u0648\u0642\u062a\u0629)")

        footage = download_footage(sd)
        print(f"  \u2713 {len(footage)} \u0641\u064a\u062f\u064a\u0648\u0647\u0627\u062a \u062e\u0644\u0641\u064a\u0629")

        create_video(sd, footage)
        print(f"  \u2713 \u0641\u064a\u062f\u064a\u0648")

        try:
            thumb = generate_thumbnail(sd.get("topic", "\u0642\u0635\u0629 \u0625\u0633\u0644\u0627\u0645\u064a\u0629"))
            sd["thumbnail_file"] = thumb
            print(f"  \u2713 \u0635\u0648\u0631\u0629 \u0645\u0635\u063a\u0631\u0629")
        except Exception as e:
            print(f"  \u26a0 \u0641\u0634\u0644 \u0627\u0644\u0635\u0648\u0631\u0629: {e}")

        if os.environ.get("UPLOAD_TO_YOUTUBE", "").lower() == "true":
            try:
                url = upload_video(sd)
                print(f"  \u2713 \u0631\u0641\u0639: {url}")
                log_event({
                    "ts": ts, "topic_id": sd["topic_id"], "topic": sd["topic"],
                    "youtube_url": url, "seconds": round(time.time() - start, 1),
                    "status": "ok",
                })
            except Exception as e:
                print(f"  \u2717 \u0641\u0634\u0644 \u0627\u0644\u0631\u0641\u0639: {e}")
                log_event({
                    "ts": ts, "topic_id": sd["topic_id"], "topic": sd["topic"],
                    "error": str(e), "seconds": round(time.time() - start, 1),
                    "status": "upload_failed",
                })
        else:
            log_event({
                "ts": ts, "topic_id": sd["topic_id"], "topic": sd["topic"],
                "video_file": sd.get("video_file"),
                "seconds": round(time.time() - start, 1),
                "status": "preview",
            })
        return True
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log_event({"ts": ts, "lang": lang, "error": str(e), "traceback": tb, "status": "fail"})
        print(f"  \u2717 {e}")
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
