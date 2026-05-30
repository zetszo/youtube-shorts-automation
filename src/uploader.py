import json
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import YOUTUBE_CREDENTIALS_FILE, YOUTUBE_TOKEN_FILE

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

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

def upload_video(script_data: dict) -> str:
    video = script_data.get("video_file")
    if not video or not os.path.exists(video):
        raise FileNotFoundError(f"Video not found: {video}")

    lang = script_data["language"]
    topic = script_data.get("topic", "Islamic Story")

    if lang == "ar":
        title = topic if len(topic) <= 100 else topic[:97] + "..."
        desc = (
            "قصص إسلامية وعبر من التاريخ\n"
            "اشترك في القناة للمزيد 🕌\n\n"
            "#قصص_إسلامية #Shorts #عبر"
        )
        tags = ["قصص إسلامية", "Shorts", "عبر", "تاريخ إسلامي", "ديني"]
    else:
        title = topic if len(topic) <= 100 else topic[:97] + "..."
        desc = (
            "Inspiring Islamic stories\n"
            "Subscribe for more 🕌\n\n"
            "#Islamic #Shorts #History"
        )
        tags = ["Islamic", "Shorts", "History", "Stories", "Inspirational"]

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
    script_data["youtube_url"] = url
    script_data["youtube_id"] = vid
    return url
