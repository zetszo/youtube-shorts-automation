import requests
import os
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import PEXELS_API_KEY

FOOTAGE_DIR = "output/footage"
os.makedirs(FOOTAGE_DIR, exist_ok=True)

# Islamic/historical context modifiers تضاف لكل بحث
ISLAMIC_MODIFIERS = [
    "historical middle eastern",
    "ancient desert landscape",
    "old city architecture",
    "middle eastern nature",
    "desert sand dunes",
    "ancient arabian",
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

    # نضيف modifier إسلامي/تاريخي لكل كلمة
    modifier = random.choice(ISLAMIC_MODIFIERS)

    search_queries = []
    for kw in keywords:
        # بحث بالكلمة + السياق التاريخي
        search_queries.append(("literal", f"{kw} {modifier}"))
        search_queries.append(("literal", kw))  # original also

    # بحث سينمائي بدون ما نضيف حاجات حديثة
    for kw in keywords[:4]:
        cine = random.choice(cine_kw) if cine_kw else random.choice(ISLAMIC_MODIFIERS)
        search_queries.append(("cine", f"{kw} {cine}"))

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

    # نفضل النتائج اللي فيها modifier تاريخي
    priority = [c for c in unique if c.get("qtype") == "literal" and modifier in c.get("query", "")]
    rest = [c for c in unique if c not in priority]
    random.shuffle(priority)
    random.shuffle(rest)
    ordered = (priority + rest)[:max_clips]

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
