#!/usr/bin/env python3
"""Generate a fresh YouTube API token.json for headless upload.
Run this locally ONCE. It will open a browser for OAuth consent.
The output token.json can be base64-encoded and stored as GitHub secret YT_TOKEN.
"""
import base64
import json
import os
import sys

# Windows cp1252 workaround: reconfigure stdout to utf-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRETS = "client_secrets.json"
TOKEN_FILE = "token.json"

def main():
    if not os.path.exists(CLIENT_SECRETS):
        print("[ERROR] الملف client_secrets.json غير موجود.")
        print("       حمّله من Google Cloud Console > APIs & Services > Credentials > OAuth 2.0 Client IDs")
        print("       (نوع Desktop application)")
        sys.exit(1)

    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, encoding="utf-8") as f:
                creds = Credentials.from_authorized_user_info(json.load(f))
        except Exception as e:
            print(f"[WARN] token.json تالف، سيتم إنشاء جديد: {e}")
            creds = None

    if creds and creds.valid:
        print("[OK] Token صالح حالياً. لا حاجة للتجديد.")
    else:
        if creds and creds.expired and creds.refresh_token:
            print("[..] تجديد token المنتهي...")
            try:
                creds.refresh(Request())
                print("[OK] تم التجديد!")
            except Exception as e:
                print(f"[WARN] فشل تجديد token: {e}")
                print("[..] سيتم فتح المتصفح لتسجيل الدخول من جديد...")
                creds = None

        if not creds or not creds.valid:
            print("[..] فتح المتصفح لتسجيل الدخول إلى Google...")
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS, SCOPES,
                redirect_uri="http://localhost:8080/"
            )
            creds = flow.run_local_server(
                port=8080,
                open_browser=True,
                access_type='offline',
                prompt='consent'
            )
            print("[OK] تم تسجيل الدخول!")

        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        print("[OK] حفظ token.json")

    # Verify token has refresh_token
    with open(TOKEN_FILE, encoding="utf-8") as f:
        tok = json.load(f)
    if "refresh_token" in tok and tok["refresh_token"]:
        print("[OK] Token يحتوي على refresh_token.")
    else:
        print("[WARN] لا يوجد refresh_token! سيحتاج token إلى تجديد يدوي كل ساعة.")
        print("       احذف token.json وشغّل السكريبت مجدداً.")

    # Print base64 for GitHub secrets
    with open(TOKEN_FILE, encoding="utf-8") as f:
        b64 = base64.b64encode(f.read().encode()).decode()
    print(f"\n=== base64 لـ YT_TOKEN (انسخ هذا إلى GitHub Secrets) ===\n{b64}\n")

    with open(CLIENT_SECRETS, encoding="utf-8") as f:
        cs_b64 = base64.b64encode(f.read().encode()).decode()
    print(f"=== base64 لـ YT_CLIENT_SECRETS ===\n{cs_b64}\n")

if __name__ == "__main__":
    main()
