import html
from pathlib import Path
from aiohttp import web
from config import STATIC_DIR, TEMPLATES_DIR, BASE_URL
from database import get_wish

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
        # Chiroyli 404 sahifasi
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
                a {
                    display: inline-block;
                    background: #f59e0b;
                    color: #0f172a;
                    padding: 12px 24px;
                    border-radius: 99px;
                    text-decoration: none;
                    font-weight: bold;
                }
            </style>
        </head>
        <body>
            <div class="box">
                <h1>🔍</h1>
                <h2>Tabriknoma topilmadi</h2>
                <p>Ushbu QR kod yoki havola mavjud emas yoki noto'g'ri kiritilgan.</p>
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
    
    # Telegram bot username (dynamic context dan olinadi)
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
        </style>
    </head>
    <body>
        <div class="card">
            <span class="icon">🎂</span>
            <h1>Tug'ilgan Kun Tabrik Xizmati</h1>
            <p>Ushbu server QR kodli interaktiv tug'ilgan kun tabriknomalarini taqdim etadi.</p>
            {"<a href='https://t.me/" + bot_username + "' class='btn'><span>🤖</span> Telegram Botni Ochish</a>" if bot_username else "<span style='color:#94a3b8'>Bot faol ishlamoqda ✨</span>"}
        </div>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type="text/html")

async def handle_health(request: web.Request) -> web.Response:
    """Server holatini tekshirish va keep-alive (UptimeRobot / cron-job) uchun endpoint"""
    return web.Response(text="OK", content_type="text/plain")

def create_web_app(bot_username: str = "") -> web.Application:
    """Aiohttp veb ilovasini yaratish va sozlash"""
    app = web.Application()
    app["bot_username"] = bot_username
    
    # Marshrutlar
    app.router.add_get("/", handle_index)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/w/{slug}", handle_wish_page)
    
    # Statik fayllar (rasmlar, QR kodlar, scriptlar)
    app.router.add_static("/static/", path=str(STATIC_DIR), name="static")
    
    return app

