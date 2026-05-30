import requests
import os
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import PEXELS_API_KEY

FOOTAGE_DIR = "output/footage"
os.makedirs(FOOTAGE_DIR, exist_ok=True)

def _search_pexels(query: str) -> list:
    results = []
    params = {
        "query": query,
        "per_page": 5,
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
        for video in data.get("videos", []):
            best = None
            for vf in video.get("video_files", []):
                w, h = vf.get("width"), vf.get("height")
                if w and h and 0.5 <= w / h <= 0.6 and vf.get("quality") == "hd":
                    best = vf
                    break
            if not best:
                for vf in video.get("video_files", []):
                    w, h = vf.get("width"), vf.get("height")
                    if w and h and 0.5 <= w / h <= 0.6:
                        best = vf
                        break
            if not best:
                best = (video.get("video_files") or [None])[0]
            if not best or not best.get("link"):
                continue
            results.append({
                "link": best["link"],
                "duration": video.get("duration", 10),
                "id": video["id"],
                "query": query,
            })
    except Exception:
        pass
    return results

def _download_video(item: dict) -> dict:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(FOOTAGE_DIR, f"ft_{ts}_{item['query']}_{item['id']}.mp4")
    try:
        r = requests.get(item["link"], timeout=30)
        r.raise_for_status()
        with open(path, "wb") as f:
            f.write(r.content)
        return {"path": path, "duration": item["duration"]}
    except Exception:
        return None

def download_footage(keywords: list, max_clips: int = 15) -> list:
    if not keywords:
        keywords = ["nature", "sky", "desert"]

    # Search with each keyword and also with related Islamic terms
    search_queries = []
    for kw in keywords[:5]:
        search_queries.append(kw)
        # Add combined queries for better relevance
        search_queries.append(f"{kw} nature landscape")

    all_candidates = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_search_pexels, q): q for q in search_queries}
        for future in as_completed(futures):
            try:
                all_candidates.extend(future.result())
            except Exception:
                pass

    # Deduplicate by video id
    seen = set()
    unique = []
    for c in all_candidates:
        if c["id"] not in seen:
            seen.add(c["id"])
            unique.append(c)

    random.shuffle(unique)
    target = unique[:max_clips]

    downloaded = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(_download_video, item) for item in target]
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    downloaded.append(result)
            except Exception:
                pass

    return downloaded
