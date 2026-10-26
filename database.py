import aiosqlite
import secrets
from datetime import datetime
from typing import Optional, Dict, Any
from config import DB_PATH

async def init_db():
    """Ma'lumotlar bazasini ishga tushirish va jadvallarni yaratish"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS wishes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                recipient_name TEXT NOT NULL,
                wish_text TEXT NOT NULL,
                photo_filename TEXT,
                sender_name TEXT,
                theme TEXT DEFAULT 'gold',
                music_enabled INTEGER DEFAULT 1,
                views_count INTEGER DEFAULT 0,
                telegram_user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

def generate_slug() -> str:
    """Xavfsiz va qisqa unikal identifikator yaratish"""
    return secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8]

async def create_wish(
    recipient_name: str,
    wish_text: str,
    photo_filename: Optional[str] = None,
    sender_name: Optional[str] = None,
    theme: str = "gold",
    telegram_user_id: Optional[int] = None
) -> str:
    """Yangi tabriknoma saqlash va uning slug kodini qaytarish"""
    slug = generate_slug()
    async with aiosqlite.connect(DB_PATH) as db:
        # Check uniqueness just in case
        while True:
            cursor = await db.execute("SELECT id FROM wishes WHERE slug = ?", (slug,))
            row = await cursor.fetchone()
            if not row:
                break
            slug = generate_slug()

        await db.execute("""
            INSERT INTO wishes (
                slug, recipient_name, wish_text, photo_filename,
                sender_name, theme, telegram_user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            slug, recipient_name.strip(), wish_text.strip(),
            photo_filename, sender_name.strip() if sender_name else "Yaqiningiz",
            theme, telegram_user_id
        ))
        await db.commit()
    return slug

async def get_wish(slug: str) -> Optional[Dict[str, Any]]:
    """Slug bo'yicha tabrikni olish va ko'rishlar sonini 1 taga oshirish"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM wishes WHERE slug = ?", (slug,))
        row = await cursor.fetchone()
        if not row:
            return None
        
        # Ko'rishlar sonini oshirish
        await db.execute("UPDATE wishes SET views_count = views_count + 1 WHERE slug = ?", (slug,))
        await db.commit()
        return dict(row)

async def get_user_wishes(telegram_user_id: int):
    """Foydalanuvchi yaratgan barcha tabriknomalar ro'yxati"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM wishes WHERE telegram_user_id = ? ORDER BY id DESC LIMIT 20",
            (telegram_user_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
