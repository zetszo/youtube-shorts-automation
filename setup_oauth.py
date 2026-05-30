"""
تشغيل هذه السكريبت على جهازك المحلي لتوليد token.pickle
ثم ارفع client_secrets.json و token.pickle كـ base64 إلى GitHub Secrets
"""
import base64
import pickle
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CREDENTIALS_FILE = "client_secrets.json"
TOKEN_FILE = "token.pickle"

def generate_token():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"✗ ضع ملف {CREDENTIALS_FILE} أولاً في هذا المجلد")
        return

    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
        print(f"✓ تم حفظ {TOKEN_FILE}")

    # إنشاء base64 للنشر على GitHub
    with open(TOKEN_FILE, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    print(f"\n=== TOKEN.PICKLE (base64) - انسخ هذا إلى GitHub Secret YT_TOKEN ===")
    print(b64[:100] + "...")

    with open(CREDENTIALS_FILE, "rb") as f:
        b64c = base64.b64encode(f.read()).decode()
    print(f"\n=== CLIENT_SECRETS.JSON (base64) - انسخ هذا إلى GitHub Secret YT_CLIENT_SECRETS ===")
    print(b64c[:100] + "...")

if __name__ == "__main__":
    generate_token()
