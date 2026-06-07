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

UPLOAD_RETRIES = 3

def log_event(event: dict):
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, encoding="utf-8") as f:
            logs = json.load(f)
    logs.append(event)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

def _should_upload():
    """Auto-detect: upload if UPLOAD_TO_YOUTUBE=true OR if credentials exist."""
    env = os.environ.get("UPLOAD_TO_YOUTUBE", "").lower()
    if env == "true":
        return True
    if env == "":
        # auto-detect: try upload if token file exists
        if os.path.exists("token.json") and os.path.exists("client_secrets.json"):
            return True
    return False

def run_one(language: str = None):
    start = time.time()
    lang = "ar"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] بدء: {lang}")

    try:
        sd = generate_script(lang)
        ep = sd.get("episode_id", sd.get("topic_id", ""))
        season_info = ""
        if "season_name" in sd:
            season_info = f" | {sd['season_name']} الحلقة {sd.get('episode_num', '?')}/{sd.get('total_eps', '?')}"
        print(f"  ✓ {ep}{season_info} ({len(sd['story'].split())} كلمة)")

        generate_voiceover(sd)
        print(f"  ✓ صوت ({len(sd.get('word_timings',[]))} كلمة موقتة)")

        footage = download_footage(sd)
        print(f"  ✓ {len(footage)} فيديوهات خلفية")

        create_video(sd, footage)
        print(f"  ✓ فيديو")

        try:
            thumb = generate_thumbnail(sd.get("topic", "قصة إسلامية"))
            sd["thumbnail_file"] = thumb
            print(f"  ✓ صورة مصغرة")
        except Exception as e:
            print(f"  ⚠ فشل الصورة: {e}")

        tid = sd.get("topic_id", sd.get("episode_id", ""))

        if _should_upload():
            last_err = None
            for attempt in range(1, UPLOAD_RETRIES + 1):
                try:
                    url = upload_video(sd)
                    print(f"  ✓ رفع: {url}")
                    log_event({
                        "ts": ts, "topic_id": tid, "topic": sd["topic"],
                        "youtube_url": url, "seconds": round(time.time() - start, 1),
                        "status": "ok",
                    })
                    break
                except Exception as e:
                    last_err = e
                    print(f"  ✗ محاولة {attempt}/{UPLOAD_RETRIES} فشلت: {e}")
                    if attempt < UPLOAD_RETRIES:
                        wait = 10 * attempt
                        print(f"  ⏳ انتظار {wait}ث وإعادة المحاولة...")
                        time.sleep(wait)
            if last_err:
                print(f"  ✗ فشل الرفع بعد {UPLOAD_RETRIES} محاولات: {last_err}")
                log_event({
                    "ts": ts, "topic_id": tid, "topic": sd["topic"],
                    "error": str(last_err), "seconds": round(time.time() - start, 1),
                    "status": "upload_failed",
                })
        else:
            log_event({
                "ts": ts, "topic_id": tid, "topic": sd["topic"],
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
