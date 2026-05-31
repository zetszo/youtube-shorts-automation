import json
import os
import requests
from datetime import datetime
from config import GROQ_API_KEY, GROQ_MODEL, TOPICS_ARABIC

HISTORY_FILE = "output/history.json"
SCRIPTS_DIR = "output/scripts"
os.makedirs(SCRIPTS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)

def _groq_complete(prompt: str) -> str:
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
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

def generate_script(language: str = "ar") -> dict:
    history = 0
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding="utf-8") as f:
            history = json.load(f).get("count", 0)

    history += 1
    idx = (history - 1) % len(TOPICS_ARABIC)
    topic = TOPICS_ARABIC[idx]
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

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump({"count": history}, f, ensure_ascii=False, indent=2)

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
        "language": "ar",
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
