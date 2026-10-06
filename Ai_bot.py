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
    user_memory[user_id].clear()
    
    await message.answer(
        f"Assalomu alaykum! Men — **Sardorbek AI** man. Meni {BOT_IDENTITY} yaratgan.\n\n"
        "Menga istalgan mavzuda savol bering, yordam berishdan xursand bo'laman!",
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

# ---------------- TEXT HANDLER ----------------
@dp.message(F.text)
async def text_handler(message: types.Message):
    user_id = message.from_user.id
    save_user(user_id)
    
    user_text = message.text
    user_memory[user_id].append({"role": "user", "content": user_text})
    
    # Xotira haddan tashqari uzun bo'lib ketib, eski mavzular aralashib ketmasligi uchun oxirgi 6 ta xabarni qoldiramiz
    if len(user_memory[user_id]) > 6:
        user_memory[user_id] = user_memory[user_id][-6:]

    try:
        # Eng qat'iy system prompt (ChatGPT nomini butunlay bloklash uchun)
        system_prompt = {
            "role": "system", 
            "content": (
                f"Sizning yagona ismingiz: Sardorbek AI. Sizni {BOT_IDENTITY} yaratgan. "
                "DIQQAT: Siz hech qachon, hech qanday sharoitda o'zingizni ChatGPT, OpenAI yoki boshqa sun'iy intellekt deb atamasligingiz shart! "
                "Agar sizdan ismingizni so'rashsa, faqat va faqat 'Mening ismim Sardorbek AI' deb javob bering. "
                "O'zbek tilida ravon, tushunarli va aniq javob bering. "
                "Javobingiz oxirida foydalanuvchiga shu mavzuni davom ettirish uchun qo'shimcha variantlar yoki takliflar yozib qoldiring."
            )
        }

        messages_payload = [system_prompt] + user_memory[user_id]

        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages_payload,
            temperature=0.5  # Model adashib ketmasligi uchun temperatirani pasaytiramiz
        )
        
        reply_text = completion.choices[0].message.content.strip()
        
        # Agar model javobida adashib ChatGPT so'zi kelsa, uni avtomatik ravishda Sardorbek AI ga almashtiramiz
        reply_text = reply_text.replace("ChatGPT", "Sardorbek AI").replace("chatgpt", "Sardorbek AI")

        user_memory[user_id].append({"role": "assistant", "content": reply_text})
        
        await message.answer(reply_text, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Xatolik yuz berdi: {e}")
        if user_memory[user_id]:
            user_memory[user_id].pop()
            
        await message.answer("Kechirasiz, so'rovni bajarishda xatolik yuz berdi. Qaytadan yozib ko'ring.")

# ---------------- MAIN ----------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
