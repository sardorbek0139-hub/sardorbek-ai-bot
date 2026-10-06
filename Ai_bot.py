import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from groq import Groq

# ---------------- CONFIGURATION ----------------
# Render'dagi nomlarga moslandi (TELEGRAM_TOKEN va API_KEYS)
TOKEN = os.getenv("TELEGRAM_TOKEN", "SIZNING_BOT_TOKENINGIZ")
GROQ_API_KEY = os.getenv("API_KEYS", "SIZNING_GROQ_API_KEY")
ADMIN_ID = 123456789  # O'zingizning Telegram ID raqamingizni yozing

# Admin bilan bog'lanish uchun static havola
ADMIN_USERNAME_LINK = "https://t.me/@Sardorbek_Ai_admin"

# Bot shaxsi va xotirasi
BOT_IDENTITY = "Sardorbek Khudoyberdiyev Dasturchi"
user_memory = {}
vip_users = set()  # VIP foydalanuvchilar ro'yxati

# Botni ishga tushirish
bot = Bot(token=TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)

logging.basicConfig(level=logging.INFO)

# Foydalanuvchini ro'yxatga olish funksiyasi
def save_user(user_id):
    if user_id not in user_memory:
        user_memory[user_id] = []

# ---------------- COMMANDS ----------------
@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    save_user(user_id)
    
    await message.answer(
        f"Assalomu alaykum! Men — **{BOT_IDENTITY}** tomonidan yaratilgan sun'iy intellekt yordamchisiman.\n\n"
        "Menga istalgan savolingizni yuborishingiz yoki rasm yaratish / ovozli suhbat rejimlaridan foydalanishingiz mumkin!",
        parse_mode="Markdown"
    )

@dp.message(Command("voice"))
async def voice_chat_command(message: types.Message):
    save_user(message.from_user.id)
    
    # Netlify orqali olingan jonli havola ulandi
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🎙 Jonli Ovozli Suhbatni Boshlash", 
                web_app=WebAppInfo(url="https://calm-dieffenbachia-eabf5a.netlify.app")
            )
        ]
    ])
    
    await message.answer(
        "🎙 **Jonli ovozli muloqot rejimi**\n\n"
        "Sun'iy intellekt bilan real vaqt rejimida ovozli suhbatlashish uchun pastdagi tugmani bosing:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# ---------------- IMAGE GENERATION & VIP CHECK ----------------
@dp.message(Command("image"))
async def image_command(message: types.Message):
    user_id = message.from_user.id
    
    # VIP cheklovini tekshirish
    if user_id not in vip_users and user_id != ADMIN_ID:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔒 VIP huquqni olish", url=ADMIN_USERNAME_LINK)
            ]
        ])
        await message.answer(
            "⚠️ **Diqqat! Rasm yaratish funksiyasi faqat VIP foydalanuvchilar uchun ochilgan.**\n\n"
            "Ushbu imkoniyatni yoqish uchun adminga murojaat qiling:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return

    await message.answer("🖼 Rasm yaratish so'rovi qabul qilindi. (Bu yerda rasm generatsiya qilish logikasi ishlaydi)")

# ---------------- TEXT HANDLER (GROQ API) ----------------
@dp.message()
async def text_handler(message: types.Message):
    user_id = message.from_user.id
    save_user(user_id)
    
    user_text = message.text
    user_memory[user_id].append({"role": "user", "content": user_text})
    
    try:
        # Groq API orqali javob olish (gpt-oss-120b modeli)
        completion = groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": f"Sizning ismingiz va shaxsingiz: {BOT_IDENTITY}. Doimiy ravishda o'zbek tilida professional tarzda javob bering."}
            ] + user_memory[user_id][-10:]  # Oxirgi 10 ta xabar tarixi
        )
        
        reply_text = completion.choices[0].message.content
        user_memory[user_id].append({"role": "assistant", "content": reply_text})
        
        await message.answer(reply_text, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Xatolik yuz berdi: {e}")
        await message.answer("Kechirasiz, so'rovingizni qayta ishlashda xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.")

# ---------------- MAIN ----------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
