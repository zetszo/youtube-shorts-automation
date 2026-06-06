#!/usr/bin/env python3
"""Generate a fresh YouTube API token.json for headless upload.
Run this locally ONCE. It will open a browser for OAuth consent.
The output token.json can be base64-encoded and stored as GitHub secret YT_TOKEN.
"""
import base64
import json
import os
import sys
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRETS = "client_secrets.json"
TOKEN_FILE = "token.json"

def main():
    if not os.path.exists(CLIENT_SECRETS):
        print(f"❌ الملف {CLIENT_SECRETS} غير موجود.")
        print("   حمّله من Google Cloud Console > APIs & Services > Credentials > OAuth 2.0 Client IDs")
        print("   (نوع Desktop application)")
        sys.exit(1)

    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, encoding="utf-8") as f:
            creds = Credentials.from_authorized_user_info(json.load(f))

    if creds and creds.valid:
        print("✅ Token صالح حالياً. لا حاجة للتجديد.")
    else:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 تجديد token المنتهي...")
            creds.refresh(Request())
            print("✅ تم التجديد!")
        else:
            print("🔑 فتح المتصفح لتسجيل الدخول إلى Google...")
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS, SCOPES,
                redirect_uri="http://localhost:8080/"
            )
            creds = flow.run_local_server(port=8080, open_browser=True)
            print("✅ تم تسجيل الدخول!")

        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        print(f"💾 حفظ token.json")

    # Print base64 for GitHub secret
    with open(TOKEN_FILE, encoding="utf-8") as f:
        b64 = base64.b64encode(f.read().encode()).decode()
    print(f"\n📋 base64 لـ YT_TOKEN (انسخ هذا إلى GitHub Secrets):\n\n{b64}\n")

    # Also print client_secrets base64
    with open(CLIENT_SECRETS, encoding="utf-8") as f:
        cs_b64 = base64.b64encode(f.read().encode()).decode()
    print(f"📋 base64 لـ YT_CLIENT_SECRETS:\n\n{cs_b64}\n")

    # Verify token has refresh_token
    with open(TOKEN_FILE, encoding="utf-8") as f:
        tok = json.load(f)
    if "refresh_token" in tok and tok["refresh_token"]:
        print("✅ Token يحتوي على refresh_token.")
    else:
        print("⚠️  لا يوجد refresh_token! سيحتاج token إلى تجديد يدوي كل ساعة.")
        print("   احذف token.json وشغّل السكريبت مجدداً.")

if __name__ == "__main__":
    main()
