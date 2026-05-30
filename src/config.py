import os

# Groq API (مجاني - Llama 3 70B)
# سجل في https://console.groq.com/ واحصل على API Key
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "YOUR_GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

# Pexels (مجاني - https://www.pexels.com/api/)
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "YOUR_PEXELS_API_KEY")

# YouTube API
YOUTUBE_CREDENTIALS_FILE = "client_secrets.json"
YOUTUBE_TOKEN_FILE = "token.pickle"

# إعدادات الفيديو
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_DURATION = 50

# إعدادات الصوت
TTS_VOICE_ARABIC = "ar-SA-ZariyahNeural"
TTS_VOICE_ENGLISH = "en-US-JennyNeural"

# عدد الفيديوهات اليومية
VIDEOS_PER_DAY = 3

# مواضيع القصص
TOPICS_ARABIC = [
    "قصة نبي من الأنبياء",
    "موقف من حياة الصحابة",
    "معجزة من القرآن",
    "حدث تاريخي في الإسلام",
    "قصة صحابي جليل",
    "قصة من الجنة والنار",
    "موقف من حياة النبي صلى الله عليه وسلم",
]

TOPICS_ENGLISH = [
    "Story of a Prophet",
    "Story of a Companion",
    "Islamic historical event",
    "Miracle in the Quran",
    "Inspiring Islamic story",
    "Lesson from Islamic history",
]
