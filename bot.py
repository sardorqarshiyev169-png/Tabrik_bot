import os
import uuid
import logging
import asyncio
from pathlib import Path
from aiogram import Bot, Dispatcher, F, types, BaseMiddleware
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    FSInputFile,
    WebAppInfo
)
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramAPIError

from config import BOT_TOKEN, BASE_URL, UPLOADS_DIR, QRCODES_DIR, STATIC_DIR, ADMIN_IDS, ADMIN_PASSWORD, is_admin
from database import (
    create_wish,
    get_wish,
    get_user_wishes,
    add_or_update_user,
    mark_user_blocked,
    get_stats_summary,
    get_all_broadcast_users,
    get_recent_users,
    get_recent_wishes,
    check_user_is_admin,
    make_user_admin
)
from qr_generator import generate_birthday_qr

logger = logging.getLogger("BirthdayBot")

# FSM holatlari (Tabrik yaratish)
class WishForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_wish = State()
    waiting_for_photo = State()
    waiting_for_sender = State()
    waiting_for_theme = State()

# FSM holatlari (Admin xabarnoma yuborish)
class BroadcastForm(StatesGroup):
    waiting_for_message = State()
    waiting_for_confirm = State()

# FSM holatlari (Admin parol kiritish)
class AdminAuthForm(StatesGroup):
    waiting_for_password = State()

# Foydalanuvchilar faolligini avtomatik bazaga yozib borish middleware'i
class UserTrackingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user and not user.is_bot:
            try:
                await add_or_update_user(
                    telegram_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name
                )
            except Exception as e:
                logger.debug(f"User tracking error: {e}")
        return await handler(event, data)

# Tayyor chiroyli tabrik shablonlari
TEMPLATES_LIST = {
    "tpl_friend": (
        "Qadrdon do'stim! Tug'ilgan kuning muborak bo'lsin! 🥳\n\n"
        "Senga sihat-salomatlik, bitmas-tuganmas baxt va eng ulug' maqsadlaringga erishishingni tilayman! "
        "Har doim yuzingdan kulgu, dilingdan quvonch arimasin. Doimo yoningda sadoqatli do'stlar bo'lsin! 🎉"
    ),
    "tpl_parents": (
        "Mehribon va aziz insonim! 💖\n\n"
        "Tug'ilgan kuningiz bilan chin qalbimdan tabriklayman! "
        "Sizga uzoq umr, mustahkam sog'lik, xonadoningizga tinchlik-totuvlik va fayz-u baraka tilayman. "
        "Baxtimizga doimo sog'-omon bo'ling! 🌹"
    ),
    "tpl_love": (
        "Yuragimdagi eng qadrli insonim! 💕\n\n"
        "Tug'ilgan kuningiz muborak bo'lsin! Hayotingiz doimo quyosh kabi porloq, "
        "baxtli va quvonchli onlarga to'la bo'lsin. Har bir kuningiz yangi quvonch va mehr olib kelsin! ✨🎂"
    ),
    "tpl_general": (
        "Tug'ilgan kuningiz bilan samimiy muborakbod etaman! 🌟\n\n"
        "Yangi yoshingiz yangi zafarlar, ulkan muvaffaqiyatlar va mustahkam sog'lik olib kelsin. "
        "Barcha orzu-istaklaringiz ro'yobga chiqsin! 🎈🎁"
    )
}

def is_valid_telegram_button_url(url: str) -> bool:
    """Telegram inline tugmalarida faqat haqiqiy public HTTP/HTTPS ruxsat etiladi"""
    if not url:
        return False
    lower = url.lower()
    if "localhost" in lower or "127.0.0.1" in lower:
        return False
    if lower.startswith("http://192.168.") or lower.startswith("http://10."):
        return False
    return lower.startswith("https://") or lower.startswith("http://")

def get_main_reply_keyboard():
    """Doimiy pastki menyu tugmalari"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎉 Yangi tabrik yaratish"), KeyboardButton(text="📜 Mening tabriklarim")],
            [KeyboardButton(text="📊 Bot statistikasi"), KeyboardButton(text="👑 Admin Panel")],
            [KeyboardButton(text="ℹ️ Qanday ishlaydi?")]
        ],
        resize_keyboard=True
    )

def get_main_keyboard(is_admin_user: bool = False):
    """Xabar ostidagi inline tugmalar"""
    buttons = [
        [InlineKeyboardButton(text="🎉 Yangi tabrik yaratish", callback_data="start_create_wish")],
        [InlineKeyboardButton(text="📜 Mening tabriklarim", callback_data="my_wishes_list")],
        [
            InlineKeyboardButton(text="📊 Bot statistikasi", callback_data="admin_stats"),
            InlineKeyboardButton(text="👑 Admin Panel", callback_data="admin_panel")
        ],
        [InlineKeyboardButton(text="ℹ️ Qanday ishlaydi?", callback_data="how_it_works")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Foydalanuvchilar statistikasi", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Xabarnoma / Reklama yuborish", callback_data="admin_broadcast_start")],
        [InlineKeyboardButton(text="👥 Oxirgi foydalanuvchilar", callback_data="admin_recent_users")],
        [InlineKeyboardButton(text="🎁 Oxirgi tabriknomalar", callback_data="admin_recent_wishes")],
        [InlineKeyboardButton(text="🌐 Web Admin havolasi", callback_data="admin_web_info")],
        [InlineKeyboardButton(text="⬅️ Bosh menyuga qaytish", callback_data="back_to_menu")]
    ])

def get_admin_stats_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin_stats"),
            InlineKeyboardButton(text="📢 Reklama yuborish", callback_data="admin_broadcast_start")
        ],
        [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_recent_users")],
        [InlineKeyboardButton(text="⬅️ Admin menyu", callback_data="admin_panel")]
    ])

def get_broadcast_confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Ha, barchaga yuborilsin!", callback_data="confirm_broadcast_send")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_broadcast")]
    ])

def get_templates_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ 1. Do'st / Qadrdon uchun", callback_data="tpl_friend")],
        [InlineKeyboardButton(text="🌹 2. Ota-ona / Aziz inson uchun", callback_data="tpl_parents")],
        [InlineKeyboardButton(text="💖 3. Sevimli inson uchun", callback_data="tpl_love")],
        [InlineKeyboardButton(text="🌟 4. Umumiy samimiy tabrik", callback_data="tpl_general")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")]
    ])

def get_skip_photo_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏩ O'tkazib yuborish (Rasmsiz)", callback_data="skip_photo")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")]
    ])

def get_skip_sender_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏩ O'tkazib yuborish (Anonim)", callback_data="skip_sender")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")]
    ])

def get_theme_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌟 Hashamatli Oltin (Gold Luxury)", callback_data="theme_gold")],
        [InlineKeyboardButton(text="🎆 Yorqin Neon (Cyber Party)", callback_data="theme_neon")],
        [InlineKeyboardButton(text="🌹 Romantik Atirgul (Romantic Rose)", callback_data="theme_romantic")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")]
    ])

def register_bot_handlers(dp: Dispatcher):
    """Barcha bot handlerlarini ro'yxatdan o'tkazish"""

    # Foydalanuvchilarni avtomatik ro'yxatga olish middleware'ini ulash
    tracking_middleware = UserTrackingMiddleware()
    dp.message.outer_middleware(tracking_middleware)
    dp.callback_query.outer_middleware(tracking_middleware)

    # ==================== ADMIN PANEL HANDLERS ====================

    # /admin komandasi yoki "👑 Admin Panel" matni
    @dp.message(Command("admin"))
    @dp.message(F.text == "👑 Admin Panel")
    async def cmd_admin(message: types.Message, state: FSMContext):
        await state.clear()
        user_id = message.from_user.id
        
        # Parol bilan /admin admin123 kiritilgan bo'lsa
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) > 1 and parts[1].strip() == ADMIN_PASSWORD:
            await make_user_admin(user_id)
            await message.answer("✅ <b>Tabriklaymiz! Siz admin sifatida tasdiqlandingiz!</b>", parse_mode="HTML")

        is_adm = await check_user_is_admin(user_id)
        if not is_adm:
            text = (
                "👑 <b>Admin Boshqaruv Paneliga kirish</b>\n\n"
                f"Sizning Telegram ID: <code>{user_id}</code>\n\n"
                "Agar siz bot egasi bo'lsangiz, admin parolini kiritib darhol admin bo'lishingiz mumkin:\n"
                "👉 Buyruq: <code>/admin admin123</code>\n"
                "Yoki pastdagi tugmani bosing 👇"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔐 Parol orqali kirish", callback_data="admin_auth_start")],
                [InlineKeyboardButton(text="⬅️ Bosh menyuga qaytish", callback_data="back_to_menu")]
            ])
            await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
            return

        first_name = message.from_user.first_name or "Admin"
        text = (
            f"👑 <b>Boshqaruv Paneli (Admin Panel)</b>\n\n"
            f"Assalomu alaykum, <b>{first_name}</b>!\n"
            "Bot boshqaruv markaziga xush kelibsiz.\n\n"
            "Bu yerda bot statistikasi (foydalanuvchilar soni)ni ko'rishingiz va barcha a'zolarga xabarnoma/reklama yuborishingiz mumkin.\n\n"
            "Kerakli bo'limni tanlang 👇"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=get_admin_keyboard())

    # Parol orqali admin bo'lish
    @dp.callback_query(F.data == "admin_auth_start")
    async def cb_admin_auth_start(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(AdminAuthForm.waiting_for_password)
        text = (
            "🔐 <b>Admin parolini kiriting:</b>\n\n"
            "<i>(Standart parol: <code>admin123</code>)</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")]
        ])
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        await callback.answer()

    # Parolni tekshirish
    @dp.message(AdminAuthForm.waiting_for_password, F.text)
    async def process_admin_password(message: types.Message, state: FSMContext):
        password = message.text.strip()
        if password == ADMIN_PASSWORD:
            await make_user_admin(message.from_user.id)
            await state.clear()
            await message.answer(
                "✅ <b>Tabriklaymiz! Siz muvaffaqiyatli admin bo'ldingiz!</b>\n\n"
                "Admin panelga xush kelibsiz 👇",
                parse_mode="HTML",
                reply_markup=get_admin_keyboard()
            )
        else:
            await message.answer("❌ Noto'g'ri parol. Qayta urinib ko'ring yoki /cancel bosing:")

    # Admin bosh menyusi (Callback)
    @dp.callback_query(F.data == "admin_panel")
    async def cb_admin_panel(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        user_id = callback.from_user.id
        is_adm = await check_user_is_admin(user_id)
        if not is_adm:
            text = (
                "👑 <b>Admin Boshqaruv Paneliga kirish</b>\n\n"
                f"Sizning Telegram ID: <code>{user_id}</code>\n\n"
                "Admin bo'lish uchun parolni kiriting:"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔐 Parol orqali kirish", callback_data="admin_auth_start")],
                [InlineKeyboardButton(text="⬅️ Bosh menyuga qaytish", callback_data="back_to_menu")]
            ])
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            await callback.answer()
            return

        text = (
            "👑 <b>Boshqaruv Paneli (Admin Panel)</b>\n\n"
            "Kerakli amaliyotni tanlang 👇"
        )
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_keyboard())
        await callback.answer()

    # 📊 Statistika tugmasi (Necha kishi foydalanayotgani) — Callback va Message
    @dp.message(F.text == "📊 Bot statistikasi")
    @dp.callback_query(F.data == "admin_stats")
    async def show_stats(event: types.Message | types.CallbackQuery):
        stats = await get_stats_summary()

        text = (
            "📊 <b>BOT FOYDALANUVCHILARI VA STATISTIKA</b>\n\n"
            f"👥 <b>Jami foydalanuvchilar:</b> <code>{stats['total_users']}</code> ta\n"
            f"🟢 <b>Faol a'zolar:</b> <code>{stats['active_users']}</code> ta\n"
            f"✨ <b>Bugun qo'shilgan yangilar:</b> <code>{stats['today_new_users']}</code> ta\n"
            f"⚡️ <b>Bugun faol bo'lganlar:</b> <code>{stats['today_active_users']}</code> ta\n"
            f"🚫 <b>Botni to'xtatganlar (blok):</b> <code>{stats['blocked_users']}</code> ta\n\n"
            f"🎁 <b>Jami yaratilgan tabriklar:</b> <code>{stats['total_wishes']}</code> ta\n"
            f"🎉 <b>Bugun yaratilgan tabriklar:</b> <code>{stats['today_wishes']}</code> ta\n"
            f"👁 <b>Tabriknomalar jami ko'rilishi:</b> <code>{stats['total_views']}</code> marta\n\n"
            "<i>⚡️ Ma'lumotlar real vaqt rejimida yangilandi.</i>"
        )
        if isinstance(event, types.CallbackQuery):
            await event.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_stats_keyboard())
            await event.answer("Statistika yangilandi!")
        else:
            await event.answer(text, parse_mode="HTML", reply_markup=get_admin_stats_keyboard())

    # 👥 Oxirgi foydalanuvchilar ro'yxati
    @dp.callback_query(F.data == "admin_recent_users")
    async def cb_admin_recent_users(callback: types.CallbackQuery):
        users = await get_recent_users(limit=15)
        if not users:
            text = "👥 Hozircha foydalanuvchilar ro'yxati bo'sh."
        else:
            text = f"👥 <b>So'nggi faol foydalanuvchilar ({len(users)} ta):</b>\n\n"
            for idx, u in enumerate(users, 1):
                name = u.get("first_name") or "Noma'lum"
                uname = f"@{u['username']}" if u.get("username") else "usernamesiz"
                uid = u["telegram_id"]
                status = "🚫 Bloklagan" if u.get("is_blocked") else "🟢 Faol"
                active_at = str(u.get("last_active_at", ""))[:16]
                text += f"{idx}. <b>{name}</b> ({uname})\n   🆔 <code>{uid}</code> | {status}\n   ⏱ {active_at}\n\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin_recent_users")],
            [InlineKeyboardButton(text="⬅️ Admin panelga qaytish", callback_data="admin_panel")]
        ])
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        await callback.answer()

    # 🎁 Oxirgi tabriknomalar ro'yxati
    @dp.callback_query(F.data == "admin_recent_wishes")
    async def cb_admin_recent_wishes(callback: types.CallbackQuery):
        wishes = await get_recent_wishes(limit=10)
        if not wishes:
            text = "🎁 Hozircha yaratilgan tabriknomalar mavjud emas."
        else:
            text = f"🎁 <b>So'nggi yaratilgan tabriknomalar ({len(wishes)} ta):</b>\n\n"
            for idx, w in enumerate(wishes, 1):
                rec = w["recipient_name"]
                snd = w.get("sender_name") or "Yaqiningiz"
                slug = w["slug"]
                views = w.get("views_count", 0)
                url = f"{BASE_URL}/w/{slug}"
                text += f"{idx}. <b>{rec}</b> (Kimdan: {snd})\n   👁 {views} marta | 🔗 {url}\n\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin_recent_wishes")],
            [InlineKeyboardButton(text="⬅️ Admin panelga qaytish", callback_data="admin_panel")]
        ])
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)
        await callback.answer()

    # 🌐 Web Admin Dashboard havolasi
    @dp.callback_query(F.data == "admin_web_info")
    async def cb_admin_web_info(callback: types.CallbackQuery):
        admin_web_url = f"{BASE_URL}/admin"
        text = (
            "🌐 <b>Veb Boshqaruv Paneli (Web Admin Dashboard)</b>\n\n"
            "Bot statistikasi, foydalanuvchilar va tabriklarni kompyuter yoki telefon brauzeridan ham boshqarishingiz mumkin!\n\n"
            f"🔗 <b>Admin havolasi:</b>\n{admin_web_url}\n\n"
            "🔐 <b>Kirish paroli:</b> <code>admin123</code>\n\n"
            "<i>Veb panelda qulay grafiklar, jadvallar va to'g'ridan-to'g'ri saytdan turib reklama yuborish imkoniyati mavjud.</i>"
        )
        buttons = []
        if is_valid_telegram_button_url(admin_web_url):
            buttons.append([InlineKeyboardButton(text="🌐 Saytda ochish", url=admin_web_url)])
        buttons.append([InlineKeyboardButton(text="⬅️ Admin panelga qaytish", callback_data="admin_panel")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)
        await callback.answer()

    # 📢 Xabarnoma / Reklama yuborishni boshlash
    @dp.callback_query(F.data == "admin_broadcast_start")
    async def cb_broadcast_start(callback: types.CallbackQuery, state: FSMContext):
        is_adm = await check_user_is_admin(callback.from_user.id)
        if not is_adm:
            await callback.answer("⛔️ Siz admin emassiz!", show_alert=True)
            return

        stats = await get_stats_summary()
        active_count = stats["active_users"]

        await state.set_state(BroadcastForm.waiting_for_message)
        text = (
            "📢 <b>Foydalanuvchilarga xabarnoma / reklama yuborish</b>\n\n"
            f"Hozirda botda faol foydalanuvchilar soni: <b>{active_count} ta</b>\n\n"
            "Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring.\n\n"
            "<b>Quyidagilarni yuborishingiz mumkin:</b>\n"
            "• 📝 Oddiy matnli xabar\n"
            "• 🖼 Rasm va uning ostidagi izoh (caption)\n"
            "• 🎬 Video, GIF yoki Hujjat\n"
            "• 🔄 Boshqa kanallardan uzatilgan (Forward) post\n\n"
            "<i>Xabarni yuborganingizdan so'ng, u avval sizga ko'rib chiqish (preview) uchun ko'rsatiladi va tasdiqlashingiz so'raladi.</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_broadcast")]
        ])
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        await callback.answer()

    # Reklama xabari qabul qilinganda (Preview tayyorlash)
    @dp.message(BroadcastForm.waiting_for_message)
    async def process_broadcast_message(message: types.Message, state: FSMContext, bot: Bot):
        is_adm = await check_user_is_admin(message.from_user.id)
        if not is_adm:
            return

        await state.update_data(
            broadcast_chat_id=message.chat.id,
            broadcast_message_id=message.message_id
        )

        stats = await get_stats_summary()
        active_count = stats["active_users"]

        # Preview ko'rsatish
        await message.answer("👁 <b>Siz yuborgan xabar ko'rinishi (Preview):</b>", parse_mode="HTML")
        await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )

        confirm_text = (
            f"Yuqoridagi xabarni barcha faol <b>{active_count} ta</b> bot foydalanuvchilariga yuborishni tasdiqlaysizmi?"
        )
        await message.answer(confirm_text, parse_mode="HTML", reply_markup=get_broadcast_confirm_keyboard())
        await state.set_state(BroadcastForm.waiting_for_confirm)

    # Reklamani tasdiqlab barchaga yuborish
    @dp.callback_query(BroadcastForm.waiting_for_confirm, F.data == "confirm_broadcast_send")
    async def cb_broadcast_confirm_send(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        is_adm = await check_user_is_admin(callback.from_user.id)
        if not is_adm:
            await callback.answer("⛔️ Siz admin emassiz!", show_alert=True)
            return

        data = await state.get_data()
        from_chat_id = data.get("broadcast_chat_id")
        message_id = data.get("broadcast_message_id")
        await state.clear()

        if not from_chat_id or not message_id:
            await callback.message.edit_text(
                "⚠️ Xatolik: Xabar ma'lumotlari topilmadi yoki eskirgan.",
                reply_markup=get_admin_keyboard()
            )
            return

        users = await get_all_broadcast_users()
        total_targets = len(users)

        status_msg = await callback.message.edit_text(
            f"⏳ <b>Xabarnoma yuborilmoqda...</b>\n\nJami: {total_targets} ta foydalanuvchi.\nIltimos, kuting...",
            parse_mode="HTML"
        )

        success_count = 0
        blocked_count = 0
        failed_count = 0
        start_time = asyncio.get_event_loop().time()

        for user_id in users:
            try:
                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=from_chat_id,
                    message_id=message_id
                )
                success_count += 1
            except TelegramForbiddenError:
                blocked_count += 1
                await mark_user_blocked(user_id)
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
                try:
                    await bot.copy_message(
                        chat_id=user_id,
                        from_chat_id=from_chat_id,
                        message_id=message_id
                    )
                    success_count += 1
                except Exception:
                    failed_count += 1
            except Exception as e:
                logger.warning(f"Broadcast error for user {user_id}: {e}")
                failed_count += 1

            await asyncio.sleep(0.04)

        duration = asyncio.get_event_loop().time() - start_time

        result_text = (
            "📢 <b>XABARNOMA YUBORISH YAKUNLANDI!</b>\n\n"
            "📊 <b>Natijalar:</b>\n"
            f"• 👥 Jami foydalanuvchilar: <b>{total_targets} ta</b>\n"
            f"• ✅ Muvaffaqiyatli yetib bordi: <b>{success_count} ta</b>\n"
            f"• 🚫 Botni bloklaganlar: <b>{blocked_count} ta</b>\n"
            f"• ⚠️ Xatolik tufayli yetib bormadi: <b>{failed_count} ta</b>\n"
            f"• ⏱ Ketgan vaqt: <b>{duration:.1f} soniya</b>\n\n"
            "<i>Bloklagan foydalanuvchilar kelgusida keraksiz urinish bo'lmasligi uchun belgilab qo'yildi.</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Yangi statistikani ko'rish", callback_data="admin_stats")],
            [InlineKeyboardButton(text="👑 Admin panel", callback_data="admin_panel")]
        ])
        await status_msg.edit_text(result_text, parse_mode="HTML", reply_markup=keyboard)
        await callback.answer("Xabarnoma muvaffaqiyatli yuborildi!")

    # Reklamani bekor qilish
    @dp.callback_query(F.data == "cancel_broadcast")
    async def cb_broadcast_cancel(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        text = "❌ <b>Xabarnoma yuborish bekor qilindi.</b>"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👑 Admin panelga qaytish", callback_data="admin_panel")]
        ])
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        await callback.answer("Bekor qilindi")

    # ==================== ASOSIY BOT HANDLERS ====================

    # /start komandasi
    @dp.message(CommandStart())
    async def cmd_start(message: types.Message, state: FSMContext):
        await state.clear()
        first_name = message.from_user.first_name or "Do'st"
        is_adm = await check_user_is_admin(message.from_user.id)

        text = (
            f"Salom, <b>{first_name}</b>! 👋🎂\n\n"
            "Men <b>Tug'ilgan kun tabriknoma boti</b>man!\n"
            "Men bilan yaqinlaringiz uchun <b>sehrli, musiqali va interaktiv</b> tabriknoma yaratishingiz va uni <b>chiroyli QR kod</b> ko'rinishida sovg'a qilishingiz mumkin!\n\n"
            "🎁 <b>Bu qanday ishlaydi?</b>\n"
            "1. Ism, tabrik matni va rasm kiritasiz.\n"
            "2. Bot maxsus veb-sahifa va sovg'abop QR kod yasaydi.\n"
            "3. QR kodni sovg'aga yopishtirasiz yoki do'stingizga yuborasiz!\n"
            "4. Telefon kamerasi bilan ochganda — musiqa, konfetti va tort shamini puflash animatsiyasi ochiladi! ✨\n\n"
            "Boshlash uchun pastdagi tugmani bosing 👇"
        )
        # Ham reply keyboard, ham inline keyboard chiqariladi!
        await message.answer(
            "Boshqaruv menyusi faollashtirildi 👇",
            reply_markup=get_main_reply_keyboard()
        )
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_main_keyboard(is_admin_user=is_adm)
        )

    # /help komandasi
    @dp.message(Command("help"))
    async def cmd_help(message: types.Message):
        help_text = (
            "📖 <b>Botdan foydalanish qo'llanmasi:</b>\n\n"
            "1️⃣ <b>/start</b> — Bosh menyuni ochish\n"
            "2️⃣ <b>/new</b> — Yangi tabriknoma yaratish\n"
            "3️⃣ <b>/mywishes</b> — Siz yaratgan barcha tabriklar va statistika\n"
            "4️⃣ <b>/admin</b> — 👑 Admin Panel (Statistika & Reklama)\n"
            "5️⃣ <b>/cancel</b> — Jarayonni bekor qilish\n\n"
            "💡 <i>QR kodni qayerga qo'yish mumkin?</i>\n"
            "• Sovg'a qutisiga yopishtirish\n"
            "• Gullar dastasiga ilib qo'yish\n"
            "• Konvert yoki tabriknoma qog'oziga chop etish\n"
            "• Telegram yoki Instagramda rasm sifatida yuborish!"
        )
        await message.answer(help_text, parse_mode="HTML")

    # /cancel komandasi
    @dp.message(Command("cancel"))
    async def cmd_cancel(message: types.Message, state: FSMContext):
        current_state = await state.get_state()
        if current_state is None:
            await message.answer("Hech qanday faol jarayon yo'q.", reply_markup=get_main_reply_keyboard())
            return
        await state.clear()
        await message.answer("❌ Jarayon bekor qilindi.", reply_markup=get_main_reply_keyboard())

    # Callback: Bekor qilish
    @dp.callback_query(F.data == "cancel_fsm")
    async def cb_cancel(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await callback.message.edit_text("❌ Jarayon bekor qilindi.", reply_markup=get_main_keyboard())
        await callback.answer()

    # Callback: Qanday ishlaydi?
    @dp.message(F.text == "ℹ️ Qanday ishlaydi?")
    @dp.callback_query(F.data == "how_it_works")
    async def cb_how_it_works(event: types.Message | types.CallbackQuery):
        text = (
            "ℹ️ <b>Sehrli tabriknoma haqida:</b>\n\n"
            "Bu oddiy tabrik emas! QR kod orqali ochiladigan sahifada:\n"
            "• 🎁 Sovg'a qutisini ochish introsi\n"
            "• 🎊 Haqiqiy konfetti va bayramona sharlar parvozi\n"
            "• 🎂 <b>Interaktiv tort va sham:</b> Tug'ilgan kun egasi ekranni bosib shamni puflaydi va qarsaklar chalinadi!\n"
            "• 🎵 «Happy Birthday» musiqasi yangraydi\n"
            "• 📸 Egasining rasmi va sizning samimiy tilaklaringiz chiroyli dizaynda chiqadi!\n\n"
            "Sinab ko'rishga tayyormisiz? 🚀"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎉 Hozir yaratish", callback_data="start_create_wish")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_menu")]
        ])
        if isinstance(event, types.CallbackQuery):
            await event.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            await event.answer()
        else:
            await event.answer(text, parse_mode="HTML", reply_markup=keyboard)

    # Callback: Bosh menyuga qaytish
    @dp.callback_query(F.data == "back_to_menu")
    async def cb_back_to_menu(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        is_adm = await check_user_is_admin(callback.from_user.id)
        await callback.message.edit_text(
            "Asosiy menyudasiz. Kerakli bo'limni tanlang:",
            reply_markup=get_main_keyboard(is_admin_user=is_adm)
        )
        await callback.answer()

    # /new yoki "start_create_wish" yoki Reply button "🎉 Yangi tabrik yaratish"
    @dp.message(Command("new"))
    @dp.message(F.text == "🎉 Yangi tabrik yaratish")
    @dp.callback_query(F.data == "start_create_wish")
    async def start_wish_flow(event: types.Message | types.CallbackQuery, state: FSMContext):
        await state.set_state(WishForm.waiting_for_name)
        text = (
            "1️⃣ <b>1-qadam: Tug'ilgan kun egasining ismi</b>\n\n"
            "Tabriklamoqchi bo'lgan insoningizning ismini yozib yuboring:\n"
            "<i>(Masalan: Jasur, Madinaxon, Onajonim, Dadam, Azizbek...)</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")]
        ])
        if isinstance(event, types.CallbackQuery):
            await event.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            await event.answer()
        else:
            await event.answer(text, parse_mode="HTML", reply_markup=keyboard)

    # 1-Qadam: Ismni qabul qilish
    @dp.message(WishForm.waiting_for_name, F.text)
    async def process_name(message: types.Message, state: FSMContext):
        name = message.text.strip()
        if len(name) > 50:
            await message.answer("⚠️ Ism juda uzun. Iltimos, 50 ta belgidan oshmasin:")
            return
        
        await state.update_data(recipient_name=name)
        await state.set_state(WishForm.waiting_for_wish)

        text = (
            f"Ajoyib! <b>{name}</b> uchun tabrik tayyorlaymiz. 🎂\n\n"
            "2️⃣ <b>2-qadam: Tabrik so'zlari va tilaklar</b>\n\n"
            "O'zingizning samimiy tilaklaringizni yozib yuboring ✍️\n"
            "Yoki pastdagi tayyor chiroyli shablonlardan birini tanlang:"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=get_templates_keyboard())

    # Shablon tanlanganda
    @dp.callback_query(WishForm.waiting_for_wish, F.data.startswith("tpl_"))
    async def process_template_selection(callback: types.CallbackQuery, state: FSMContext):
        tpl_key = callback.data
        wish_text = TEMPLATES_LIST.get(tpl_key, "Tug'ilgan kuningiz muborak bo'lsin!")
        await state.update_data(wish_text=wish_text)
        await ask_for_photo(callback.message, state, is_edit=True)
        await callback.answer("Shablon tanlandi!")

    # Qo'lda yozilgan tabrik matni
    @dp.message(WishForm.waiting_for_wish, F.text)
    async def process_custom_wish(message: types.Message, state: FSMContext):
        wish_text = message.text.strip()
        if len(wish_text) < 5:
            await message.answer("⚠️ Tabrik matni juda qisqa. Iltimos, batafsilroq tilaklar yozing:")
            return
        
        await state.update_data(wish_text=wish_text)
        await ask_for_photo(message, state)

    async def ask_for_photo(message: types.Message, state: FSMContext, is_edit: bool = False):
        await state.set_state(WishForm.waiting_for_photo)
        text = (
            "3️⃣ <b>3-qadam: Tug'ilgan kun egasining rasmi 📸</b>\n\n"
            "Uning rasmini yuboring (sahifada toj va oltin hoshiyada chiroyli chiqadi).\n\n"
            "<i>Agar rasmi bo'lmasa yoki qo'yishni xohlamasangiz, pastdagi tugmani bosing:</i>"
        )
        if is_edit:
            await message.edit_text(text, parse_mode="HTML", reply_markup=get_skip_photo_keyboard())
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=get_skip_photo_keyboard())

    # Rasm yuborilganda
    @dp.message(WishForm.waiting_for_photo, F.photo)
    async def process_photo(message: types.Message, state: FSMContext, bot: Bot):
        photo = message.photo[-1]
        file_id = photo.file_id
        
        file_info = await bot.get_file(file_id)
        filename = f"{uuid.uuid4().hex}.jpg"
        save_path = UPLOADS_DIR / filename
        
        await bot.download_file(file_info.file_path, destination=save_path)
        await state.update_data(photo_filename=filename)
        
        await ask_for_sender(message, state)

    # Rasm o'tkazib yuborilganda
    @dp.callback_query(WishForm.waiting_for_photo, F.data == "skip_photo")
    async def process_skip_photo(callback: types.CallbackQuery, state: FSMContext):
        await state.update_data(photo_filename=None)
        await ask_for_sender(callback.message, state, is_edit=True)
        await callback.answer()

    # Noto'g'ri formatdagi fayl yuborilganda
    @dp.message(WishForm.waiting_for_photo)
    async def process_invalid_photo(message: types.Message):
        await message.answer(
            "⚠️ Iltimos, rasm yuboring yoki 'O'tkazib yuborish' tugmasini bosing:",
            reply_markup=get_skip_photo_keyboard()
        )

    async def ask_for_sender(message: types.Message, state: FSMContext, is_edit: bool = False):
        await state.set_state(WishForm.waiting_for_sender)
        text = (
            "4️⃣ <b>4-qadam: Tabrik kimdan?</b>\n\n"
            "Ismingizni yoki kim nomidan ekanligini yozing:\n"
            "<i>(Masalan: Sardor, Yaqin do'stingiz, 10-A sinf nomidan...)</i>\n\n"
            "<i>O'tkazib yuborsangiz, standart 'Yaqiningiz' deb ko'rsatiladi:</i>"
        )
        if is_edit:
            await message.edit_text(text, parse_mode="HTML", reply_markup=get_skip_sender_keyboard())
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=get_skip_sender_keyboard())

    # Yuboruvchi ismini qabul qilish
    @dp.message(WishForm.waiting_for_sender, F.text)
    async def process_sender(message: types.Message, state: FSMContext):
        sender_name = message.text.strip()
        await state.update_data(sender_name=sender_name)
        await ask_for_theme(message, state)

    # Yuboruvchini o'tkazib yuborish
    @dp.callback_query(WishForm.waiting_for_sender, F.data == "skip_sender")
    async def process_skip_sender(callback: types.CallbackQuery, state: FSMContext):
        await state.update_data(sender_name="Yaqiningiz")
        await ask_for_theme(callback.message, state, is_edit=True)
        await callback.answer()

    async def ask_for_theme(message: types.Message, state: FSMContext, is_edit: bool = False):
        await state.set_state(WishForm.waiting_for_theme)
        text = (
            "5️⃣ <b>5-qadam: Tabriknoma dizayni / mavzusi 🎨</b>\n\n"
            "Qaysi uslubdagi dizaynni tanlaysiz?"
        )
        if is_edit:
            await message.edit_text(text, parse_mode="HTML", reply_markup=get_theme_keyboard())
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=get_theme_keyboard())

    # Mavzu tanlanganda va generatsiya boshlanganda
    @dp.callback_query(WishForm.waiting_for_theme, F.data.startswith("theme_"))
    async def process_finish_generation(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        theme_choice = callback.data.replace("theme_", "")
        data = await state.get_data()
        await state.clear()

        recipient_name = data.get("recipient_name", "Do'stim")
        wish_text = data.get("wish_text", "Tug'ilgan kuningiz bilan!")
        photo_filename = data.get("photo_filename")
        sender_name = data.get("sender_name", "Yaqiningiz")
        user_id = callback.from_user.id

        await callback.message.edit_text("⏳ <i>Sehrli tabriknoma va QR kod yaratilmoqda...</i>", parse_mode="HTML")

        try:
            slug = await create_wish(
                recipient_name=recipient_name,
                wish_text=wish_text,
                photo_filename=photo_filename,
                sender_name=sender_name,
                theme=theme_choice,
                telegram_user_id=user_id
            )

            wish_url = f"{BASE_URL}/w/{slug}"
            qr_file_path = generate_birthday_qr(wish_url, slug, recipient_name)

            caption = (
                f"🎉 <b>Tabriknoma muvaffaqiyatli tayyorlandi!</b>\n\n"
                f"👤 <b>Tug'ilgan kun egasi:</b> {recipient_name}\n"
                f"💌 <b>Kimdan:</b> {sender_name}\n"
                f"🎨 <b>Mavzu:</b> {theme_choice.capitalize()}\n\n"
                f"📝 <b>Tabrik so'zlari:</b>\n"
                f"<i>«{wish_text[:300]}{'...' if len(wish_text) > 300 else ''}»</i>\n\n"
                f"🔗 <b>Tabriknoma veb-havolasi:</b>\n{wish_url}\n\n"
                f"📱 <b>Qanday yetkaziladi?</b>\n"
                f"1️⃣ Yuqoridagi maxsus QR kod rasmini saqlang va sovg'aga yopishtiring yoki jo'nating!\n"
                f"2️⃣ Telefon kamerasi orqali QR kod skaner qilinganda — musiqa, konfetti va tortli sahifa ochiladi!\n"
                f"3️⃣ Yoki pastdagi tugma orqali tabrikni hoziroq ko'ring 👇"
            )

            buttons = []
            if is_valid_telegram_button_url(wish_url):
                buttons.append([InlineKeyboardButton(text="🌐 Saytda ochish", url=wish_url)])
                if wish_url.startswith("https://"):
                    buttons.append([InlineKeyboardButton(text="📱 Telegram WebApp da ochish", web_app=WebAppInfo(url=wish_url))])

            buttons.append([InlineKeyboardButton(text="👁 Tabriknomani Telegramda ko'rish", callback_data=f"view_wish_{slug}")])
            buttons.append([InlineKeyboardButton(text="🎉 Yangi tabrik yaratish", callback_data="start_create_wish")])
            buttons.append([InlineKeyboardButton(text="📜 Mening tabriklarim", callback_data="my_wishes_list")])
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

            if qr_file_path and os.path.exists(qr_file_path):
                photo_input = FSInputFile(qr_file_path)
                try:
                    await callback.message.delete()
                } catch Exception:
                    pass
                await bot.send_photo(
                    chat_id=callback.message.chat.id,
                    photo=photo_input,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            else:
                await callback.message.edit_text(caption, parse_mode="HTML", reply_markup=keyboard)

            await callback.answer("Tabriknoma tayyor!")

        except Exception as e:
            logger.error(f"Tabriknoma yaratishda xatolik: {e}", exc_info=True)
            is_adm = await check_user_is_admin(user_id)
            await callback.message.edit_text(
                f"⚠️ Kechirasiz, tabriknomani tayyorlashda xatolik yuz berdi:\n<code>{e}</code>\n\nIltimos, qayta urinib ko'ring.",
                reply_markup=get_main_keyboard(is_admin_user=is_adm),
                parse_mode="HTML"
            )

    # Tabriknomani to'liq ko'rish (Preview)
    @dp.callback_query(F.data.startswith("view_wish_"))
    async def cb_view_wish(callback: types.CallbackQuery, bot: Bot):
        slug = callback.data.replace("view_wish_", "")
        wish = await get_wish(slug)
        if not wish:
            await callback.answer("Tabriknoma topilmadi!", show_alert=True)
            return
        
        recipient = wish["recipient_name"]
        text_content = wish["wish_text"]
        sender = wish["sender_name"] or "Yaqiningiz"
        theme = wish.get("theme", "gold")
        views = wish.get("views_count", 0)
        wish_url = f"{BASE_URL}/w/{slug}"
        photo_file = wish.get("photo_filename")

        preview_text = (
            f"👑 <b>{recipient.upper()} UCHUN TUG'ILGAN KUN TABRIKNOMASI</b> 🎉\n\n"
            f"🎂 <i>Bugun sizning eng quvonchli va baxtli kuningiz!</i>\n\n"
            f"💌 <b>Samimiy tilaklar:</b>\n"
            f"«{text_content}»\n\n"
            f"✍️ <b>Hurmat va ehtirom bilan:</b> {sender}\n"
            f"🎨 <b>Uslub:</b> {theme.capitalize()}\n"
            f"👁 <b>Ko'rishlar soni:</b> {views} marta\n"
            f"🔗 <b>Veb havola:</b> {wish_url}\n"
        )

        buttons = []
        if is_valid_telegram_button_url(wish_url):
            buttons.append([InlineKeyboardButton(text="🌐 Saytda ochish", url=wish_url)])
            if wish_url.startswith("https://"):
                buttons.append([InlineKeyboardButton(text="📱 WebApp da ochish", web_app=WebAppInfo(url=wish_url))])

        qr_path = QRCODES_DIR / f"qr_{slug}.png"
        if qr_path.exists():
            buttons.append([InlineKeyboardButton(text="📷 QR kodni qayta olish", callback_data=f"resend_qr_{slug}")])
        buttons.append([InlineKeyboardButton(text="📜 Tabriklarim ro'yxati", callback_data="my_wishes_list")])
        buttons.append([InlineKeyboardButton(text="🎉 Yangi tabrik yaratish", callback_data="start_create_wish")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        sent = False
        if photo_file and (UPLOADS_DIR / photo_file).exists():
            try:
                photo_input = FSInputFile(UPLOADS_DIR / photo_file)
                await bot.send_photo(
                    chat_id=callback.message.chat.id,
                    photo=photo_input,
                    caption=preview_text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                sent = True
            except Exception as e:
                logger.error(f"Foto yuborishda xato: {e}")

        if not sent:
            avatar_path = STATIC_DIR / "default_avatar.png"
            if avatar_path.exists():
                try:
                    photo_input = FSInputFile(avatar_path)
                    await bot.send_photo(
                        chat_id=callback.message.chat.id,
                        photo=photo_input,
                        caption=preview_text,
                        parse_mode="HTML",
                        reply_markup=keyboard
                    )
                    sent = True
                except Exception as e:
                    logger.error(f"Avatar yuborishda xato: {e}")

        if not sent:
            await callback.message.answer(preview_text, parse_mode="HTML", reply_markup=keyboard)

        await callback.answer()

    # QR kodni qayta yuborish
    @dp.callback_query(F.data.startswith("resend_qr_"))
    async def cb_resend_qr(callback: types.CallbackQuery, bot: Bot):
        slug = callback.data.replace("resend_qr_", "")
        qr_path = QRCODES_DIR / f"qr_{slug}.png"
        if qr_path.exists():
            photo_input = FSInputFile(qr_path)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👁 Tabriknomani ko'rish", callback_data=f"view_wish_{slug}")],
                [InlineKeyboardButton(text="⬅️ Tabriklarim", callback_data="my_wishes_list")]
            ])
            await bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=photo_input,
                caption=f"📷 <b>Tabriknoma QR kodi:</b>\n{BASE_URL}/w/{slug}",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            await callback.answer("QR kod yuborildi!")
        else:
            await callback.answer("QR kod topilmadi!", show_alert=True)

    # Mening tabriklarim ro'yxati
    @dp.message(Command("mywishes"))
    @dp.message(F.text == "📜 Mening tabriklarim")
    @dp.callback_query(F.data == "my_wishes_list")
    async def show_my_wishes(event: types.Message | types.CallbackQuery):
        user_id = event.from_user.id
        wishes = await get_user_wishes(user_id)

        if not wishes:
            text = (
                "📜 Siz hali hech qanday tabriknoma yaratmadingiz.\n\n"
                "Birinchi tabriknomani hoziroq yarating! 👇"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎉 Yangi tabrik yaratish", callback_data="start_create_wish")],
                [InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="back_to_menu")]
            ])
        else:
            text = f"📋 <b>Siz yaratgan tabriknomalar ({len(wishes)} ta):</b>\n\n"
            buttons = []
            for idx, w in enumerate(wishes[:10], 1):
                name = w["recipient_name"]
                slug = w["slug"]
                views = w["views_count"]
                url = f"{BASE_URL}/w/{slug}"
                text += f"{idx}. <b>{name}</b> — 👁 {views} marta ko'rilgan\n🔗 {url}\n\n"
                buttons.append([InlineKeyboardButton(text=f"🎁 {name} (Ko'rish 👁)", callback_data=f"view_wish_{slug}")])
            
            buttons.append([InlineKeyboardButton(text="➕ Yangi tabrik yaratish", callback_data="start_create_wish")])
            buttons.append([InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="back_to_menu")])
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        if isinstance(event, types.CallbackQuery):
            await event.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)
            await event.answer()
        else:
            await event.answer(text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)
