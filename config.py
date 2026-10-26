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
# Render.com avtomatik tarzda RENDER_EXTERNAL_URL (masalan: https://my-bot.onrender.com) beradi
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
