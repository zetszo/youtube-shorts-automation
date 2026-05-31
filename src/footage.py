import requests
import os
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import PEXELS_API_KEY

FOOTAGE_DIR = "output/footage"
os.makedirs(FOOTAGE_DIR, exist_ok=True)

# أولويات البحث: طبيعة + عمارة إسلامية + رجال فقط إن لزم
SAFE_QUERIES = [
    "desert landscape sand dunes",
    "mountain landscape nature",
    "sunset golden hour sky",
    "stars night sky moon",
    "ocean sea waves nature",
    "palm trees oasis desert",
    "ancient mosque architecture",
    "old city arabian architecture",
    "historical mid eastern building",
    "man walking traditional robe",
    "men traditional middle eastern",
    "camel desert caravan",
    "horse arabian desert",
    "clouds dramatic sky cinematic",
    "sunrise over desert landscape",
    "sand dunes golden light",
    "ancient ruins middle eastern",
    "arabian desert nature",
    "bird flying sky freedom",
    "valley mountain landscape",
]

def _add_context(kw: str) -> list:
    """توليد كلمات بحث متعددة مع سياق إسلامي محتشم"""
    base = kw.strip().lower()
    results = []
    # البحث الأساسي
    results.append(base)
    # مع سياق تاريخي
    results.append(f"{base} historical ancient")
    # مع طبيعة
    results.append(f"{base} desert landscape nature")
    # مع رجال (بدون نساء)
    if any(w in base for w in ["person", "people", "human", "man", "woman", "walk", "stand"]):
        results.append(base.replace("woman", "man").replace("people", "men").replace("person", "man"))
    return results

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

    search_queries = []

    # 1. كلمات من السكربت + سياق إسلامي/تاريخي
    for kw in keywords[:6]:
        for variant in _add_context(kw):
            search_queries.append(("script", variant))

    # 2. كلمات آمنة مضمونة (طبيعة، عمارة، الخ)
    safe_sample = random.sample(SAFE_QUERIES, min(6, len(SAFE_QUERIES)))
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

    # ترتيب: safe queries أولاً (مضمونة)، ثم script queries
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
