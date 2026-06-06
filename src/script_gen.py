import json
import os
import random
import requests
import time
from datetime import datetime
from config import GROQ_API_KEY, GROQ_MODEL, SEASONS, FINALE_TOPICS

HISTORY_FILE = "output/history.json"
SCRIPTS_DIR = "output/scripts"
os.makedirs(SCRIPTS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)

FALLBACK_KEYWORDS = [
    "desert sand dunes landscape",
    "ancient mosque architecture",
    "camel caravan sunset",
    "mountain valley nature",
    "starry night sky moon",
    "old city arabian building",
    "sunrise golden hour desert",
    "palm trees oasis",
    "arabian horse galloping",
    "dramatic sky clouds",
]

FALLBACK_CINE = [
    "golden hour desert haze",
    "volumetric light rays",
    "dramatic sky sunset",
    "soft cinematic lighting",
    "ancient atmosphere",
    "warm desert tones",
]

_RATE_LIMIT_WAIT = 0

def _groq_complete(prompt: str, retries: int = 5) -> str:
    global _RATE_LIMIT_WAIT
    for attempt in range(retries):
        if _RATE_LIMIT_WAIT > 0:
            wait = _RATE_LIMIT_WAIT
            print(f"  \u23f3 \u0627\u0646\u062a\u0638\u0627\u0631 {wait}\u062b \u0644\u0644\u062a\u0623\u0643\u064a\u062f")
            time.sleep(wait)
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 2048,
            },
            timeout=60,
        )
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            wait = int(retry_after) if retry_after else min(10 * (3 ** attempt), 120)
            _RATE_LIMIT_WAIT = min(wait + 10, 120)
            print(f"  \u23f3 \u062d\u062f \u0627\u0644\u0627\u0633\u062a\u062e\u062f\u0627\u0645 Groq\u060c \u0627\u0646\u062a\u0638\u0627\u0631 {wait}\u062b ({attempt+1}/{retries})")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        _RATE_LIMIT_WAIT = 0
        return resp.json()["choices"][0]["message"]["content"].strip()
    resp.raise_for_status()

def _get_next_episode(history):
    """Return (season_id, episode_id, episode_topic, is_finale) or (None, None, None, True) if all done."""
    seasons = history.get("seasons", {})
    current_season = history.get("current_season", 1)

    for sid in sorted(SEASONS.keys()):
        if sid < current_season:
            continue
        season_data = seasons.get(str(sid), {"completed": [], "status": "pending"})
        season_config = SEASONS[sid]
        completed = set(season_data.get("completed", []))
        all_eps = [ep[0] for ep in season_config["episodes"]]
        remaining = [eid for eid in all_eps if eid not in completed]

        if remaining:
            next_ep_id = remaining[0]
            ep_topic = [ep[1] for ep in season_config["episodes"] if ep[0] == next_ep_id][0]
            return sid, next_ep_id, ep_topic, False

        if sid == max(SEASONS.keys()):
            return None, None, None, True

    return None, None, None, True

def generate_script(language: str = "ar", specific_ep: str = None) -> dict:
    history = {"seasons": {}, "current_season": 1, "total": 0, "all_done": False}
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding="utf-8") as f:
            history = json.load(f)

    # ── resolve which episode to generate ──
    sid, eid, topic = None, None, None
    is_finale = False

    if specific_ep:
        found = False
        for s in sorted(SEASONS.keys()):
            sc = SEASONS[s]
            for ep_id, ep_topic in sc["episodes"]:
                if ep_id == specific_ep:
                    sid, eid, topic = s, ep_id, ep_topic
                    found = True
                    break
            if found:
                break
        if not found:
            print(f"  ⚠️ الحلقة '{specific_ep}' غير موجودة. استخدام التالي.")

    if not eid:
        sid, eid, topic, is_finale = _get_next_episode(history)

    # ── mark in history ──
    if is_finale or sid is None:
        print(f"  🏆 كل المواسم اكتملت! إنشاء فيديو الختام...")
        history["all_done"] = True
        topic = "انتهت رحلتنا مع الأنبياء والصحابة... فما السلسلة القادمة؟"
        idx = "FINALE"
        eps_in_season = 0
        eps_total = sum(len(s["episodes"]) for s in SEASONS.values())
    else:
        if str(sid) not in history["seasons"]:
            history["seasons"][str(sid)] = {"completed": [], "status": "active"}
        completed_list = history["seasons"][str(sid)].setdefault("completed", [])
        if eid not in completed_list:
            completed_list.append(eid)
        history["seasons"][str(sid)]["status"] = "active"
        history["current_season"] = sid
        history["total"] = history.get("total", 0) + 1
        idx = eid
        season_config = SEASONS[sid]
        all_eps = [ep[0] for ep in season_config["episodes"]]
        eps_in_season = len([c for c in completed_list if c in all_eps])
        eps_total = len(all_eps)

        print(f"  ℹ️ {idx} | الحلقة {eps_in_season}/{eps_total}")

    # ── save history early ──
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    # ── build story prompt ──
    if is_finale or sid is None:
        options_str = "\n".join(f"- {t}" for t in FINALE_TOPICS)
        story_prompt = (
            f"اكتب نصاً قصيراً بالعربية بعنوان: {topic}\n\n"
            "المطلوب:\n"
            "- المدة: 40-50 ثانية (100-150 كلمة)\n"
            "- اشكر المتابعين على رحلة الأنبياء والصحابة\n"
            "- اطلب من المشاهدين التصويت على الموسم القادم من خلال التعليقات\n"
            f"خيارات التصويت:\n{options_str}\n\n"
            "خاتمة: 'لا تنس الاشتراك وتفعيل الجرس للموسم القادم!'"
        )
        data = {
            "topic_id": "FINALE",
            "topic": topic,
            "season": "finale",
            "episode": "finale",
            "finale_topics": FINALE_TOPICS,
        }
    else:
        season_config = SEASONS[sid]
        is_first = eps_in_season == 1
        is_last = eps_in_season == eps_total
        season_name = season_config["name"]

        word_target = "60-80 ثانية (150-200 كلمة)" if sid == 3 else "90-120 ثانية (250-350 كلمة)"

        intro_line = ""
        if is_first:
            intro_line = f"- ابدأ الحلقة بمقدمة: 'مرحباً بكم في الحلقة الأولى من {season_name}'\n"
        if is_last:
            intro_line = "- في نهاية القصة، أضف: '" + season_config["finale"] + "'\n"

        story_prompt = (
            f"اكتب قصة قصيرة فيرالية بالعربية عن: {topic}\n\n"
            f"الحلقة {eps_in_season} من {eps_total} - {season_name}\n\n"
            "هندسة الانتشار (viral):\n"
            f"{intro_line}"
            "- ابدأ بجملة صادمة تشد الانتباه في أول 3 ثوان\n"
            f"- المدة: {word_target}\n"
            "- أسلوب مؤثر يحرك المشاعر\n"
            "- خاتمة: 'اللهم صل على سيدنا محمد' + دعوة للمشاركة\n\n"
            "بعد القصة، اكتب سطراً على هذه الصيغة:\n"
            "##KEYWORDS## desert sand dunes, ancient mosque, camel sunset\n"
            "(استبدل الكلمات بما يناسب القصة، 8-10 كلمات إنجليزية)\n\n"
            "اكتب القصة ثم الكلمات المفتاحية."
        )

        data = {
            "season_id": sid,
            "season_name": season_name,
            "episode_id": idx,
            "episode_num": eps_in_season,
            "total_eps": eps_total,
        }

    # ── call Groq ──
    try:
        story_raw = _groq_complete(story_prompt)
    except Exception:
        story_raw = ""

    story = story_raw
    keywords = []
    cine_keywords = []

    if "##KEYWORDS##" in story_raw:
        parts = story_raw.split("##KEYWORDS##")
        story = parts[0].strip()
        kw_text = parts[1].strip()
        keywords = [k.strip() for k in kw_text.replace("\n", ",").split(",") if k.strip() and len(k.strip()) > 2]

    if not keywords:
        keywords = random.sample(FALLBACK_KEYWORDS, min(8, len(FALLBACK_KEYWORDS)))

    if not cine_keywords:
        cine_keywords = FALLBACK_CINE[:]

    if not story:
        hooks = [
            "هل تصدّق أن؟ ",
            "قصة لن تصدّقها! ",
            "سبحان الله! ",
        ]
        story = (
            random.choice(hooks) + topic + ". "
            "هذه قصة عظيمة من تاريخنا الإسلامي. "
            "فيها عبر وعظات كثيرة. "
            "اللهم صل على سيدنا محمد."
        )

    story = _clean_text(story)

    data.update({
        "topic": topic,
        "story": story,
        "keywords": keywords[:10],
        "cine_keywords": cine_keywords[:6],
    })

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SCRIPTS_DIR, f"script_{ts}_ar.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    return data

def _clean_text(text: str) -> str:
    lines = [l.strip() for l in text.strip().split("\n")]
    lines = [l for l in lines if l and not l.startswith(("**", "*"))]
    return " ".join(lines)
