# 🎂 Tug'ilgan Kun Tabrik Boti (QR Kodli Interaktiv Tabriknoma)

Ushbu bot yaqinlaringiz uchun **sehrli, musiqali va interaktiv** tug'ilgan kun tabriknomalarini yaratadi va uni **chiroyli dizayndagi QR kod** ko'rinishida taqdim etadi!

---

## 🌟 Imkoniyatlar va Qulayliklar:

1. **Bosqichma-bosqich qulay FSM jarayoni:**
   - 👤 Tug'ilgan kun sohibi (egasi) ismi.
   - ✍️ Tabrik matni (o'z tilaklarini yozish yoki 4 xil tayyor chiroyli shablonlardan birini tanlash).
   - 📸 Egasining rasmini yuklash (agar rasm bo'lmasa, avtomatik chiroyli 3D bayramona tort avatari qo'yiladi).
   - 💌 Tabrik kimdanligi (o'z ismini yozish yoki anonim qoldirish).
   - 🎨 Dizayn mavzusi (🌟 Hashamatli Oltin, 🎆 Cyber Neon, 🌹 Romantik Atirgul).

2. **Sovg'abop Karta shaklidagi maxsus QR Kod:**
   - Standart qora-oq QR kod emas, balki hashamatli oltin hoshiyali, "Happy Birthday", ism va ko'rsatmalar yozilgan tayyor sovg'a kartasi ko'rinishida rasm generatsiya qilinadi.
   - Uni chop etib sovg'a qutisiga, gul dastasiga yoki konvertga yopishtirish mumkin!

3. **QR kod ochilganda chiqadigan sehrli veb-sahifa:**
   - 🎁 **Sovg'ani ochish introsi:** Ekranda sovg'a qutisi chiqadi, ochish tugmasi bosilganda konfetti otiladi!
   - 🎵 **"Happy Birthday" musiqasi:** Web Audio API orqali avtomatik yoqiladi (musiqa tugmasi bilan to'xtatish mumkin).
   - 🎈 **Uchib yuruvchi rang-barang sharlar va chaqnoq yulduzchalar.**
   - 🎂 **Interaktiv bayram torti va sham:** Tug'ilgan kun egasi ekrandagi shamni bosganda sham o'chadi, tutun chiqadi, qarsaklar va yangi konfetti otiladi!
   - 👑 **Oltin hoshiyali rasm va toj:** Yuklangan rasm gradientli nur sochib turadi.
   - 🔗 **Ulashish tugmasi:** Bir marta bosish bilan havolani do'stlarga nusxalash yoki ulashish.
   - 📱 **Telegram WebApp:** Telegramning o'zida ham to'g'ridan-to'g'ri ochiladi!

---

## 🚀 Ishga tushirish:

### 1. Bot tokenini o'rnatish
Telegramda [@BotFather](https://t.me/BotFather) ga kiring, `/newbot` buyrug'i orqali yangi bot oching va berilgan **API Token**ni oling.
Keyin `.env` faylini ochib, tokeningizni yozing:

```env
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
PORT=8080
BASE_URL=http://localhost:8080
```

> **Eslatma:** Agar tabriknomangiz butun internet bo'ylab boshqa telefonlarda ham ochilishini xohlasangiz, `BASE_URL` ga [Ngrok](https://ngrok.com) havolangizni yoki o'z serveringiz domenini yozishingiz mumkin (masalan: `https://sizning-domen.uz` yoki `https://abc-123.ngrok-free.app`).

### 2. Admin sozlamalari (`.env`)
Admin Telegram ID raqamini `.env` faylida belgilashingiz mumkin:
```env
BOT_TOKEN=8725456314:AAE8_hnW4Znhs-l16Rt08SXE1QKg7RXQp_U
ADMIN_IDS=6363224227
ADMIN_PASSWORD=admin123
PORT=8080
BASE_URL=
```

---

## 👑 Admin Panel va Reklama / Statistika Tizimi:

### 1. Bot ichidagi Admin Panel (`/admin`):
- 📊 **Foydalanuvchilar statistikasi:**
  - Jami bot foydalanuvchilari soni
  - Faol a'zolar va botni bloklaganlar soni
  - Bugun qo'shilgan va faol bo'lganlar
  - Jami yaratilgan tabriknomalar va ko'rishlar soni
- 📢 **Xabarnoma / Reklama yuborish (Broadcast):**
  - Barcha bot foydalanuvchilariga xabar yuborish
  - Matn, rasm + izoh, video yoki forward qilingan postlar
  - Yuborishdan oldin ko'rib chiqish (**Preview**) va tasdiqlash
  - Muvaffaqiyatli yetkazilganlar va bloklaganlar hisoboti
- 👥 **Oxirgi foydalanuvchilar ro'yxati:**
  - So'nggi faol a'zolar, ularning ID si, username va holati

### 2. Zamonaviy Web Dashboard (`http://localhost:8080/admin`):
- Real-time grafik va hisoblagichlar
- Brauzerdan turib to'g'ridan-to'g'ri reklama yuborish
- Yaratilgan barcha tabriknomalar va foydalanuvchilar jadvali

---

### 3. Dasturni ishga tushirish

Terminalda:
```bash
python main.py
```
Yoki Windowsda `run.bat` faylini ikki marta bosing!

