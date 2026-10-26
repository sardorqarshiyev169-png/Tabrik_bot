import asyncio
from database import init_db, create_wish, get_wish
from qr_generator import generate_birthday_qr
from config import BASE_URL

async def test():
    print("1. Initializing DB...")
    await init_db()

    print("2. Creating demo wish...")
    slug = await create_wish(
        recipient_name="Madinaxon",
        wish_text="Qadrdonim Madinaxon! Tug'ilgan kuningiz bilan chin yurakdan muborakbod etaman! Hayotingiz doimo quvonch, muhabbat va baxtga to'la bo'lsin. Har doim kulib yuring! 🎂✨💖",
        photo_filename=None, # Will use the lovely default 3D cake avatar
        sender_name="Jasurbek",
        theme="gold",
        telegram_user_id=123456
    )

    url = f"{BASE_URL}/w/{slug}"
    print(f"3. Wish created successfully! Slug: {slug}")
    print(f"   URL: {url}")

    print("4. Generating QR code...")
    qr_path = generate_birthday_qr(url, slug, "Madinaxon")
    print(f"   QR Code generated at: {qr_path}")

    print("5. Verifying DB fetch...")
    wish = await get_wish(slug)
    print(f"   Fetched: {wish['recipient_name']} | Views: {wish['views_count']}")
    print("\n✅ All tests passed successfully!")

if __name__ == "__main__":
    asyncio.run(test())
