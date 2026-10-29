import html
import asyncio
import logging
from pathlib import Path
from aiohttp import web
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from config import STATIC_DIR, TEMPLATES_DIR, BASE_URL
from database import (
    get_wish,
    get_stats_summary,
    get_all_broadcast_users,
    get_recent_users,
    get_recent_wishes,
    mark_user_blocked
)

logger = logging.getLogger("BirthdayWebServer")

def render_template(template_name: str, context: dict) -> str:
    """Oddiy va xavfsiz shablon renderlash mexanizmi"""
    template_path = TEMPLATES_DIR / template_name
    if not template_path.exists():
        return "Template not found"
    
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    for key, value in context.items():
        placeholder = f"{{{{{key}}}}}"
        content = content.replace(placeholder, str(value))
    
    return content

async def handle_wish_page(request: web.Request) -> web.Response:
    """Tabriknoma sahifasi (/w/{slug})"""
    slug = request.match_info.get("slug", "")
    wish = await get_wish(slug)
    
    if not wish:
        error_html = """
        <!DOCTYPE html>
        <html lang="uz">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Tabriknoma topilmadi</title>
            <style>
                body {
                    background: #0f172a;
                    color: #f8fafc;
                    font-family: system-ui, -apple-system, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                    margin: 0;
                    text-align: center;
                    padding: 20px;
                }
                .box {
                    background: rgba(30, 41, 59, 0.7);
                    padding: 40px 30px;
                    border-radius: 24px;
                    border: 1px solid rgba(255,255,255,0.1);
                    max-width: 400px;
                }
                h1 { font-size: 48px; margin: 0 0 10px; }
                p { color: #94a3b8; font-size: 16px; margin-bottom: 24px; }
            </style>
        </head>
        <body>
            <div class="box">
                <h1>🔍</h1>
                <h2>Tabriknoma topilmadi</h2>
                <p>Ushbu QR kod yoki havola mavjud emas yoki muddati o'tgan.</p>
            </div>
        </body>
        </html>
        """
        return web.Response(text=error_html, content_type="text/html", status=404)
    
    # Rasm manzili
    photo_filename = wish.get("photo_filename")
    if photo_filename:
        photo_url = f"/static/uploads/{photo_filename}"
    else:
        photo_url = "/static/default_avatar.png"
    
    bot_username = request.app.get("bot_username", "TugilganKunTabrikBot")
    
    context = {
        "recipient_name": html.escape(wish.get("recipient_name", "Qadrdonim")),
        "wish_text": html.escape(wish.get("wish_text", "Tug'ilgan kuningiz muborak bo'lsin!")),
        "photo_url": photo_url,
        "sender_name": html.escape(wish.get("sender_name", "Yaqiningiz")),
        "theme": wish.get("theme", "gold"),
        "bot_username": bot_username,
        "views_count": wish.get("views_count", 1)
    }
    
    rendered = render_template("greeting.html", context)
    return web.Response(text=rendered, content_type="text/html")

async def handle_index(request: web.Request) -> web.Response:
    """Bosh sahifa (/): Tizim holati va botga yo'naltirish"""
    bot_username = request.app.get("bot_username", "")
    html_content = f"""
    <!DOCTYPE html>
    <html lang="uz">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Tug'ilgan Kun Tabrik Boti</title>
        <style>
            body {{
                background: radial-gradient(circle at center, #1e1b4b 0%, #0f172a 100%);
                color: #f8fafc;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                margin: 0;
                padding: 20px;
                text-align: center;
            }}
            .card {{
                background: rgba(30, 41, 59, 0.8);
                backdrop-filter: blur(16px);
                border: 1px solid rgba(245, 158, 11, 0.3);
                border-radius: 28px;
                padding: 40px 32px;
                max-width: 480px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.5);
            }}
            .icon {{ font-size: 64px; margin-bottom: 16px; display: inline-block; }}
            h1 {{ font-size: 26px; color: #fbbf24; margin-bottom: 12px; }}
            p {{ color: #cbd5e1; font-size: 16px; line-height: 1.6; margin-bottom: 28px; }}
            .btn {{
                background: linear-gradient(135deg, #f59e0b, #d97706);
                color: #0f172a;
                font-weight: bold;
                padding: 14px 28px;
                border-radius: 99px;
                text-decoration: none;
                display: inline-flex;
                align-items: center;
                gap: 8px;
                transition: transform 0.2s;
            }}
            .btn:hover {{ transform: scale(1.04); }}
            .admin-link {{
                display: block;
                margin-top: 20px;
                color: #94a3b8;
                font-size: 14px;
                text-decoration: none;
            }}
            .admin-link:hover {{ color: #f59e0b; text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="card">
            <span class="icon">🎂</span>
            <h1>Tug'ilgan Kun Tabrik Xizmati</h1>
            <p>Ushbu server QR kodli interaktiv tug'ilgan kun tabriknomalarini taqdim etadi.</p>
            {"<a href='https://t.me/" + bot_username + "' class='btn'><span>🤖</span> Telegram Botni Ochish</a>" if bot_username else "<span style='color:#94a3b8'>Bot faol ishlamoqda ✨</span>"}
            <a href="/admin" class="admin-link">👑 Boshqaruv Markazi (Admin Panel)</a>
        </div>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type="text/html")

async def handle_health(request: web.Request) -> web.Response:
    """Server holatini tekshirish va keep-alive endpoint"""
    return web.Response(text="OK", content_type="text/plain")

async def handle_admin(request: web.Request) -> web.Response:
    """Web Admin Dashboard sahifasi (/admin)"""
    bot_username = request.app.get("bot_username", "TugilganKunTabrikBot")
    stats = await get_stats_summary()

    context = {
        "bot_username": bot_username,
        "total_users": stats["total_users"],
        "active_users": stats["active_users"],
        "blocked_users": stats["blocked_users"],
        "today_new_users": stats["today_new_users"],
        "today_active_users": stats["today_active_users"],
        "total_wishes": stats["total_wishes"],
        "today_wishes": stats["today_wishes"],
        "total_views": stats["total_views"],
        "base_url": BASE_URL
    }

    rendered = render_template("admin.html", context)
    return web.Response(text=rendered, content_type="text/html")

async def handle_api_stats(request: web.Request) -> web.Response:
    """Admin dashboard uchun JSON statistika API (/api/admin/stats)"""
    stats = await get_stats_summary()
    recent_users = await get_recent_users(limit=25)
    recent_wishes = await get_recent_wishes(limit=25)

    return web.json_response({
        "status": "ok",
        "stats": stats,
        "recent_users": recent_users,
        "recent_wishes": recent_wishes
    })

async def handle_api_broadcast(request: web.Request) -> web.Response:
    """Web Admin orqali barcha foydalanuvchilarga xabarnoma/reklama yuborish (/api/admin/broadcast)"""
    bot = request.app.get("bot")
    if not bot:
        return web.json_response({"status": "error", "message": "Bot xizmati faol emas"}, status=503)

    try:
        data = await request.json()
        message_text = data.get("message", "").strip()
    except Exception:
        return web.json_response({"status": "error", "message": "Noto'g'ri so'rov formati"}, status=400)

    if not message_text:
        return web.json_response({"status": "error", "message": "Xabar matni kiritilmagan"}, status=400)

    users = await get_all_broadcast_users()
    sent_count = 0
    blocked_count = 0
    failed_count = 0
    start_time = asyncio.get_event_loop().time()

    for user_id in users:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=message_text,
                parse_mode="HTML"
            )
            sent_count += 1
        except TelegramForbiddenError:
            blocked_count += 1
            await mark_user_blocked(user_id)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=message_text,
                    parse_mode="HTML"
                )
                sent_count += 1
            except Exception:
                failed_count += 1
        except Exception as e:
            logger.warning(f"Web broadcast error for {user_id}: {e}")
            failed_count += 1

        await asyncio.sleep(0.04)

    duration = asyncio.get_event_loop().time() - start_time

    return web.json_response({
        "status": "ok",
        "sent": sent_count,
        "blocked": blocked_count,
        "failed": failed_count,
        "total": len(users),
        "elapsed": round(duration, 1)
    })

def create_web_app(bot_username: str = "", bot = None) -> web.Application:
    """Aiohttp veb ilovasini yaratish va sozlash"""
    app = web.Application()
    app["bot_username"] = bot_username
    app["bot"] = bot
    
    # Marshrutlar
    app.router.add_get("/", handle_index)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/admin", handle_admin)
    app.router.add_get("/api/admin/stats", handle_api_stats)
    app.router.add_post("/api/admin/broadcast", handle_api_broadcast)
    app.router.add_get("/w/{slug}", handle_wish_page)
    
    # Statik fayllar (rasmlar, QR kodlar, scriptlar)
    app.router.add_static("/static/", path=str(STATIC_DIR), name="static")
    
    return app
