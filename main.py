import asyncio
import logging
import os
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, HOST, PORT, BASE_URL
from database import init_db
from bot import register_bot_handlers
from web_server import create_web_app

# Logging sozlash
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("BirthdayWishApp")

async def start_web_server(bot_username: str):
    """Veb-serverni ishga tushirish (QR orqali ochiladigan tabrik sahifalari uchun)"""
    app = create_web_app(bot_username)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()
    logger.info(f"🌐 Veb-server ishga tushdi: http://localhost:{PORT}")
    logger.info(f"🔗 QR kodlar uchun asosiy havola: {BASE_URL}")
    return runner

async def keep_awake_task():
    """Server uyquga ketmasligi uchun har 8 daqiqada o'zini chaqirib turadi"""
    render_url = os.getenv("RENDER_EXTERNAL_URL", "") or os.getenv("BASE_URL", "")
    if not render_url or "localhost" in render_url or "127.0.0.1" in render_url:
        return
    logger.info(f"⏰ Keep-alive xizmati faollashdi: {render_url}")
    await asyncio.sleep(60)
    import aiohttp
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                target_url = f"{render_url.rstrip('/')}/health"
                async with session.get(target_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    logger.info(f"💓 Keep-alive ping status: {resp.status}")
        except Exception as e:
            logger.warning(f"Keep-alive ping xatosi: {e}")
        await asyncio.sleep(480) # Har 8 daqiqada bir marta

async def main():
    # 1. Ma'lumotlar bazasini initsializatsiya qilish
    await init_db()
    logger.info("📁 Ma'lumotlar bazasi tayyorlandi.")

    # 1.1 Keep-awake vazifasini ishga tushirish
    asyncio.create_task(keep_awake_task())

    # 2. Token mavjudligini tekshirish
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.warning("=" * 60)
        logger.warning("⚠️ DIQQAT: Telegram bot tokeni kiritilmagan!")
        logger.warning("Iltimos, .env fayliga @BotFather dan olingan BOT_TOKEN ni kiriting.")
        logger.warning(f"Biroq, veb-server ishga tushirilmoqda: http://localhost:{PORT}")
        logger.warning("=" * 60)
        
        # Veb-serverni barchasiz ham sinash uchun ishga tushiramiz
        runner = await start_web_server(bot_username="BirthdayBot")
        try:
            # Kutish rejimi
            while True:
                await asyncio.sleep(3600)
        finally:
            await runner.cleanup()
        return

    # 3. Bot va Dispatcherni yaratish
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # 4. Bot ma'lumotlarini olish (username)
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    logger.info(f"🤖 Telegram bot tayyor: @{bot_username}")

    # 5. Handlerlarni ulash
    register_bot_handlers(dp)

    # 6. Veb-serverni ishga tushirish
    runner = await start_web_server(bot_username=bot_username)

    # 7. Bot polling va veb-serverni parallel yurgizish
    try:
        logger.info("🚀 Tizim to'liq ishga tushdi! Bot xabarlarni qabul qilmoqda...")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Xatolik yuz berdi: {e}")
    finally:
        await runner.cleanup()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Dastur to'xtatildi.")
