import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from groq import Groq

# ---------------- CONFIGURATION ----------------
TOKEN = os.getenv("TELEGRAM_TOKEN", "SIZNING_BOT_TOKENINGIZ")
GROQ_API_KEY = os.getenv("API_KEYS", "SIZNING_GROQ_API_KEY")
ADMIN_ID = 123456789  # O'zingizning Telegram ID raqamingiz

ADMIN_USERNAME_LINK = "https://t.me/@Sardorbek_Ai_admin"
BOT_IDENTITY = "Sardorbek Khudoyberdiyev Dasturchi"

# Foydalanuvchilar suhbat tarixi uchun xotira
user_memory = {}
vip_users = set()

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
    user_memory[user_id].clear()  # Start bosilganda xotirani tozalash
    
    await message.answer(
        f"Assalomu alaykum! Men — **{BOT_IDENTITY}** tomonidan yaratilgan sun'iy intellekt yordamchisiman.\n\n"
        "Menga istalgan matnli savol yuborishingiz mumkin. Savollaringizni bir-biriga bog'lab, muloqotni davom ettira olaman!",
        parse_mode="Markdown"
    )

# ---------------- IMAGE COMMAND & VIP CHECK ----------------
@dp.message(Command("image"))
async def image_command(message: types.Message):
    user_id = message.from_user.id
    
    if user_id not in vip_users and user_id != ADMIN_ID:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 VIP huquqni olish", url=ADMIN_USERNAME_LINK)]
        ])
        await message.answer(
            "⚠️ **Rasm yaratish funksiyasi faqat VIP foydalanuvchilar uchun!**",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return

    await message.answer("🖼 Rasm yaratish so'rovi qabul qilindi.")

# ---------------- TEXT HANDLER (GROQ API WITH MEMORY) ----------------
@dp.message(F.text)
async def text_handler(message: types.Message):
    user_id = message.from_user.id
    save_user(user_id)
    
    user_text = message.text
    
    # Foydalanuvchi xabarini xotiraga qo'shamiz
    user_memory[user_id].append({"role": "user", "content": user_text})
    
    # Xotira juda uzun bo'lib ketmasa uchun oxirgi 10 ta xabarni qoldiramiz
    if len(user_memory[user_id]) > 10:
        user_memory[user_id] = user_memory[user_id][-10:]

    try:
        # Sistema promti: sun'iy intellektga uning vazifasi va kontekstni tushunishi kerakligi uqtiriladi
        system_prompt = {
            "role": "system", 
            "content": (
                f"Sizning ismingiz va shaxsingiz: {BOT_IDENTITY}. "
                "Siz o'zbek tilida javob beruvchi aqlli yordamchisiz. "
                "Foydalanuvchining oldingi savollari va kontekstini doimo yodda saqlang. "
                "Masalan, agar foydalanuvchi 'Navoiy kim' deb so'rasa va keyin 'g'azallari' desa, "
                "bu Alisher Navoiyning g'azallari ekanligini tushunib, unga qarab javob bering."
            )
        }

        # API ga system prompt va foydalanuvchining butun oxirgi suhbat tarixini yuboramiz
        messages_payload = [system_prompt] + user_memory[user_id]

        completion = groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",  # yoki mavjud boshqa model
            messages=messages_payload
        )
        
        reply_text = completion.choices[0].message.content
        
        # Botning javobini ham xotiraga yozib qo'yamiz (keyingi safar kontekst uzilib qolmasligi uchun)
        user_memory[user_id].append({"role": "assistant", "content": reply_text})
        
        await message.answer(reply_text, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Xatolik yuz berdi: {e}")
        await message.answer("Kechirasiz, so'rovingizni qayta ishlashda xatolik yuz berdi.")

# ---------------- MAIN ----------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
