import os
import logging
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from groq import Groq

# ==================== SOZLAMALAR ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))

# 10 ta kalitni o'qib olish va ortiqcha bo'shliqlarni tozalash
raw_keys = os.getenv("GROQ_KEYS", "")
API_KEYS = [key.strip() for key in raw_keys.replace("\n", "").split(",") if key.strip()]

if not API_KEYS:
    single_key = os.getenv("GROQ_API_KEY")
    if single_key:
        API_KEYS = [single_key]

current_key_index = 0

def get_next_groq_client():
    global current_key_index
    if not API_KEYS:
        raise ValueError("API kalitlar topilmadi!")
    key = API_KEYS[current_key_index]
    used_index = current_key_index + 1
    current_key_index = (current_key_index + 1) % len(API_KEYS)
    return Groq(api_key=key), used_index

BOT_IDENTITY = "Sardorbek Khudoyberdiyev Dasturchi"
user_memory = {}

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

# ==================== WEB SERVER ====================
async def handle_ping(request):
    return web.Response(text="Sardorbek AI Bot is active and running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Veb-server {PORT}-portda ishga tushdi.")

# ==================== BUYRUQLAR ====================
@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    user_memory[user_id] = []
    await message.answer(
        f"Assalomu alaykum! Meni {BOT_IDENTITY} yaratgan.\n\n"
        "Menga istalgan matnli savol yuborishingiz mumkin. Qanday yordam bera olaman?"
    )

# ==================== XABARLAR ====================
@dp.message(F.text)
async def handle_messages(message: types.Message):
    user_id = message.from_user.id
    user_text = message.text

    if user_id not in user_memory:
        user_memory[user_id] = []

    user_memory[user_id].append({"role": "user", "content": user_text})
    
    if len(user_memory[user_id]) > 6:
        user_memory[user_id] = user_memory[user_id][-6:]

    system_prompt = {
        "role": "system", 
        "content": (
            f"Sizning yagona ismingiz: Sardorbek AI. Sizni {BOT_IDENTITY} yaratgan. "
            "DIQQAT: Siz hech qachon o'zingizni ChatGPT yoki OpenAI deb atamang! "
            "Ismingizni so'rashsa 'Mening ismim Sardorbek AI, meni Sardorbek Khudoyberdiyev yaratgan' deb javob bering. "
            "O'zbek tilida ravon javob bering."
        )
    }

    messages_payload = [system_prompt] + user_memory[user_id]
    attempts = len(API_KEYS) if API_KEYS else 1
    reply_text = None

    for _ in range(attempts):
        try:
            groq_client, used_key_num = get_next_groq_client()
            # Eng barqaror Groq modeli ishlatilmoqda
            completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages_payload,
                temperature=0.6
            )
            reply_text = completion.choices[0].message.content.strip()
            logging.info(f"Muvaffaqiyatli bajarildi. Ishlatilgan kalit raqami: {used_key_num}")
            break
        except Exception as e:
            logging.warning(f"Kalit xatosi ({used_key_num}-kalit): {str(e)}")
            continue

    if not reply_text:
        if user_memory[user_id]:
            user_memory[user_id].pop()
        await message.answer("Kechirasiz, barcha kalitlar vaqtincha band yoki xatolik yuz berdi. Iltimos, birozdan keyin urinib ko'ring.")
        return

    for forbidden_word in ["ChatGPT", "chatgpt", "Chatgpt", "OpenAI", "openai", "GPT"]:
        reply_text = reply_text.replace(forbidden_word, "Sardorbek AI")

    user_memory[user_id].append({"role": "assistant", "content": reply_text})
    await message.answer(reply_text)

# ==================== MAIN ====================
async def main():
    await start_web_server()
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
