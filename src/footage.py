import requests
import os
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import PEXELS_API_KEY

FOOTAGE_DIR = "output/footage"
os.makedirs(FOOTAGE_DIR, exist_ok=True)

SAFE_QUERIES = [
    "desert landscape sand dunes golden hour",
    "sunrise over arabian desert nature",
    "starry night desert sky moon",
    "ancient mosque architecture old city",
    "camel caravan desert sunset",
    "arabian horse galloping desert dust",
    "palm trees oasis desert landscape",
    "rocky desert mountains dramatic sky",
    "sunset golden light sand dunes",
    "old arabian city ancient architecture",
    "minaret mosque silhouette sunset",
    "cave entrance rocky mountain desert",
    "clouds dramatic sky cinematic desert",
    "medina old city historical architecture",
    "sand storm desert dust dramatic",
    "volumetric light rays mosque interior",
    "crescent moon night sky stars",
    "arabian peninsula desert landscape",
    "ancient ruins stone columns sunset",
    "calligraphy islamic art manuscript",
    "desert camp tent traditional nomadic",
    "mountain valley sunrise golden hour",
    "sea coast mediterranean sunset",
    "candle flame light darkness",
]

def _add_context(kw: str) -> list:
    base = kw.strip().lower()
    results = []
    results.append(base)
    results.append(f"{base} historical ancient arabian")
    results.append(f"{base} desert landscape cinematic")
    if any(w in base for w in ["person", "people", "human", "man", "walk", "stand"]):
        results.append(base.replace("woman", "man").replace("people", "men").replace("person", "man"))
    return results

def _search_pexels(query: str) -> list:
    results = []
    params = {
        "query": query,
        "per_page": 12,
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

def download_footage(script_data: dict, max_clips: int = 25) -> list:
    keywords = script_data.get("keywords", [])

    search_queries = []

    for kw in keywords[:10]:
        for variant in _add_context(kw):
            search_queries.append(("script", variant))

    safe_sample = random.sample(SAFE_QUERIES, min(8, len(SAFE_QUERIES)))
    for sq in safe_sample:
        search_queries.append(("safe", sq))

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

    ordered = [c for c in unique if c["qtype"] == "safe"]
    ordered += [c for c in unique if c["qtype"] == "script" and c not in ordered]
    ordered = ordered[:max_clips]

    downloaded = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(_download_video, item) for item in ordered]
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    downloaded.append(result)
            except Exception:
                pass

    return downloaded
