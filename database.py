import aiosqlite
import secrets
from datetime import datetime
from typing import Optional, Dict, Any, List
from config import DB_PATH, ADMIN_IDS, add_admin_id

async def init_db():
    """Ma'lumotlar bazasini ishga tushirish va jadvallarni yaratish"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Tabriklar jadvali
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

        # Foydalanuvchilar jadvali (Admin panel va statistika uchun)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_blocked INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # is_admin ustuni mavjud bo'lmasa, qo'shish
        try:
            await db.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
        except Exception:
            pass

        # Wishes jadvalidagi mavjud telegram_user_id larni avtomatik users ga kiritish
        await db.execute("""
            INSERT OR IGNORE INTO users (telegram_id, first_name)
            SELECT DISTINCT telegram_user_id, 'Foydalanuvchi'
            FROM wishes
            WHERE telegram_user_id IS NOT NULL
        """)

        # Default adminlarni bazada ham admin deb belgilash
        for admin_id in ADMIN_IDS:
            await db.execute("UPDATE users SET is_admin = 1 WHERE telegram_id = ?", (admin_id,))

        await db.commit()

def generate_slug() -> str:
    """Xavfsiz va qisqa unikal identifikator yaratish"""
    return secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8]

async def add_or_update_user(
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None
):
    """Foydalanuvchini bazaga kiritish yoki faollik vaqtini yangilash"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (telegram_id, username, first_name, last_name, is_blocked, last_active_at)
            VALUES (?, ?, ?, ?, 0, CURRENT_TIMESTAMP)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = COALESCE(excluded.username, users.username),
                first_name = COALESCE(excluded.first_name, users.first_name),
                last_name = COALESCE(excluded.last_name, users.last_name),
                is_blocked = 0,
                last_active_at = CURRENT_TIMESTAMP
        """, (telegram_id, username, first_name, last_name))
        await db.commit()

async def mark_user_blocked(telegram_id: int):
    """Botni bloklagan foydalanuvchini belgilash"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_blocked = 1 WHERE telegram_id = ?", (telegram_id,))
        await db.commit()

async def make_user_admin(telegram_id: int):
    """Foydalanuvchiga adminlik huquqini berish"""
    add_admin_id(telegram_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_admin = 1 WHERE telegram_id = ?", (telegram_id,))
        await db.commit()

async def check_user_is_admin(telegram_id: int) -> bool:
    """Foydalanuvchi admin ekanligini bazadan tekshirish"""
    if telegram_id in ADMIN_IDS:
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT is_admin FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        if row and row[0] == 1:
            add_admin_id(telegram_id)
            return True
    return False

async def get_stats_summary() -> Dict[str, Any]:
    """Admin panel uchun to'liq statistika ma'lumotlarini olish"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Jami foydalanuvchilar
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0]

        # Faol foydalanuvchilar
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 0")
        active_users = (await cursor.fetchone())[0]

        # Botni bloklaganlar
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 1")
        blocked_users = (await cursor.fetchone())[0]

        # Bugun qo'shilganlar (yoki faol bo'lganlar)
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE date(created_at) = date('now')")
        today_new_users = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE date(last_active_at) = date('now')")
        today_active_users = (await cursor.fetchone())[0]

        # Jami tabriknomalar
        cursor = await db.execute("SELECT COUNT(*) FROM wishes")
        total_wishes = (await cursor.fetchone())[0]

        # Bugun yaratilgan tabriknomalar
        cursor = await db.execute("SELECT COUNT(*) FROM wishes WHERE date(created_at) = date('now')")
        today_wishes = (await cursor.fetchone())[0]

        # Jami ko'rishlar
        cursor = await db.execute("SELECT COALESCE(SUM(views_count), 0) FROM wishes")
        total_views = (await cursor.fetchone())[0]

        return {
            "total_users": total_users,
            "active_users": active_users,
            "blocked_users": blocked_users,
            "today_new_users": today_new_users,
            "today_active_users": today_active_users,
            "total_wishes": total_wishes,
            "today_wishes": today_wishes,
            "total_views": total_views
        }

async def get_all_broadcast_users() -> List[int]:
    """Reklama / xabarnoma jo'natish uchun barcha faol foydalanuvchilar ID ro'yxati"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT telegram_id FROM users WHERE is_blocked = 0")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def get_recent_users(limit: int = 15) -> List[Dict[str, Any]]:
    """Eng oxirgi faol bo'lgan foydalanuvchilar ro'yxati"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT telegram_id, username, first_name, last_name, is_blocked, is_admin, created_at, last_active_at
            FROM users
            ORDER BY last_active_at DESC
            LIMIT ?
        """, (limit,))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def get_recent_wishes(limit: int = 15) -> List[Dict[str, Any]]:
    """Eng oxirgi yaratilgan tabriknomalar ro'yxati"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT slug, recipient_name, sender_name, views_count, theme, created_at
            FROM wishes
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

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
