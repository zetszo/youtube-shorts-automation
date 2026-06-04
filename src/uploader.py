import json
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
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
            creds.refresh(Request())
        else:
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

    topic = script_data.get("topic", "قصة إسلامية")
    title = topic if len(topic) <= 90 else topic[:87] + "..."

    desc_parts = [
        topic,
        "",
        "سبحان الله 💫 قصة مؤثرة من تاريخ الإسلام",
        "لا تنسى الاشتراك في القناة وتفعيل الجرس 🔔",
        "شارك القصة لتعم الفائدة 🤲",
        "",
        "---",
        "".join(HASHTAGS),
        "",
        "📌 تابعنا للمزيد من القصص الإسلامية والعبر",
    ]
    desc = "\n".join(desc_parts)
    tags = _build_tags(topic)

    # Upload thumbnail if generated
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
    media = MediaFileUpload(video, chunksize=-1, resumable=True)
    response = youtube.videos().insert(part="snippet,status", body=body, media_body=media).execute()

    vid = response["id"]
    url = f"https://youtu.be/{vid}"

    # Upload thumbnail separately
    if thumb_path and os.path.exists(thumb_path):
        try:
            youtube.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumb_path)).execute()
        except Exception:
            pass

    script_data["youtube_url"] = url
    script_data["youtube_id"] = vid
    return url
