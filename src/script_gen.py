import json
import os
import random
import re
import shutil
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
                "temperature": 0.5,
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
    if history.get("finale_done"):
        return None, None, None, True
    if history.get("all_done"):
        return None, None, None, True

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
    history = {"seasons": {}, "current_season": 1, "total": 0, "all_done": False, "used_keywords": []}
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            loaded.setdefault("seasons", {})
            loaded.setdefault("current_season", 1)
            loaded.setdefault("total", 0)
            loaded.setdefault("all_done", False)
            loaded.setdefault("used_keywords", [])
            loaded.setdefault("finale_done", False)
            history = loaded
    history.setdefault("used_keywords", [])

    sid, eid, topic, is_finale = _get_next_episode(history)

    if is_finale or sid is None:
        if history.get("finale_done"):
            raise RuntimeError("\u062c\u0645\u064a\u0639 \u0627\u0644\u0641\u064a\u062f\u064a\u0648\u0647\u0627\u062a \u0627\u0643\u062a\u0645\u0644\u062a!")
        print(f"  \ud83c\udfc6 \u0643\u0644 \u0627\u0644\u0645\u0648\u0627\u0633\u0645 \u0627\u0643\u062a\u0645\u0644\u062a! \u0625\u0646\u0634\u0627\u0621 \u0641\u064a\u062f\u064a\u0648 \u0627\u0644\u062e\u062a\u0627\u0645...")
        history["all_done"] = True
        history["finale_done"] = True
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

        # Backup then save history
        if os.path.exists(HISTORY_FILE):
            shutil.copy2(HISTORY_FILE, HISTORY_FILE + ".bak")
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

        word_target = "300 كلمة"

        intro_line = ""
        if is_first:
            intro_line = f"- مقدمة السلسلة: 'مرحباً بكم في الحلقة الأولى من {season_name}'\n"
        if is_last:
            intro_line = "- في النهاية أضف خاتمة الموسم: '" + season_config["finale"] + "'\n"

        story_prompt = (
            "اكتب قصة دينية عن هذا الموضوع:\n"
            f"{topic}\n"
            f"الحلقة {eps_in_season} من {eps_total} - {season_name}\n\n"
            f"العدد: {word_target}\n\n"
            "اكتب بالصيغة التالية بالضبط:\n\n"
            "##TITLE## (عنوان جذاب للقصة)\n"
            "##HOOK## (جملة استفهامية تثير الفضول: هل تعلم، هل تصدق، هل تتوقع)\n"
            "(القصة كاملة بأسلوب مشوق)\n"
            "##TIP1## (نصيحة أولى مستفادة من القصة)\n"
            "##TIP2## (نصيحة ثانية مختلفة عن الأولى)\n"
            "##KEYWORDS## كلمة1, كلمة2, كلمة3, كلمة4, كلمة5, كلمة6, كلمة7, كلمة8\n\n"
            "اكتب المحتوى فقط."
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

    ctr_title = ""
    hook_text = ""
    tip1_text = ""
    tip2_text = ""
    keywords = []
    cine_keywords = []

    text = story_raw

    m = re.search(r'##TITLE##\s*(.*?)(?:\n|$)', text)
    if m:
        ctr_title = m.group(1).strip()[:90]
        text = text.replace(m.group(0), '', 1)

    m = re.search(r'##HOOK##\s*(.*?)(?:\n|$)', text)
    if m:
        hook_text = m.group(1).strip()
        text = text.replace(m.group(0), '', 1)

    m = re.search(r'##TIP1##\s*(.*?)(?:\n|$)', text)
    if m:
        tip1_text = m.group(1).strip()
        text = text.replace(m.group(0), '', 1)

    m = re.search(r'##TIP2##\s*(.*?)(?:\n|$)', text)
    if m:
        tip2_text = m.group(1).strip()
        text = text.replace(m.group(0), '', 1)

    m = re.search(r'##KEYWORDS##\s*(.*?)(?:\n|$)', text)
    if m:
        kw_text = m.group(1).strip()
        text = text.replace(m.group(0), '', 1)
        keywords = [k.strip() for k in kw_text.replace("\n", ",").split(",") if k.strip() and len(k.strip()) > 2]

    story = text.strip()

    if not keywords:
        keywords = random.sample(FALLBACK_KEYWORDS, min(8, len(FALLBACK_KEYWORDS)))

    # Filter out keywords already used in previous episodes
    used_keywords = set(history.get("used_keywords", []))
    keywords = [k for k in keywords if k not in used_keywords]
    if not keywords:
        keywords = random.sample(FALLBACK_KEYWORDS, min(8, len(FALLBACK_KEYWORDS)))
    used_keywords.update(keywords)
    history["used_keywords"] = list(used_keywords)

    if not cine_keywords:
        cine_keywords = FALLBACK_CINE[:]

    # Clean the story text
    story = _clean_text(story)

    if not story:
        hooks = [
            "هل تصدّق أن ",
            "قصة لن تصدقها! ",
            "سبحان الله! ",
            "هل تعلم أن ",
        ]
        hook_choice = random.choice(hooks) + topic + "؟"
        story = (
            hook_choice + " "
            "هذه القصة تحمل عبرة عظيمة. "
            "كان هذا في تاريخ الإسلام. "
            "اللهم صل على سيدنا محمد. "
            "ما رأيك في هذه القصة؟ شاركنا في التعليقات."
        )
        if not hook_text:
            hook_text = hook_choice
        if not tip1_text:
            tip1_text = "توكل على الله في كل أمورك."
        if not tip2_text:
            tip2_text = "الصبر مفتاح الفرج."

    data.update({
        "topic": topic,
        "ctr_title": ctr_title or topic,
        "story": story,
        "hook_text": hook_text,
        "tip1_text": tip1_text,
        "tip2_text": tip2_text,
        "keywords": keywords[:10],
        "cine_keywords": cine_keywords[:6],
    })

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SCRIPTS_DIR, f"script_{ts}_ar.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    if os.path.exists(HISTORY_FILE):
        shutil.copy2(HISTORY_FILE, HISTORY_FILE + ".bak")
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    return data

def _clean_text(text: str) -> str:
    lines = [l.strip() for l in text.strip().split("\n")]

    _blocked_prefixes = (
        "**", "*",
        "المطلوب", "تعليمات", "الهدف", "تعليمات صارمة",
        "أنت خبير", "بعد القصة", "اكتب القصة", "##",
        "##TITLE##", "##HOOK##", "##TIP1##", "##TIP2##", "##KEYWORDS##",
        "إليك", "هذه هي القصة", "القصة:", "القصة المطلوبة",
        "بالطبع", "بالتأكيد", "سأكتب", "إليك النص",
        "الافتتاحية", "الخاتمة", "نص الراوي",
        "الحلقة", "موسم", "الموسم",
        "SEO", "كلمات مفتاحية", "هاشتاغ", "هاشتاج",
        "السطر الأول", "صيغة الخرج", "مثال:", "أمثلة:",
        "تنسيق", "الإخراج", "الخرج",
        "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "0.",
        "1-", "2-", "3-", "4-", "5-",
        "1)", "2)", "3)", "4)", "5)",
    )

    filtered = []
    for line in lines:
        if not line:
            continue
        skip = False
        for p in _blocked_prefixes:
            if line.startswith(p):
                skip = True
                break
        # Skip lines with no Arabic characters
        if not skip:
            arabic_chars = sum(1 for c in line if '\u0600' <= c <= '\u06ff' or '\u0750' <= c <= '\u077f' or '\ufe70' <= c <= '\ufeff')
            if arabic_chars == 0 and len(line) > 2:
                skip = True
        if not skip:
            filtered.append(line)

    story = " ".join(filtered) if filtered else ""
    story = story.strip().strip('"').strip("'").strip("-").strip()
    story = re.sub(r'(?:المطلوب|تعليمات|اكتب القصة)\s*:?\s*', '', story)
    story = re.sub(r'الحلقة\s+\d+\s+من\s+\d+[\s\-]*', '', story)
    story = re.sub(r'\s+', ' ', story).strip()
    return story
