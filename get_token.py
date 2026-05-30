import os, json, requests, base64, sys

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Read client_secrets.json if it exists locally
if not os.path.exists("client_secrets.json"):
    print("ضع ملف client_secrets.json في هذا المجلد أولاً")
    sys.exit(1)

with open("client_secrets.json") as f:
    cs = json.load(f)
    cid = cs["installed"]["client_id"]
    csecret = cs["installed"]["client_secret"]

print("=== TOKEN GENERATOR FOR YouTube SHORTS ===")
print()

redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import WebApplicationClient

client = WebApplicationClient(cid)
oauth = OAuth2Session(client=client, redirect_uri=redirect_uri, scope=SCOPES)

auth_url, state = oauth.authorization_url(
    "https://accounts.google.com/o/oauth2/auth",
    access_type="offline",
    prompt="consent",
)

print("1. افتح هذا الرابط في المتصفح:")
print(auth_url)
print()
print("2. سجل الدخول وافتح الكود")
print("3. الصق الكود هنا:")
code = input("CODE: ").strip()

token = oauth.fetch_token(
    "https://oauth2.googleapis.com/token",
    code=code,
    client_secret=csecret,
)

from google.oauth2.credentials import Credentials
creds = Credentials(
    token=token.get("access_token"),
    refresh_token=token.get("refresh_token"),
    token_uri="https://oauth2.googleapis.com/token",
    client_id=cid,
    client_secret=csecret,
    scopes=SCOPES,
)

token_json = creds.to_json()

with open("token.json", "w", encoding="utf-8") as f:
    f.write(token_json)

b64 = base64.b64encode(token_json.encode()).decode()

print()
print("انسخ الرمز التالي وأضفه كـ GitHub Secret باسم YT_TOKEN:")
print(b64)
