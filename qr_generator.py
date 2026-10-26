import os
from pathlib import Path
from config import QRCODES_DIR

def generate_birthday_qr(url: str, slug: str, recipient_name: str) -> str:
    """
    Tug'ilgan kun uchun maxsus dizayndagi QR kod rasmini generatsiya qilish.
    Chiroyli hoshiya, tabrik yozuvi va ko'rsatmalar bilan sovg'abop karta holiga keltiradi.
    """
    output_path = QRCODES_DIR / f"qr_{slug}.png"
    
    try:
        import qrcode
        from PIL import Image, ImageDraw, ImageFont

        # QR kod obyektini yaratish
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)

        qr_img = qr.make_image(fill_color="#1e1b4b", back_color="#ffffff").convert("RGBA")
        qr_w, qr_h = qr_img.size

        # Karta o'lchamlari
        card_w = qr_w + 120
        card_h = qr_h + 240

        # Gradient fon yoki to'q binafsha/oltin hashamatli fon
        card = Image.new("RGBA", (card_w, card_h), (255, 255, 255, 255))
        draw = ImageDraw.Draw(card)

        # Oltin/binafsha hoshiya (Gold border)
        border_color = (245, 158, 11) # Amber/Gold
        bg_card_color = (254, 252, 232) # Soft gold tint
        
        # Ichki fon
        draw.rounded_rectangle(
            [(10, 10), (card_w - 10, card_h - 10)],
            radius=24,
            fill=bg_card_color,
            outline=border_color,
            width=5
        )
        # Ichki ingichka hoshiya
        draw.rounded_rectangle(
            [(18, 18), (card_w - 18, card_h - 18)],
            radius=18,
            outline=(217, 119, 6),
            width=2
        )

        # Matnlarni yozish
        # Standart shrift
        font_large = None
        font_sub = None
        font_desc = None
        try:
            # Windows standart shriftlari
            font_large = ImageFont.truetype("arialbd.ttf", 26)
            font_sub = ImageFont.truetype("arialbd.ttf", 20)
            font_desc = ImageFont.truetype("arial.ttf", 15)
        except Exception:
            font_large = ImageFont.load_default()
            font_sub = font_large
            font_desc = font_large

        # Sarlavha: HAPPY BIRTHDAY
        title_text = "HAPPY BIRTHDAY!"
        draw.text(
            (card_w / 2, 45),
            title_text,
            fill=(180, 83, 9),
            font=font_large,
            anchor="mm"
        )

        # Ism: [Ism] uchun maxsus tabriknoma
        name_display = f"{recipient_name[:24]} uchun"
        draw.text(
            (card_w / 2, 85),
            name_display,
            fill=(67, 56, 202),
            font=font_sub,
            anchor="mm"
        )

        # QR kodni markazga joylashtirish
        qr_x = (card_w - qr_w) // 2
        qr_y = 120
        card.paste(qr_img, (qr_x, qr_y), qr_img)

        # Pastki matn: Ko'rsatma
        instruction_text = "Telefon kamerangizni QR kodga qarating"
        sub_instruction = "va sehrli tabriknomani oching!"
        draw.text(
            (card_w / 2, qr_y + qr_h + 35),
            instruction_text,
            fill=(55, 65, 81),
            font=font_desc,
            anchor="mm"
        )
        draw.text(
            (card_w / 2, qr_y + qr_h + 65),
            sub_instruction,
            fill=(225, 29, 72),
            font=font_desc,
            anchor="mm"
        )

        # Saqlash
        card.save(output_path, "PNG")
        return str(output_path)

    except Exception as e:
        # Xatolik bo'lsa (masalan qrcode kutubxonasi hali to'liq ulanmagan bo'lsa), oddiy usul
        print(f"QR kod generatsiyasida xatolik: {e}")
        try:
            import qrcode
            qr_img = qrcode.make(url)
            qr_img.save(output_path)
            return str(output_path)
        except Exception:
            return ""
