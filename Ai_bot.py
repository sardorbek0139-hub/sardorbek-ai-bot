import os
import logging
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from groq import Groq
from google import genai
from google.genai import types as genai_types

# ==================== SOZLAMALAR ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))

# --- GROQ API KALITLAR (Matn uchun) ---
raw_groq_keys = os.getenv("GROQ_KEYS", "")
API_KEYS = [key.strip() for key in raw_groq_keys.replace("\n", "").split(",") if key.strip()]
if not API_KEYS:
    single_key = os.getenv("GROQ_API_KEY")
    if single_key:
        API_KEYS = [single_key]

current_groq_index = 0

def get_next_groq_client():
    global current_groq_index
    if not API_KEYS:
        raise ValueError("Groq API kalitlari topilmadi!")
    key = API_KEYS[current_groq_index]
    used_index = current_groq_index + 1
    current_groq_index = (current_groq_index + 1) % len(API_KEYS)
    return Groq(api_key=key), used_index


# --- GEMINI API KALITLAR ---
raw_gemini_keys = os.getenv("GEMINI_KEYS", "")
GEMINI_API_KEYS = [key.strip() for key in raw_gemini_keys.replace("\n", "").split(",") if key.strip()]

current_gemini_index = 0

def get_next_gemini_client():
    global current_gemini_index
    if not GEMINI_API_KEYS:
        return None, 0
    key = GEMINI_API_KEYS[current_gemini_index]
    used_index = current_gemini_index + 1
    current_gemini_index = (current_gemini_index + 1) % len(GEMINI_API_KEYS)
    return genai.Client(api_key=key), used_index


BOT_IDENTITY = "Sardorbek Khudoyberdiyev Dasturchi"
user_memory = {}

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
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
        f"Assalomu alaykum! Meni <b>{BOT_IDENTITY}</b> yaratgan.\n\n"
        "Menga istalgan fan bo'yicha matnli savol yuborishingiz yoki <b>rasm yuborib</b> tahlil qilishni so'rashingiz mumkin. Qanday yordam bera olaman?"
    )

# ==================== RASM TUSHUNTIRISH (GEMINI 1.5 FLASH) ====================
@dp.message(F.photo)
async def handle_photos(message: types.Message):
    if not GEMINI_API_KEYS:
        await message.answer("Kechirasiz, Gemini API kalitlari sozlanmagan.")
        return

    processing_msg = await message.answer("<b>Rasm tahlil qilinmoqda, biroz kuting...</b>")

    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        downloaded_file = await bot.download_file(file.file_path)
        image_bytes = downloaded_file.read()

        caption = message.caption or "Ushbu rasmdagi ma'lumotlarni to'liq tushuntirib ber."

        attempts = len(GEMINI_API_KEYS)
        reply_text = None
        used_key_num = 0
        last_error = ""

        for _ in range(attempts):
            try:
                gemini_client, used_key_num = get_next_gemini_client()
                
                prompt_content = [
                    genai_types.Part.from_bytes(
                        data=image_bytes,
                        mime_type='image/jpeg',
                    ),
                    (
                        f"Sizning ismingiz Sardorbek AI. Sizni {BOT_IDENTITY} yaratgan. "
                        "O'zingizni hech qachon ChatGPT yoki OpenAI deb atamang! "
                        "DIQQAT: Javoblaringizni formatlashda FAQAT HTML teglaridan foydalaning (masalan, qalin matn uchun <b>matn</b>, kodlar uchun <pre><code>...</code></pre>). "
                        "Aslo Markdown (**, *, `, ````) belgilarini ishlatmang! "
                        f"Foydalanuvchi so'rovi: {caption}"
                    )
                ]

                # Barqaror va xatosiz ishlaydigan gemini-1.5-flash modeli (qotmaydi)
                response = await asyncio.to_thread(
                    gemini_client.models.generate_content,
                    model='gemini-1.5-flash',
                    contents=prompt_content
                )
                reply_text = response.text.strip()
                break
            except Exception as e:
                last_error = str(e)
                logging.warning(f"Gemini kalit xatosi ({used_key_num}-kalit): {last_error}")
                continue

        if not reply_text:
            await bot.edit_message_text(f"Kechirasiz, xatolik yuz berdi: {last_error[:100]}", chat_id=message.chat.id, message_id=processing_msg.message_id)
            return

        for forbidden_word in ["ChatGPT", "chatgpt", "Chatgpt", "OpenAI", "openai", "GPT"]:
            reply_text = reply_text.replace(forbidden_word, "Sardorbek AI")

        await bot.edit_message_text(reply_text, chat_id=message.chat.id, message_id=processing_msg.message_id)

    except Exception as err:
        logging.error(f"Rasm qayta ishlashda xatolik: {str(err)}")
        await bot.edit_message_text("Kechirasiz, rasmni qayta ishlashda xatolik yuz berdi.", chat_id=message.chat.id, message_id=processing_msg.message_id)

# ==================== MATNLI XABARLAR (GROQ) ====================
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
            "Fizika, matematika yoki boshqa fanlardan formula yoki hisob-kitoblar so'ralganda, ularni albatta HTML kod tegi ichiga yozing: <pre><code>Sizning formulangiz</code></pre>. "
            "Qalin matnlar uchun <b>...</b> teglari ishlating. Aslo Markdown (**, *, `) ishlatmang! "
            "O'zbek tilida ravon javob bering."
        )
    }

    messages_payload = [system_prompt] + user_memory[user_id]
    attempts = len(API_KEYS) if API_KEYS else 1
    reply_text = None

    for _ in range(attempts):
        try:
            groq_client, used_key_num = get_next_groq_client()
            completion = await asyncio.to_thread(
                groq_client.chat.completions.create,
                model="openai/gpt-oss-120b",
                messages=messages_payload,
                temperature=0.6
            )
            reply_text = completion.choices[0].message.content.strip()
            break
        except Exception as e:
            logging.warning(f"Groq kalit xatosi: {str(e)}")
            continue

    if not reply_text:
        if user_memory[user_id]:
            user_memory[user_id].pop()
        await message.answer("Kechirasiz, barcha kalitlar vaqtincha band yoki xatolik yuz berdi.")
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
