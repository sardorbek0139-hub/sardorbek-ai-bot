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

# Render'dagi GROQ_KEYS o'zgaruvchisidan kalitlarni vergul orqali o'qiymiz
raw_keys = os.getenv("GROQ_KEYS", "")
API_KEYS = [key.strip() for key in raw_keys.split(",") if key.strip()]

# Agar GROQ_KEYS topilmasa, zaxira sifatida bitta GROQ_API_KEY ni olamiz
if not API_KEYS:
    single_key = os.getenv("GROQ_API_KEY")
    if single_key:
        API_KEYS = [single_key]

# Kalitlar indeksi (qaysi kalit navbatda ekanligini kuzatish uchun)
current_key_index = 0

def get_next_groq_client():
    """Navbatdagi API kalitni olib, Groq klientini qaytaradi va indeksni suradi"""
    global current_key_index
    if not API_KEYS:
        raise ValueError("Hech qanday Groq API kaliti topilmadi!")
    
    key = API_KEYS[current_key_index]
    used_index = current_key_index + 1
    # 10 ta kalit tugagach, yana boshidan (1-kalitga) qaytadi
    current_key_index = (current_key_index + 1) % len(API_KEYS)
    return Groq(api_key=key), used_index

BOT_IDENTITY = "Sardorbek Khudoyberdiyev Dasturchi"

# Foydalanuvchilar suhbat tarixi (Xotira)
user_memory = {}

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

# ==================== WEB SERVER (UptimeRobot uchun) ====================
async def handle_ping(request):
    return web.Response(text="Sardorbek AI Bot is active and running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Veb-server {PORT}-portda muvaffaqiyatli ishga tushdi.")

# ==================== BOT BUYRUQLARI ====================
@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    user_memory[user_id] = []
    
    await message.answer(
        f"Assalomu alaykum! Meni {BOT_IDENTITY} yaratgan.\n\n"
        "Menga istalgan matnli savol yoki dasturlash bo'yicha murojaat yuborishingiz mumkin. Qanday yordam bera olaman?"
    )

# ==================== XABARLAR BILAN ISHLASH (Kalit almashtirish tizimi) ====================
@dp.message(F.text)
async def handle_messages(message: types.Message):
    user_id = message.from_user.id
    user_text = message.text

    if user_id not in user_memory:
        user_memory[user_id] = []

    user_memory[user_id].append({"role": "user", "content": user_text})
    
    # Xotira hajmi oshib ketmasligi uchun oxirgi 6 ta xabarni saqlaymiz
    if len(user_memory[user_id]) > 6:
        user_memory[user_id] = user_memory[user_id][-6:]

    system_prompt = {
        "role": "system", 
        "content": (
            f"Sizning yagona ismingiz: Sardorbek AI. Sizni {BOT_IDENTITY} yaratgan. "
            "DIQQAT: Siz hech qachon, hech qanday sharoitda o'zingizni ChatGPT, OpenAI, Google yoki boshqa sun'iy intellekt deb atamasligingiz shart! "
            "Agar sizdan kim yaratganini yoki ismingizni so'rashsa, faqat va faqat 'Mening ismim Sardorbek AI, meni Sardorbek Khudoyberdiyev yaratgan' deb javob bering. "
            "O'zbek tilida ravon, tushunarli va aniq javob bering."
        )
    }

    messages_payload = [system_prompt] + user_memory[user_id]

    # Barcha kalitlar soni bo'yicha urinib ko'ramiz (agar bittasi limitda bo'lsa, keyingisiga o'tadi)
    attempts = len(API_KEYS) if API_KEYS else 1
    reply_text = None

    for _ in range(attempts):
        try:
            groq_client, used_key_num = get_next_groq_client()
            
            completion = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages_payload,
                temperature=0.6
            )
            
            reply_text = completion.choices[0].message.content.strip()
            logging.info(f"Muvaffaqiyatli bajarildi. Ishlatilgan API kalit tartib raqami: {used_key_num}-kalit")
            break  # Hammasi joyida bo'lsa, sikldan chiqamiz
            
        except Exception as e:
            # Agar limit to'lgan yoki xatolik chiqqan bo'lsa, logga yozib keyingi kalitga o'tamiz
            logging.warning(f"Kalit limitga yetdi yoki xatolik bo'ldi, keyingisiga o'tilmoqda: {str(e)}")
            continue

    if not reply_text:
        if user_memory[user_id]:
            user_memory[user_id].pop()
        await message.answer("Kechirasiz, barcha API kalitlarimiz vaqtincha limitga yetdi. Iltimos, birozdan keyin qayta urinib ko'ring.")
        return

    # Xavfsizlik uchun taqiqlangan so'zlarni almashtiramiz
    for forbidden_word in ["ChatGPT", "chatgpt", "Chatgpt", "OpenAI", "openai", "GPT"]:
        reply_text = reply_text.replace(forbidden_word, "Sardorbek AI")

    user_memory[user_id].append({"role": "assistant", "content": reply_text})
    await message.answer(reply_text)

# ==================== ASOSIY ISHGA TUSHIRISH ====================
async def main():
    await start_web_server()
    logging.info("Telegram bot ishga tushdi va xabarlarni qabul qilmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
