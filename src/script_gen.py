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

def generate_script(language: str = "ar") -> dict:
    history = {"seasons": {}, "current_season": 1, "total": 0, "all_done": False}
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding="utf-8") as f:
            history = json.load(f)

    sid, eid, topic, is_finale = _get_next_episode(history)

    if is_finale or sid is None:
        print(f"  \ud83c\udfc6 \u0643\u0644 \u0627\u0644\u0645\u0648\u0627\u0633\u0645 \u0627\u0643\u062a\u0645\u0644\u062a! \u0625\u0646\u0634\u0627\u0621 \u0641\u064a\u062f\u064a\u0648 \u0627\u0644\u062e\u062a\u0627\u0645...")
        history["all_done"] = True
        topic = "\u0627\u0646\u062a\u0647\u062a \u0631\u062d\u0644\u062a\u0646\u0627 \u0645\u0639 \u0627\u0644\u0623\u0646\u0628\u064a\u0627\u0621 \u0648\u0627\u0644\u0635\u062d\u0627\u0628\u0629... \u0641\u0645\u0627 \u0627\u0644\u0633\u0644\u0633\u0644\u0629 \u0627\u0644\u0642\u0627\u062f\u0645\u0629\u061f"
        idx = "FINALE"
        season_info = {}
        eps_in_season = 0
        eps_total = sum(len(s["episodes"]) for s in SEASONS.values())
    else:
        if str(sid) not in history["seasons"]:
            history["seasons"][str(sid)] = {"completed": [], "status": "active"}
        history["seasons"][str(sid)].setdefault("completed", []).append(eid)
        history["seasons"][str(sid)]["status"] = "active"
        history["current_season"] = sid
        history["total"] = history.get("total", 0) + 1
        idx = eid
        season_config = SEASONS[sid]
        all_eps = [ep[0] for ep in season_config["episodes"]]
        eps_in_season = len([c for c in history["seasons"][str(sid)]["completed"] if c in all_eps])
        eps_total = len(all_eps)
        season_info = {
            "name": season_config["name"],
            "episode_num": eps_in_season,
            "total_eps": eps_total,
        }

        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

        print(f"  \u2139\ufe0f {idx} | \u0627\u0644\u062d\u0644\u0642\u0629 {eps_in_season}/{eps_total}")

    # Build story prompt
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
            intro_line = f"- مقدمة السلسلة: 'مرحباً بكم في الحلقة الأولى من {season_name}'\n"
        if is_last:
            intro_line = "- في النهاية أضف خاتمة الموسم: '" + season_config["finale"] + "'\n"

        story_prompt = (
            "أنت خبير عالمي في صناعة المحتوى الفيروسي على YouTube Shorts ومتخصص في القصص الإسلامية الموثوقة.\n\n"
            f"المطلوب: فيديو قصير عن: {topic}\n"
            f"الحلقة {eps_in_season} من {eps_total} - {season_name}\n\n"
            "---\n"
            "تعليمات صارمة:\n"
            "1. ابدأ بأول 5 ثوانٍ أقوى جملة في الفيديو: سؤال صادم، أو معلومة مذهلة، أو لحظة مشحونة عاطفياً\n"
            "   أمثلة: 'هل تعلم أن هذا الصحابي كان يخاف من شيء واحد فقط؟'\n"
            "          'القصة التي أبكت رسول الله صلى الله عليه وسلم...'\n"
            "          'نبي عاش معجزة لا يصدقها الكثيرون...'\n"
            "2. أسلوب قصصي مشوق وعاطفي سريع الإيقاع\n"
            "3. دقة تاريخية كاملة - التزام بالمعلومات الموثقة\n"
            "4. لغة بسيطة مفهومة لجميع الأعمار\n"
            "5. ذروة درامية تجعل المشاهد يكمل للنهاية\n"
            "6. خاتمة قوية تدفع للتفاعل: سؤال، أو دعاء، أو 'اللهم صل على سيدنا محمد'\n"
            "7. في النهاية اترك فضولاً للجزء القادم\n"
            f"8. المدة: {word_target}\n\n"
            "بعد القصة مباشرة، اكتب سطراً بالصيغة التالية بالضبط:\n"
            "##KEYWORDS## كلمة1, كلمة2, كلمة3, كلمة4, كلمة5, كلمة6, كلمة7, كلمة8\n"
            "(8-10 كلمات إنجليزية عن desert, mosque, islamic, historical, arabian مناسبة للقصة)\n\n"
            "اكتب القصة كاملة ثم الكلمات المفتاحية."
        )

        data = {
            "season_id": sid,
            "season_name": season_name,
            "episode_id": idx,
            "episode_num": eps_in_season,
            "total_eps": eps_total,
        }

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
            "\u0647\u0644 \u062a\u0635\u062f\u0651\u0642 \u0623\u0646\u061f ",
            "\u0642\u0635\u0629 \u0644\u0646 \u062a\u0635\u062f\u0651\u0642\u0647\u0627! ",
            "\u0633\u0628\u062d\u0627\u0646 \u0627\u0644\u0644\u0647! ",
        ]
        story = (
            random.choice(hooks) + topic + ". "
            "\u0647\u0630\u0647 \u0642\u0635\u0629 \u0639\u0638\u064a\u0645\u0629 \u0645\u0646 \u062a\u0627\u0631\u064a\u062e\u0646\u0627 \u0627\u0644\u0625\u0633\u0644\u0627\u0645\u064a. "
            "\u0641\u064a\u0647\u0627 \u0639\u0628\u0631 \u0648\u0639\u0638\u0627\u062a \u0643\u062b\u064a\u0631\u0629. "
            "\u0627\u0644\u0644\u0647\u0645 \u0635\u0644 \u0639\u0644\u0649 \u0633\u064a\u062f\u0646\u0627 \u0645\u062d\u0645\u062f."
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
