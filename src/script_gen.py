import json
import os
import random
import requests
import time
from datetime import datetime
from config import GROQ_API_KEY, GROQ_MODEL, TOPICS_ARABIC

HISTORY_FILE = "output/history.json"
SCRIPTS_DIR = "output/scripts"
os.makedirs(SCRIPTS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)

def _groq_complete(prompt: str, retries: int = 5) -> str:
    for attempt in range(retries):
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
                "max_tokens": 1024,
            },
            timeout=60,
        )
        if resp.status_code == 429:
            wait = 2 ** attempt
            print(f"  ⏳ Groq rate limit, انتظار {wait}ث ({attempt+1}/{retries})")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    resp.raise_for_status()

def generate_script(language: str = "ar") -> dict:
    history = {"used_ids": [], "total": 0, "next_dynamic_id": 21, "custom_topics": {}}
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding="utf-8") as f:
            history = json.load(f)

    # Check if any predefined topics are still unused
    available = [t for t in TOPICS_ARABIC if t[0] not in history["used_ids"]]

    if available:
        idx, topic = random.choice(available)
        print(f"  📜 قصة #{idx} من القائمة")
    else:
        # All predefined topics used — generate a brand new topic via Groq
        used_list = TOPICS_ARABIC + [(k, v) for k, v in history.get("custom_topics", {}).items()]
        used_str = "\n".join(f"- {t}" for _, t in used_list)
        new_topic_prompt = (
            "اقترح موضوعاً جديداً وفريداً لقصة إسلامية قصيرة لم يُستخدم من قبل.\n"
            "المواضيع المستخدمة سابقاً:\n"
            f"{used_str}\n\n"
            "اكتب موضوعاً واحداً فقط مختلفاً تماماً عما سبق:\n"
            "مثال: قصة سيدنا إسحاق عليه السلام أو قصة عبد الرحمن بن عوف رضي الله عنه"
        )
        new_topic = _groq_complete(new_topic_prompt)
        new_topic = new_topic.strip().strip('"').strip("'")
        idx = history["next_dynamic_id"]
        history["next_dynamic_id"] += 1
        topic = new_topic
        history.setdefault("custom_topics", {})[str(idx)] = topic
        print(f"  🆕 قصة #{idx} جديدة: {topic[:50]}...")

    history["used_ids"].append(idx)
    history["total"] += 1

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    prompt = (
        f"اكتب قصة قصيرة بالعربية الفصحى عن: {topic}\n\n"
        "المتطلبات:\n"
        "- المدة: 45-55 ثانية عند القراءة (150-200 كلمة)\n"
        "- ابدأ بمقدمة تشد الانتباه\n"
        "- التزم بالرواية الإسلامية الصحيحة\n"
        "- القصة واضحة ومؤثرة ولها عبرة وعظة\n"
        "- خاتمة قوية وحكمة مستفادة\n"
        "- أسلوب سردي أدبي جذاب\n"
        "- مناسبة لجميع الأعمار\n"
        "- ذكر الآيات أو الأحاديث إن أمكن\n\n"
        "اكتب القصة فقط بدون عنوان."
    )

    story = _groq_complete(prompt)
    story = _clean_text(story)
    time.sleep(1)

    scene_prompt = (
        "Extract 7 specific LITERAL visual scenes from this Arabic story.\n"
        "Each scene must be a concrete English keyword (2-4 words) that EXACTLY matches a moment.\n"
        "NO metaphors, NO abstract concepts. Only things you can SEE in a video.\n"
        "Examples: Moses staff turning snake, fire burning wood, man walking through parted sea,\n"
        "baby floating in river basket, man climbing mountain with sheep.\n"
        f"Story:\n{story}\n"
        "7 comma-separated keywords (each 2-4 specific words):"
    )
    keywords_raw = _groq_complete(scene_prompt)
    keywords = [k.strip() for k in keywords_raw.replace("\n", ",").split(",") if k.strip()]
    time.sleep(1)

    cine_prompt = (
        "For this story, list 6 cinematic search modifiers for premium video footage.\n"
        "Example: volumetric light rays, golden hour desert, soft shadows mosque,\n"
        "ancient architecture sunrise, dramatic sky sunset, candlelight interior\n"
        f"Story:\n{story}\n"
        "6 comma-separated cinematic modifiers only:"
    )
    cine_raw = _groq_complete(cine_prompt)
    cine_keywords = [k.strip() for k in cine_raw.replace("\n", ",").split(",") if k.strip()]

    data = {
        "topic_id": idx,
        "topic": topic,
        "story": story,
        "keywords": keywords[:7],
        "cine_keywords": cine_keywords[:6],
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SCRIPTS_DIR, f"script_{ts}_ar.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data

def _clean_text(text: str) -> str:
    lines = [l.strip() for l in text.strip().split("\n")]
    lines = [l for l in lines if l and not l.startswith(("**", "*"))]
    return " ".join(lines)
