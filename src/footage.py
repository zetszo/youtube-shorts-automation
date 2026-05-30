import requests
import os
import random
from datetime import datetime
from config import PEXELS_API_KEY

FOOTAGE_DIR = "output/footage"
os.makedirs(FOOTAGE_DIR, exist_ok=True)

def download_footage(keywords: list) -> list:
    if not keywords:
        keywords = ["nature", "sky"]

    downloaded = []
    used_kw = set()

    for kw in keywords:
        if kw.lower() in used_kw:
            continue
        used_kw.add(kw.lower())

        params = {
            "query": kw,
            "per_page": 3,
            "orientation": "portrait",
            "size": "medium",
            "min_duration": 5,
        }
        try:
            resp = requests.get(
                "https://api.pexels.com/videos/search",
                params=params,
                headers={"Authorization": PEXELS_API_KEY},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            continue

        for video in data.get("videos", []):
            best = None
            for vf in video.get("video_files", []):
                w, h = vf.get("width"), vf.get("height")
                if w and h and 0.5 <= w / h <= 0.6:
                    best = vf
                    break
            if not best:
                best = (video.get("video_files") or [None])[0]
            if not best or not best.get("link"):
                continue

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(FOOTAGE_DIR, f"ft_{ts}_{kw}_{video['id']}.mp4")
            try:
                r = requests.get(best["link"], timeout=30)
                r.raise_for_status()
                with open(path, "wb") as f:
                    f.write(r.content)
                downloaded.append({"path": path, "duration": video.get("duration", 10)})
            except Exception:
                continue

    return downloaded
