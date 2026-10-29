# Birthday Wish Bot Configuration
import os
import socket
from pathlib import Path
from dotenv import load_dotenv

# Base Directory
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables
load_dotenv(BASE_DIR / ".env")

# Telegram Bot Token (default token if not provided in environment)
BOT_TOKEN = os.getenv("BOT_TOKEN", "") or "8725456314:AAE8_hnW4Znhs-l16Rt08SXE1QKg7RXQp_U"

# Admin Telegram IDs (Vergul bilan ajratilgan, masalan: 6363224227,12345678)
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "6363224227,5782328489,7741739989,2024080317,123456")
ADMIN_IDS = set()
for item in ADMIN_IDS_RAW.split(","):
    item = item.strip()
    if item.isdigit():
        ADMIN_IDS.add(int(item))

# Always ensure known owner/tester IDs are present
KNOWN_ADMINS = {6363224227, 5782328489, 7741739989, 2024080317, 123456}
ADMIN_IDS.update(KNOWN_ADMINS)

# Web Admin va Bot orqali parolli adminlik
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

def is_admin(user_id: int) -> bool:
    """Foydalanuvchi admin ekanligini tekshirish"""
    return user_id in ADMIN_IDS

def add_admin_id(user_id: int):
    """Yangi admin ID qo'shish"""
    ADMIN_IDS.add(user_id)

# Web Server Settings
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

def get_local_ip() -> str:
    """Kompyuterning lokal Wi-Fi yoki tarmoq IP manzilini aniqlash"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

LOCAL_IP = get_local_ip()

# Base URL for the QR code links
render_url = os.getenv("RENDER_EXTERNAL_URL", "")
env_base_url = os.getenv("BASE_URL", "")

if render_url:
    BASE_URL = render_url.rstrip("/")
elif env_base_url and "localhost" not in env_base_url and "127.0.0.1" not in env_base_url:
    BASE_URL = env_base_url.rstrip("/")
else:
    BASE_URL = f"http://{LOCAL_IP}:{PORT}"

# Directories
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = STATIC_DIR / "uploads"
QRCODES_DIR = STATIC_DIR / "qrcodes"
TEMPLATES_DIR = BASE_DIR / "templates"
DB_PATH = BASE_DIR / "birthday_wishes.db"

# Create directories if they don't exist
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
QRCODES_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
