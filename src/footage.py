import requests
import os
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import PEXELS_API_KEY

FOOTAGE_DIR = "output/footage"
os.makedirs(FOOTAGE_DIR, exist_ok=True)

CINE_MODIFIERS = [
    "cinematic lighting",
    "volumetric light rays",
    "golden hour",
    "soft shadows",
    "dramatic sky",
    "ancient architecture",
]

def _search_pexels(query: str) -> list:
    results = []
    params = {
        "query": query,
        "per_page": 8,
        "orientation": "portrait",
        "size": "medium",
        "min_duration": 4,
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
    path = os.path.join(FOOTAGE_DIR, f"ft_{ts}_{item['query'][:20]}_{item['id']}.mp4")
    try:
        r = requests.get(item["link"], timeout=30)
        r.raise_for_status()
        with open(path, "wb") as f:
            f.write(r.content)
        return {"path": path, "duration": item["duration"], "keyword": item["query"]}
    except Exception:
        return None

def download_footage(script_data: dict, max_clips: int = 15) -> list:
    keywords = script_data.get("keywords", [])
    cine_kw = script_data.get("cine_keywords", [])

    if not keywords:
        keywords = ["desert landscape", "sky clouds", "ancient city"]

    search_queries = []
    # Literal scene matches (highest priority)
    for kw in keywords:
        search_queries.append(("literal", kw))
        # Also search with an Islamic modifier for spiritual tone
        search_queries.append(("literal", f"{kw} mosque"))
    # Cinematic premium queries
    modifier = cine_kw[0] if cine_kw else random.choice(CINE_MODIFIERS)
    for kw in keywords[:4]:
        search_queries.append(("cine", f"{kw} {modifier}"))

    all_candidates = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(_search_pexels, q[1]): q for q in search_queries}
        for future in as_completed(futures):
            try:
                results = future.result()
                qtype, q = futures[future]
                for r in results:
                    r["qtype"] = qtype
                all_candidates.extend(results)
            except Exception:
                pass

    seen = set()
    unique = []
    for c in all_candidates:
        if c["id"] not in seen:
            seen.add(c["id"])
            unique.append(c)

    # Prioritize literal matches first, then cinematic
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
