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
            print(f"  \u23f3 Groq rate limit, \u0627\u0646\u062a\u0638\u0627\u0631 {wait}\u062b ({attempt+1}/{retries})")
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

    available = [t for t in TOPICS_ARABIC if t[0] not in history["used_ids"]]

    if available:
        idx, topic = random.choice(available)
        print(f"  \u2139\ufe0f \u0642\u0635\u0629 #{idx}")
    else:
        used_list = TOPICS_ARABIC + [(k, v) for k, v in history.get("custom_topics", {}).items()]
        used_str = "\n".join(f"- {t}" for _, t in used_list)
        new_topic_prompt = (
            "\u0627\u0642\u062a\u0631\u062d \u0645\u0648\u0636\u0648\u0639\u0627\u064b \u062c\u062f\u064a\u062f\u0627\u064b \u0648\u0641\u0631\u064a\u062f\u0627\u064b \u0644\u0642\u0635\u0629 \u0625\u0633\u0644\u0627\u0645\u064a\u0629 \u0642\u0635\u064a\u0631\u0629 \u0644\u0645 \u064a\u0633\u062a\u062e\u062f\u0645 \u0645\u0646 \u0642\u0628\u0644.\n"
            "\u0627\u0644\u0645\u0648\u0627\u0636\u064a\u0639 \u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645\u0629 \u0633\u0627\u0628\u0642\u0627\u064b:\n"
            f"{used_str}\n\n"
            "\u0627\u0643\u062a\u0628 \u0645\u0648\u0636\u0648\u0639\u0627\u064b \u0648\u0627\u062d\u062f\u0627\u064b \u0641\u0642\u0637 \u0645\u062e\u062a\u0644\u0641\u0627\u064b \u062a\u0645\u0627\u0645\u0627\u064b \u0639\u0645\u0627 \u0633\u0628\u0642:\n"
            "\u0645\u062b\u0627\u0644: \u0642\u0635\u0629 \u0633\u064a\u062f\u0646\u0627 \u0625\u0633\u062d\u0627\u0642 \u0639\u0644\u064a\u0647 \u0627\u0644\u0633\u0644\u0627\u0645 \u0623\u0648 \u0642\u0635\u0629 \u0639\u0628\u062f \u0627\u0644\u0631\u062d\u0645\u0646 \u0628\u0646 \u0639\u0648\u0641 \u0631\u0636\u064a \u0627\u0644\u0644\u0647 \u0639\u0646\u0647"
        )
        new_topic = _groq_complete(new_topic_prompt)
        new_topic = new_topic.strip().strip('"').strip("'")
        idx = history["next_dynamic_id"]
        history["next_dynamic_id"] += 1
        topic = new_topic
        history.setdefault("custom_topics", {})[str(idx)] = topic
        print(f"  \ud83d\udd04 \u0642\u0635\u0629 #{idx} \u062c\u062f\u064a\u062f\u0629")

    history["used_ids"].append(idx)
    history["total"] += 1

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    prompt = (
        f"\u0627\u0643\u062a\u0628 \u0642\u0635\u0629 \u0642\u0635\u064a\u0631\u0629 \u0628\u0627\u0644\u0639\u0631\u0628\u064a\u0629 \u0627\u0644\u0641\u0635\u062d\u0649 \u0639\u0646: {topic}\n\n"
        "\u0627\u0644\u0645\u062a\u0637\u0644\u0628\u0627\u062a:\n"
        "- \u0627\u0644\u0645\u062f\u0629: 45-55 \u062b\u0627\u0646\u064a\u0629 \u0639\u0646\u062f \u0627\u0644\u0642\u0631\u0627\u0621\u0629 (150-200 \u0643\u0644\u0645\u0629)\n"
        "- \u0627\u0628\u062f\u0623 \u0628\u0645\u0642\u062f\u0645\u0629 \u062a\u0634\u062f \u0627\u0644\u0627\u0646\u062a\u0628\u0627\u0647 \u0648\u062a\u0635\u0641 \u0627\u0644\u0645\u0634\u0647\u062f\n"
        "- \u0627\u0644\u062a\u0632\u0645 \u0628\u0627\u0644\u0631\u0648\u0627\u064a\u0629 \u0627\u0644\u0625\u0633\u0644\u0627\u0645\u064a\u0629 \u0627\u0644\u0635\u062d\u064a\u062d\u0629\n"
        "- \u0627\u0633\u062a\u062e\u062f\u0645 \u0623\u0644\u0641\u0627\u0638\u0627\u064b \u0648\u0635\u0641\u064a\u0629 \u062a\u0646\u0627\u0633\u0628 \u0639\u0635\u0631 \u0627\u0644\u0635\u062d\u0627\u0628\u0629 \u0648\u0627\u0644\u0623\u0646\u0628\u064a\u0627\u0621: \u0627\u0644\u0635\u062d\u0631\u0627\u0621\u060c \u0627\u0644\u0631\u0645\u0627\u0644\u060c \u0627\u0644\u062c\u0645\u0627\u0644\u060c \u0627\u0644\u062e\u064a\u0644\u060c \u0627\u0644\u0633\u064a\u0648\u0641\u060c \u0627\u0644\u0646\u062e\u064a\u0644\u060c \u0627\u0644\u0628\u062d\u0631\u060c \u0627\u0644\u062c\u0628\u0627\u0644\u060c \u0627\u0644\u0645\u0633\u0627\u062c\u062f\u060c \u0627\u0644\u0642\u0645\u0631\u060c \u0627\u0644\u0646\u062c\u0648\u0645\u060c \u0627\u0644\u0641\u062c\u0631\u060c \u0627\u0644\u063a\u0631\u0648\u0628\n"
        "- \u0627\u0644\u0642\u0635\u0629 \u0648\u0627\u0636\u062d\u0629 \u0648\u0645\u0624\u062b\u0631\u0629 \u0648\u0644\u0647\u0627 \u0639\u0628\u0631\u0629 \u0648\u0639\u0638\u0629\n"
        "- \u062e\u0627\u062a\u0645\u0629 \u0642\u0648\u064a\u0629 \u0648\u062d\u0643\u0645\u0629 \u0645\u0633\u062a\u0641\u0627\u062f\u0629\n"
        "- \u0623\u0633\u0644\u0648\u0628 \u0633\u0631\u062f\u064a \u0623\u062f\u0628\u064a \u062c\u0630\u0627\u0628 \u0628\u0623\u0644\u0641\u0627\u0638 \u0641\u0635\u064a\u062d\u0629\n"
        "- \u0630\u0643\u0631 \u0627\u0644\u0622\u064a\u0627\u062a \u0623\u0648 \u0627\u0644\u0623\u062d\u0627\u062f\u064a\u062b \u0625\u0646 \u0623\u0645\u0643\u0646\n\n"
        "\u0627\u0643\u062a\u0628 \u0627\u0644\u0642\u0635\u0629 \u0641\u0642\u0637 \u0628\u062f\u0648\u0646 \u0639\u0646\u0648\u0627\u0646."
    )

    story = _groq_complete(prompt)
    story = _clean_text(story)
    time.sleep(1)

    scene_prompt = (
        "Extract 7 visual search keywords in English for video footage describing this Arabic story.\n"
        "Focus on early Islamic / Arabian historical visuals ONLY:\n"
        "- desert landscapes, sand dunes, golden hour, sunset, sunrise\n"
        "- ancient Arabic architecture, old mosque, minaret, arches\n"
        "- camels, Arabian horses, oasis, palm trees\n"
        "- mountains, valleys, caves, rocky desert\n"
        "- starry night, crescent moon, dramatic sky, clouds\n"
        "- old manuscripts, calligraphy, candlelight\n"
        "- tents, traditional clothing, keffiyeh, thobe\n"
        "- swords, shields, horses galloping, dust\n"
        "AVOID: women, modern buildings, cities, cars, technology, people closeups.\n"
        "Each keyword: 2-4 English words, nature/historical focused.\n"
        f"Story:\n{story}\n"
        "7 comma-separated keywords:"
    )
    keywords_raw = _groq_complete(scene_prompt)
    keywords = [k.strip() for k in keywords_raw.replace("\n", ",").split(",") if k.strip()]
    time.sleep(1)

    cine_prompt = (
        "For this Arabic historical/Islamic story, suggest 6 cinematic atmospheric search modifiers.\n"
        "Examples: golden hour desert haze, volumetric light rays mosque, dust storm dramatic,\n"
        "ancient stone texture sunset, starry desert night, candle flame flicker\n"
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
