import os
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from groq import Groq

# ---------------- CONFIGURATION ----------------
TOKEN = os.getenv("TELEGRAM_TOKEN", "SIZNING_BOT_TOKENINGIZ")
GROQ_API_KEY = os.getenv("API_KEYS", "SIZNING_GROQ_API_KEY")
ADMIN_ID = 123456789  # O'zingizning Telegram ID raqamingiz

# Admin bilan bog'lanish uchun havola
ADMIN_USERNAME_LINK = "https://t.me/@Sardorbek_Ai_admin"

# Bot shaxsi va xotirasi
BOT_IDENTITY = "Sardorbek Khudoyberdiyev Dasturchi"
user_memory = {}
vip_users = set()

# Botni ishga tushirish
bot = Bot(token=TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)

logging.basicConfig(level=logging.INFO)

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
        "Menga istalgan matnli yoki **ovozli xabar** yuborishingiz mumkin, ularni tushunib javob beraman!",
        parse_mode="Markdown"
    )

# ---------------- VOICE MESSAGE HANDLER (WHISPER API) ----------------
@dp.message(lambda message: message.voice is not None)
async def voice_handler(message: types.Message):
    user_id = message.from_user.id
    save_user(user_id)
    
    await message.answer("🎙 Ovozli xabaringiz qabul qilindi, matnga o'girilmoqda...")

    try:
        # 1. Telegram serveridan ovozli faylni yuklab olish
        voice = message.voice
        file = await bot.get_file(voice.file_id)
        file_path = file.file_path
        
        # Ovozli faylni vaqtincha saqlab turish uchun nom
        local_audio_file = f"voice_{user_id}.ogg"
        await bot.download_file(file_path, local_audio_file)

        # 2. Groq Whisper API yordamida ovozni matnga o'girish
        with open(local_audio_file, "rb") as audio_file:
            transcript = groq_client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_file,
                prompt="O'zbek tilidagi ovozli xabar"
            )
        
        user_text = transcript.text
        
        # Vaqtincha faylni o'chirib tashlash
        if os.path.exists(local_audio_file):
            os.remove(local_audio_file)

        if not user_text.strip():
            await message.answer("Kechirasiz, ovozingizni aniqlay olmadim. Qaytadan urinib ko'ring.")
            return

        # Foydalanuvchiga nima deb yozganini bildirish
        await message.answer(f"📝 **Sizning ovozingiz:** \"{user_text}\"", parse_mode="Markdown")

        # 3. Groq LLM orqali matnga javob olish
        user_memory[user_id].append({"role": "user", "content": user_text})
        
        completion = groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": f"Sizning ismingiz va shaxsingiz: {BOT_IDENTITY}. Doimiy ravishda o'zbek tilida professional tarzda javob bering."}
            ] + user_memory[user_id][-10:]
        )
        
        reply_text = completion.choices[0].message.content
        user_memory[user_id].append({"role": "assistant", "content": reply_text})
        
        await message.answer(reply_text, parse_mode="Markdown")

    except Exception as e:
        logging.error(f"Ovozli xabarni qayta ishlashda xatolik: {e}")
        await message.answer("Kechirasiz, ovozli xabaringizni qayta ishlashda xatolik yuz berdi.")

# ---------------- IMAGE GENERATION & VIP CHECK ----------------
@dp.message(Command("image"))
async def image_command(message: types.Message):
    user_id = message.from_user.id
    
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

    await message.answer("🖼 Rasm yaratish so'rovi qabul qilindi.")

# ---------------- TEXT HANDLER (GROQ API) ----------------
@dp.message()
async def text_handler(message: types.Message):
    user_id = message.from_user.id
    save_user(user_id)
    
    user_text = message.text
    user_memory[user_id].append({"role": "user", "content": user_text})
    
    try:
        completion = groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": f"Sizning ismingiz va shaxsingiz: {BOT_IDENTITY}. Doimiy ravishda o'zbek tilida professional tarzda javob bering."}
            ] + user_memory[user_id][-10:]
        )
        
        reply_text = completion.choices[0].message.content
        user_memory[user_id].append({"role": "assistant", "content": reply_text})
        
        await message.answer(reply_text, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f5"Xatolik yuz berdi: {e}")
        await message.answer("Kechirasiz, so'rovingizni qayta ishlashda xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.")

# ---------------- MAIN ----------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
