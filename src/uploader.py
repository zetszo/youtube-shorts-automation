import json
import os
import sys
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from config import YOUTUBE_CREDENTIALS_FILE, YOUTUBE_TOKEN_FILE

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

HASHTAGS = [
    "#قصص_إسلامية", "#اسلام", "#دين", "#اللهم",
    "#انبياء", "#صحابة", "#السيرة_النبوية", "# shorts",
    "#قران", "#ذكر", "#adhan", "#islamic_video",
    "#خواطر_دينية", "#عبر_وعظات", "#إيمان", "#هداية",
]

CATEGORY_TAGS = {
    "prophet": ["انبياء", "قصص الانبياء", "سيدنا", "عليه السلام", "نبي"],
    "companion": ["صحابة", "الصحابة", "رضي الله عنه", "الخلفاء الراشدين"],
    "story": ["قصة", "عبرة", "موعظة", "حكمة", "قصة اسلامية"],
}

VIRAL_TAGS = [
    "قصص إسلامية", "Islamic stories", "quran", "allah",
    "islamic shorts", "viral islam", "سبحان الله",
    "islamic video", "muslim", "faith", "deen",
    "قصص الانبياء", "الصحابة", "السيرة النبوية",
    "islamic reminder", "motivation islam",
]

def _get_service():
    creds = None
    if os.path.exists(YOUTUBE_TOKEN_FILE):
        with open(YOUTUBE_TOKEN_FILE, encoding="utf-8") as f:
            creds = Credentials.from_authorized_user_info(json.load(f))

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(YOUTUBE_TOKEN_FILE, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
                print("  ↻ تم تجديد token اليوتيوب", file=sys.stderr)
            except Exception as e:
                print(f"  ↻ فشل تجديد token: {e}", file=sys.stderr)
                creds = None  # force re-auth flow below (will raise clear error on headless)
        if not creds or not creds.valid:
            if not os.path.exists(YOUTUBE_CREDENTIALS_FILE):
                raise RuntimeError(
                    "❌ client_secrets.json غير موجود.\n"
                    "   شغّل python auth_youtube.py محلياً لإنشاء token.json\n"
                    "   وانسخ base64 إلى GitHub Secrets YT_TOKEN و YT_CLIENT_SECRETS"
                )
            if os.environ.get("GITHUB_ACTIONS") == "true":
                raise RuntimeError(
                    "❌ token اليوتيوب منتهي ولا يمكن تجديده في GitHub Actions.\n"
                    "   1. شغّل محلياً: python auth_youtube.py\n"
                    "   2. حدّث YT_TOKEN في GitHub Secrets بالـ base64 الجديد\n"
                    "   3. شغّل الـ pipeline مجدداً"
                )
            flow = InstalledAppFlow.from_client_secrets_file(YOUTUBE_CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0, open_browser=False)
            with open(YOUTUBE_TOKEN_FILE, "w", encoding="utf-8") as f:
                f.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)

def _build_tags(topic):
    tags = set(VIRAL_TAGS)
    topic_lower = topic.lower()
    for key, words in CATEGORY_TAGS.items():
        for w in words:
            if w in topic_lower:
                tags.update(words)
    return list(tags)[:20]

def upload_video(script_data: dict) -> str:
    video = script_data.get("video_file")
    if not video or not os.path.exists(video):
        raise FileNotFoundError(f"Video not found: {video}")

    topic = script_data.get("topic", "\u0642\u0635\u0629 \u0625\u0633\u0644\u0627\u0645\u064a\u0629")
    ctr_title = script_data.get("ctr_title", "")
    title = ctr_title if ctr_title and len(ctr_title) <= 90 else (topic if len(topic) <= 90 else topic[:87] + "...")

    desc_parts = [
        title,
        "",
        "\u0642\u0646\u0627\u0629 \u0625\u0631\u062b \u0627\u0644\u0625\u064a\u0645\u0627\u0646 \u2014 \u0642\u0635\u0635 \u0625\u0633\u0644\u0627\u0645\u064a\u0629 \u0645\u0648\u062b\u0648\u0642\u0629 \u062a\u0623\u062e\u0630 \u0628\u0642\u0644\u0628\u0643 \u0641\u064a \u0631\u062d\u0644\u0629 \u0627\u0644\u0625\u064a\u0645\u0627\u0646.",
        "\u0645\u0627 \u0631\u0623\u064a\u0643 \u0641\u064a \u0647\u0630\u0647 \u0627\u0644\u0642\u0635\u0629\u061f \u0643\u062a\u0628 \u062a\u0639\u0644\u064a\u0642\u0643 \u0648\u0644\u0646 \u0646\u0646\u0633\u0627\u0647 \ud83d\udc47",
        "\u0644\u0627 \u062a\u0646\u0633\u0649 \u0627\u0644\u0627\u0634\u062a\u0631\u0627\u0643 \u0641\u064a \u0627\u0644\u0642\u0646\u0627\u0629 \u0648\u062a\u0641\u0639\u064a\u0644 \u0627\u0644\u062c\u0631\u0633 \ud83d\udd14",
        "",
        "\u2014\u2014\u2014",
        "#\u0625\u0631\u062b_\u0627\u0644\u0625\u064a\u0645\u0627\u0646 #\u0642\u0635\u0635_\u0625\u0633\u0644\u0627\u0645\u064a\u0629 #\u0627\u0633\u0644\u0627\u0645 #\u0627\u0646\u0628\u064a\u0627\u0621 #\u0635\u062d\u0627\u0628\u0629 #\u0627\u0644\u0644\u0647\u0645 #\u0642\u0635\u0635_\u0627\u0644\u0627\u0646\u0628\u064a\u0627\u0621 #\u0627\u0644\u0633\u064a\u0631\u0629_\u0627\u0644\u0646\u0628\u0648\u064a\u0629 #shorts",
        "",
        "\u062a\u0627\u0628\u0639\u0646\u0627 \u0644\u0644\u0645\u0632\u064a\u062f \u0645\u0646 \u0627\u0644\u0642\u0635\u0635 \u0627\u0644\u0625\u0633\u0644\u0627\u0645\u064a\u0629 \u0648\u0627\u0644\u0639\u0628\u0631",
    ]
    desc = "\n".join(desc_parts)
    tags = _build_tags(topic)

    thumb_path = script_data.get("thumbnail_file")
    body = {
        "snippet": {
            "title": title,
            "description": desc,
            "tags": tags,
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    youtube = _get_service()
    print(f"  ↻ جاري رفع الفيديو إلى YouTube...", file=sys.stderr)
    media = MediaFileUpload(video, chunksize=-1, resumable=True)

    # Retry API call with backoff
    last_err = None
    for attempt in range(1, 4):
        try:
            response = youtube.videos().insert(
                part="snippet,status", body=body, media_body=media
            ).execute()
            vid = response["id"]
            url = f"https://youtu.be/{vid}"
            print(f"  ✓ رفع: {url}", file=sys.stderr)
            break
        except HttpError as e:
            last_err = e
            if e.resp.status in [429, 500, 502, 503, 504]:
                wait = 5 * attempt
                print(f"  ⏳ خطأ {e.resp.status}، انتظار {wait}ث...", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
    else:
        raise last_err or RuntimeError("رفع فاشل")

    if thumb_path and os.path.exists(thumb_path):
        try:
            youtube.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumb_path)).execute()
            print(f"  ✓ thumbnail مرفوعة", file=sys.stderr)
        except Exception:
            pass

    script_data["youtube_url"] = url
    script_data["youtube_id"] = vid
    return url
