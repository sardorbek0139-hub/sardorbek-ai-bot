import asyncio
import logging
import os
import http.server
import socketserver
import threading
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from groq import Groq
from google import genai
from google.genai import types as genai_types

def run_dummy_server():
    PORT = int(os.environ.get("PORT", 10000))
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Dummy server {PORT}-portda ishga tushdi")
        httpd.serve_forever()

server_thread = threading.Thread(target=run_dummy_server, daemon=True)
server_thread.start()

def save_user(user_id):
    try:
        users = []
        if os.path.exists("users.txt"):
            with open("users.txt", "r") as f:
                users = f.read().splitlines()
        if str(user_id) not in users:
            with open("users.txt", "a") as f:
                f.write(f"{user_id}\n")
    except Exception as e:
        print(f"Foydalanuvchini saqlashda xatolik: {e}")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Matn uchun Groq kalitlari (Render Environment variables dan o'qiydi)
API_KEYS_ENV = os.getenv("API_KEYS", "")
API_KEYS = [k.strip() for k in API_KEYS_ENV.split(",") if k.strip()]

# Rasm uchun Gemini kalitlari (Render Environment variables dan o'qiydi)
GEMINI_KEYS_ENV = os.getenv("GEMINI_API_KEYS", "")
GEMINI_KEYS = [k.strip() for k in GEMINI_KEYS_ENV.split(",") if k.strip()]

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

# 1. MATN UCHUN GROQ FUNKSIYASI
async def ask_groq(prompt_text):
    last_error = None
    for api_key in API_KEYS:
        try:
            client = Groq(api_key=api_key)
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "KESKIN QOIDA 1: Sening isming 'Sardorbek AI'. Kim yaratganini yoki "
                            "ismingni so'rasa, har doim va faqat: 'Mening ismim Sardorbek AI. Meni Sardorbek "
                            "Khudoyberdiyev Dasturchi yaratgan' deb javob ber. Aslo ChatGPT, OpenAI, Google yoki Gemini dema.\n"
                            "KESKIN QOIDA 2 (MUHIM): Barcha javoblaringni va yechimlaringni "
                            "to'liqligicha bir yoki bir nechta ` ```text ... ``` ` kod bloki ichida taqdim et. "
                            "Hech qanday LaTeX tegralaridan (masalan: `\sqrt`, `\frac`, `\bar`) foydalanma! "
                            "Barcha matematik formulalarni oddiy tushunarli matn va belgilar shaklida yoz (masalan: ildiz uchun `√`, bo'lish uchun `/`, daraja uchun `^`, katta yoki teng `≥`)."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt_text
                    }
                ],
                temperature=0.7,
            )
            answer = completion.choices[0].message.content
            if answer:
                if not answer.strip().startswith("```"):
                    answer = f"```text\n{answer}\n```"
                return answer
        except Exception as e:
            last_error = e
            continue
    raise last_error or Exception("Groq kalitlari ishlamadi.")

# 2. RASM UCHUN GEMINI FUNKSIYASI (Fallback bilan)
async def ask_gemini_vision(prompt_text, image_bytes):
    if not GEMINI_KEYS:
        raise Exception("GEMINI_API_KEYS topilmadi! Render environment variables ga qo'shing.")
    
    last_error = None
    for gemini_key in GEMINI_KEYS:
        try:
            client = genai.Client(api_key=gemini_key)
            
            system_instruction = (
                "Sening isming 'Sardorbek AI'. Kim yaratganini yoki ismingni so'rasa, har doim va faqat: "
                "'Mening ismim Sardorbek AI. Meni Sardorbek Khudoyberdiyev Dasturchi yaratgan' deb javob ber. "
                "Barcha javoblaringni va yechimlaringni to'liqligicha bir yoki bir nechta ` ```text ... ``` ` kod bloki ichida taqdim et. "
                "Hech qanday LaTeX tegralaridan (masalan: `\sqrt`, `\frac`, `\bar`) foydalanma! "
                "Barcha matematik formulalarni oddiy tushunarli matn va belgilar shaklida yoz (masalan: ildiz uchun `√`, bo'lish uchun `/`, daraja uchun `^`, katta yoki teng `≥`)."
            )
            
            full_prompt = f"{system_instruction}\n\nFoydalanuvchi yuborgan rasm bo'yicha ko'rsatma: {prompt_text}"
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    genai_types.Part.from_bytes(
                        data=image_bytes,
                        mime_type='image/jpeg',
                    ),
                    full_prompt
                ]
            )
            
            answer = response.text
            if answer:
                if not answer.strip().startswith("```"):
                    answer = f"```text\n{answer}\n```"
                return answer
        except Exception as e:
            last_error = e
            continue
            
    raise last_error or Exception("Barcha Gemini kalitlari limiti tugadi yoki ishlamadi.")

async def send_markdown_message(message: types.Message, text: str):
    max_length = 4000
    for i in range(0, len(text), max_length):
        chunk = text[i:i + max_length]
        try:
            await message.answer(chunk, parse_mode="Markdown")
        except Exception:
            await message.answer(chunk)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    save_user(message.from_user.id)
    await message.answer(
        "Assalomu alaykum! Mening ismim Sardorbek AI. Meni Sardorbek Khudoyberdiyev Dasturchi yaratgan. "
        "Menga istalgan matnli savol, kod yoki rasm yuborishingiz mumkin (rasmdagi misollarni o'zim ko'rib yechib beraman)."
    )

@dp.message(Command("stats"))
async def stats_handler(message: types.Message):
    try:
        if os.path.exists("users.txt"):
            with open("users.txt", "r") as f:
                users = f.read().splitlines()
            total_users = len(users)
            users_list = "\n".join(users[-20:])
            await message.answer(
                f"Bot statistikasi:\n\n"
                f"Jami foydalanuvchilar: {total_users} ta\n\n"
                f"Oxirgi foydalanuvchi ID lari:\n{users_list}"
            )
        else:
            await message.answer("Hozircha foydalanuvchilar yo'q.")
    except Exception as e:
        await message.answer(f"Xatolik: {e}")

# Rasmlar uchun handler (Faqat GEMINI ishlaydi)
@dp.message(F.photo)
async def photo_handler(message: types.Message):
    save_user(message.from_user.id)
    wait_msg = await message.answer("Rasm Gemini orqali tahlil qilinmoqda...")
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes_io = await bot.download_file(file.file_path)
        file_bytes = file_bytes_io.read()
        
        prompt = "Ushbu rasmda ko'rsatilgan barcha matematik misollar va masalalarni o'qib, ularning har birining aniqlanish sohalarini (domain) va batafsil yechimlarini tushunarli matn va belgilar (√, /, ^) yordamida chiroyli qilib yozib bering."
        
        answer_text = await ask_gemini_vision(prompt, file_bytes)
        
        try:
            await wait_msg.delete()
        except Exception:
            pass
            
        await send_markdown_message(message, answer_text)
    except Exception as e:
        logging.error(f"Gemini rasm xatoligi: {e}")
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await message.answer(f"Xatolik yuz berdi: {str(e)}")

# Matnlar uchun handler (Faqat GROQ ishlaydi)
@dp.message(F.text & ~F.text.startswith("/"))
async def answer_question(message: types.Message):
    save_user(message.from_user.id)
    wait_msg = await message.answer("O'ylayapman...")
    try:
        answer_text = await ask_groq(message.text.strip())
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await send_markdown_message(message, answer_text)
    except Exception as e:
        logging.error(f"Groq xatoligi: {e}")
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await message.answer(f"Xatolik yuz berdi: {str(e)}")

async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
