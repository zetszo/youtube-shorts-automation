import json
import os
import random
import re
import requests
import time
from datetime import datetime
from config import GROQ_API_KEY, GROQ_MODEL, TOPICS_ARABIC

HISTORY_FILE = "output/history.json"
SCRIPTS_DIR = "output/scripts"
os.makedirs(SCRIPTS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)

# Default fallback keywords when Groq is rate-limited
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
            print(f"  \u23f3 \u0627\u0646\u062a\u0638\u0627\u0631 {_RATE_LIMIT_WAIT}\u062b \u0644\u0644\u062a\u0623\u0643\u064a\u062f")
            time.sleep(_RATE_LIMIT_WAIT)
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
        new_topic_prompt = (
            "\u0627\u0642\u062a\u0631\u062d \u0645\u0648\u0636\u0648\u0639\u0627\u064b \u062c\u062f\u064a\u062f\u0627\u064b \u0648\u0641\u0631\u064a\u062f\u0627\u064b \u0644\u0642\u0635\u0629 \u0625\u0633\u0644\u0627\u0645\u064a\u0629 \u0642\u0635\u064a\u0631\u0629 \u0644\u0645 \u064a\u0633\u062a\u062e\u062f\u0645 \u0645\u0646 \u0642\u0628\u0644.\n"
            "\u0627\u0643\u062a\u0628 \u0645\u0648\u0636\u0648\u0639\u0627\u064b \u0648\u0627\u062d\u062f\u0627\u064b \u0641\u0642\u0637 \u0645\u062e\u062a\u0644\u0641\u0627\u064b \u062a\u0645\u0627\u0645\u0627\u064b:\n"
            "\u0645\u062b\u0627\u0644: \u0642\u0635\u0629 \u0633\u064a\u062f\u0646\u0627 \u0625\u0633\u062d\u0627\u0642 \u0639\u0644\u064a\u0647 \u0627\u0644\u0633\u0644\u0627\u0645 \u0623\u0648 \u0642\u0635\u0629 \u0639\u0628\u062f \u0627\u0644\u0631\u062d\u0645\u0646 \u0628\u0646 \u0639\u0648\u0641 \u0631\u0636\u064a \u0627\u0644\u0644\u0647 \u0639\u0646\u0647"
        )
        try:
            new_topic = _groq_complete(new_topic_prompt)
            new_topic = new_topic.strip().strip('"').strip("'")
        except Exception:
            new_topic = "\u0642\u0635\u0629 \u0635\u062d\u0627\u0628\u064a \u062c\u0644\u064a\u0644 \u0645\u0646 \u0635\u062d\u0627\u0628\u0629 \u0627\u0644\u0631\u0633\u0648\u0644 \u0635\u0644\u0649 \u0627\u0644\u0644\u0647 \u0639\u0644\u064a\u0647 \u0648\u0633\u0644\u0645"
        idx = history["next_dynamic_id"]
        history["next_dynamic_id"] += 1
        topic = new_topic
        history.setdefault("custom_topics", {})[str(idx)] = topic
        print(f"  \ud83d\udd04 \u0642\u0635\u0629 #{idx} \u062c\u062f\u064a\u062f\u0629")

    history["used_ids"].append(idx)
    history["total"] += 1
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    # ONE Groq call for the story + embedded keywords
    story_prompt = (
        f"\u0627\u0643\u062a\u0628 \u0642\u0635\u0629 \u0642\u0635\u064a\u0631\u0629 \u0628\u0627\u0644\u0639\u0631\u0628\u064a\u0629 \u0627\u0644\u0641\u0635\u062d\u0649 \u0639\u0646: {topic}\n\n"
        "\u0627\u0644\u0645\u062a\u0637\u0644\u0628\u0627\u062a:\n"
        "- \u0627\u0644\u0645\u062f\u0629: 90-120 \u062b\u0627\u0646\u064a\u0629 (250-350 \u0643\u0644\u0645\u0629)\n"
        "- \u0627\u0644\u062a\u0632\u0645 \u0628\u0627\u0644\u0631\u0648\u0627\u064a\u0629 \u0627\u0644\u0635\u062d\u064a\u062d\u0629\n"
        "- \u0623\u0633\u0644\u0648\u0628 \u0633\u0631\u062f\u064a \u062c\u0630\u0627\u0628 \u0648\u0641\u064a\u0647 \u0639\u0628\u0631\u0629\n\n"
        "\u0628\u0639\u062f \u0627\u0644\u0642\u0635\u0629\u060c \u0627\u0643\u062a\u0628 \u0633\u0637\u0631\u064b\u0627 \u0639\u0644\u0649 \u0647\u0630\u0647 \u0627\u0644\u0635\u064a\u063a\u0629:\n"
        "##KEYWORDS## desert sand dunes, ancient mosque, camel sunset\n"
        "(\u0627\u0633\u062a\u0628\u062f\u0644 \u0627\u0644\u0643\u0644\u0645\u0627\u062a \u0628\u0645\u0627 \u064a\u0646\u0627\u0633\u0628 \u0627\u0644\u0642\u0635\u0629\u060c 8-10 \u0643\u0644\u0645\u0627\u062a \u0625\u0646\u062c\u0644\u064a\u0632\u064a\u0629 \u0644\u0628\u062d\u062b \u0627\u0644\u0641\u064a\u062f\u064a\u0648)\n\n"
        "\u0627\u0643\u062a\u0628 \u0627\u0644\u0642\u0635\u0629 \u062b\u0645 \u0627\u0644\u0643\u0644\u0645\u0627\u062a \u0627\u0644\u0645\u0641\u062a\u0627\u062d\u064a\u0629."
    )

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
    elif not story_raw:
        story = ""
    else:
        story = story_raw

    if not keywords:
        keywords = random.sample(FALLBACK_KEYWORDS, min(8, len(FALLBACK_KEYWORDS)))
        print("  \u2139\ufe0f \u0627\u0633\u062a\u062e\u062f\u0627\u0645 \u0643\u0644\u0645\u0627\u062a \u0627\u0641\u062a\u0631\u0627\u0636\u064a\u0629")

    if not cine_keywords:
        cine_keywords = FALLBACK_CINE[:]

    if not story:
        print("  \u26a0\ufe0f Groq \u0644\u0645 \u064a\u0633\u062a\u062c\u0628\u060c \u0627\u0633\u062a\u062e\u062f\u0627\u0645 \u0642\u0635\u0629 \u0627\u0641\u062a\u0631\u0627\u0636\u064a\u0629")
        story = (
            f"\u0642\u0635\u0629 {topic} \u0647\u064a \u0625\u062d\u062f\u0649 \u0623\u0639\u0638\u0645 \u0627\u0644\u0642\u0635\u0635 \u0641\u064a \u0627\u0644\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0625\u0633\u0644\u0627\u0645\u064a. "
            "\u0643\u0627\u0646 \u0631\u062c\u0644\u0627\u064b \u0639\u0638\u064a\u0645\u0627\u064b \u064a\u062a\u0645\u064a\u0632 \u0628\u0627\u0644\u0625\u064a\u0645\u0627\u0646 \u0648\u0627\u0644\u0635\u062f\u0642 \u0648\u0627\u0644\u0625\u062e\u0644\u0627\u0635. "
            "\u064a\u0631\u0648\u0649 \u0623\u0646\u0647 \u0641\u064a \u064a\u0648\u0645 \u0645\u0646 \u0627\u0644\u0623\u064a\u0627\u0645 \u0643\u0627\u0646 \u0641\u064a \u0635\u062d\u0631\u0627\u0621 \u0627\u0644\u062c\u0632\u064a\u0631\u0629 \u0627\u0644\u0639\u0631\u0628\u064a\u0629\u060c "
            "\u062a\u062d\u062a \u0633\u0645\u0627\u0621 \u0635\u0627\u0641\u064a\u0629 \u0648\u0646\u062c\u0648\u0645 \u0644\u0627\u0645\u0639\u0629\u060c "
            "\u064a\u062a\u0623\u0645\u0644 \u0641\u064a \u062e\u0644\u0642 \u0627\u0644\u0644\u0647. "
            "\u0643\u0627\u0646\u062a \u0627\u0644\u0631\u064a\u0627\u062d \u062a\u0647\u0628 \u0639\u0644\u0649 \u0627\u0644\u0631\u0645\u0627\u0644 \u0648\u0627\u0644\u0646\u062e\u064a\u0644 \u062a\u062a\u0630\u0628\u0630\u0628 \u0641\u064a \u0627\u0644\u0647\u0648\u0627\u0621. "
            "\u0641\u064a \u062a\u0644\u0643 \u0627\u0644\u0644\u064a\u0644\u0629\u060c \u062d\u062f\u062b \u0623\u0645\u0631 \u0639\u0638\u064a\u0645 \u063a\u064a\u0631 \u0645\u062c\u0631\u0627\u0647. "
            "\u0641\u0647\u0648 \u064a\u0639\u0644\u0645\u0646\u0627 \u0623\u0646 \u0627\u0644\u0635\u0628\u0631 \u0648\u0627\u0644\u0625\u064a\u0645\u0627\u0646 \u0647\u0645\u0627 \u0645\u0641\u062a\u0627\u062d \u0627\u0644\u0641\u0631\u062c\u060c "
            "\u0648\u0623\u0646 \u0627\u0644\u0644\u0647 \u0645\u0639 \u0627\u0644\u0635\u0627\u0628\u0631\u064a\u0646. "
            "\u0647\u0630\u0647 \u0642\u0635\u0629 \u062a\u062f\u0648\u064a \u0641\u064a \u0627\u0644\u0642\u0644\u0648\u0628 \u0648\u062a\u0638\u0644 \u0641\u064a \u0627\u0644\u0623\u0630\u0647\u0627\u0646."
        )

    story = _clean_text(story)
    print(f"  \u0642\u0635\u0629: {len(story.split())} \u0643\u0644\u0645\u0629 | {len(keywords)} keywords")

    data = {
        "topic_id": idx,
        "topic": topic,
        "story": story,
        "keywords": keywords[:10],
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
