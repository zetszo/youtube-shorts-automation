import os

# Groq API (مجاني - Llama 3 70B)
# سجل في https://console.groq.com/ واحصل على API Key
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "YOUR_GROQ_API_KEY")
GROQ_MODEL_AR = "allam-2-7b"
GROQ_MODEL_EN = "llama-3.3-70b-versatile"

# Pexels (مجاني - https://www.pexels.com/api/)
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "YOUR_PEXELS_API_KEY")

# YouTube API
YOUTUBE_CREDENTIALS_FILE = "client_secrets.json"
YOUTUBE_TOKEN_FILE = "token.json"

# إعدادات الفيديو
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_DURATION = 50

# إعدادات الصوت
TTS_VOICE_ARABIC = "ar-EG-ShakirNeural"
TTS_VOICE_ENGLISH = "en-US-JennyNeural"
TTS_RATE = "+0%"

# عدد الفيديوهات اليومية
VIDEOS_PER_DAY = 3

# مواضيع القصص - أنبياء فقط
TOPICS_ARABIC = [
    "قصة سيدنا آدم عليه السلام وابنه هابيل",
    "قصة سيدنا نوح عليه السلام والطوفان",
    "قصة سيدنا إبراهيم عليه السلام والنار",
    "قصة سيدنا موسى عليه السلام وفرعون",
    "قصة سيدنا يوسف عليه السلام وإخوته",
    "قصة سيدنا سليمان عليه السلام والنمل",
    "قصة سيدنا محمد صلى الله عليه وسلم والإسراء",
    "قصة سيدنا عيسى عليه السلام والمائدة",
    "قصة سيدنا يونس عليه السلام والحوت",
    "قصة سيدنا أيوب عليه السلام والصبر",
]

TOPICS_ENGLISH = [
    "Story of Prophet Adam and his son Abel",
    "Story of Prophet Noah and the flood",
    "Story of Prophet Abraham and the fire",
    "Story of Prophet Moses and Pharaoh",
    "Story of Prophet Joseph and his brothers",
    "Story of Prophet Solomon and the ants",
    "Story of Prophet Muhammad and the night journey",
    "Story of Prophet Jesus and the table spread",
    "Story of Prophet Jonah and the whale",
    "Story of Prophet Job and patience",
]
