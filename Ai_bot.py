import os
import logging
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from groq import Groq

# ---------------- CONFIGURATION ----------------
TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PORT = int(os.getenv("PORT", 8080))  # Render avtomatik beradigan port

ADMIN_ID = 123456789  
ADMIN_USERNAME_LINK = "https://t.me/@Sardorbek_Ai_admin"
BOT_IDENTITY = "Sardorbek Khudoyberdiyev Dasturchi"

user_memory = {}
vip_users = set()

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)

logging.basicConfig(level=logging.INFO)

def save_user(user_id):
    if user_id not in user_memory:
        user_memory[user_id] = []

# ---------------- WEB SERVER (Monitoring uchun) ----------------
async def handle_ping(request):
    # UptimeRobot har gal so'rov yuborganda ushbu javob qaytariladi va bot uxlamaydi
    return web.Response(text="Bot is running and alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Web server started on port {PORT}")

# ---------------- COMMANDS & HANDLERS ----------------
@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    save_user(user_id)
    user_memory[user_id].clear()
    
    await message.answer(
        f"Assalomu alaykum! Meni {BOT_IDENTITY} yaratgan. Menga matnli savol yoki dasturlash kodi yuboring, javob beraman."
    )

@dp.message(F.text)
async def text_handler(message: types.Message):
    user_id = message.from_user.id
    save_user(user_id)
    
    user_text = message.text
    user_memory[user_id].append({"role": "user", "content": user_text})
    
    if len(user_memory[user_id]) > 6:
        user_memory[user_id] = user_memory[user_id][-6:]

    try:
        system_prompt = {
            "role": "system", 
            "content": (
                f"Sizning yagona ismingiz: Sardorbek AI. Sizni {BOT_IDENTITY} yaratgan. "
                "DIQQAT: Siz hech qachon, hech qanday sharoitda o'zingizni ChatGPT, OpenAI yoki boshqa sun'iy intellekt deb atamasligingiz shart! "
                "Agar sizdan ismingizni so'rashsa, faqat va faqat 'Mening ismim Sardorbek AI' deb javob bering. "
                "O'zbek tilida ravon, tushunarli va aniq javob bering."
            )
        }

        messages_payload = [system_prompt] + user_memory[user_id]

        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages_payload,
            temperature=0.5
        )
        
        reply_text = completion.choices[0].message.content.strip()
        
        for forbidden_word in ["ChatGPT", "chatgpt", "Chatgpt", "OpenAI", "openai", "GPT"]:
            reply_text = reply_text.replace(forbidden_word, "Sardorbek AI")

        user_memory[user_id].append({"role": "assistant", "content": reply_text})
        
        await message.answer(reply_text)
        
    except Exception as e:
        error_msg = f"❌ Xatolik yuz berdi: {str(e)}"
        logging.error(error_msg)
        if user_memory[user_id]:
            user_memory[user_id].pop()
        await message.answer(error_msg)

# ---------------- MAIN (Ikkalasini birga yuritish) ----------------
async def main():
    # Veb-serverni va bot polling'ni bir vaqtning o'zida ishga tushiramiz
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
