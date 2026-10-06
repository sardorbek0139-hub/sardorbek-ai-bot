import asyncio
import logging
import os
import http.server
import socketserver
import threading
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
import google.generativeai as genai
from groq import Groq

# Render uchun dummy server
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

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8605848716:AAEJO1uLAjZ0O9VNBSxhACBvqMarVPMTPWw")

# Gemini API kalitingiz (Rasmlar uchun)
GEMINI_API_KEYS = [
    "AIzaSySizningGeminiKalitingizShuYergaYoziladi"  # <-- O'zingizning haqiqiy Gemini kalitingizni yozing
]

# Groq API kalitlari (Matnli xabarlar uchun Render'dan o'qiydi)
groq_env = os.getenv("API_KEYS", "") 
GROQ_API_KEYS = [k.strip() for k in groq_env.split(",") if k.strip()]

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

# Umumiy qoidalar
SYSTEM_INSTRUCTION = (
    "Seni Sardorbek Khudoyberdiyev Dasturchi yaratgan. "
    "Kim yaratganini so'rasa har doim va faqat shuni ayt. "
    "Aslo LaTeX belgilaridan foydalanma (masalan, \$ yoki \text{...} kabi belgilarni ishlatma). "
    "Matematik ifodalar va javoblarni tushunarli matn yoki markdown formatida yoz. "
    "Dasturlash kodlari yoki javoblarni ```til ... ``` bloklariga olib yoz."
)

# 1. Matnlar uchun Groq funksiyasi (Model rasmda ko'rsatilganidek yangilandi)
async def ask_groq_with_fallback(prompt_text):
    if not GROQ_API_KEYS:
        raise Exception("Groq API_KEYS topilmadi!")
        
    last_error = None
    for i, api_key in enumerate(GROQ_API_KEYS):
        try:
            client = Groq(api_key=api_key)
            completion = client.chat.completions.create(
                model="openai/gpt-oss-120b",  # Rasmda ko'rsatilgan yangi model
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_INSTRUCTION
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
                return answer
        except Exception as e:
            last_error = e
            continue
            
    raise last_error or Exception("Barcha Groq kalitlar limiti tugadi yoki ishlamadi.")

# 2. Rasmlar uchun Gemini funksiyasi
async def ask_gemini_with_fallback(prompt_text, image_parts=None):
    if not GEMINI_API_KEYS:
        raise Exception("GEMINI_API_KEYS topilmadi!")
        
    last_error = None
    for i, api_key in enumerate(GEMINI_API_KEYS):
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name='gemini-1.5-flash',
                system_instruction=SYSTEM_INSTRUCTION
            )
            
            content_list = []
            if image_parts:
                content_list.append(image_parts)
            
            full_prompt = prompt_text if prompt_text else "Bu rasmdagi matnni, testni yoki matematik masalani o'qib, tushuntirib va to'liq yechib ber."
            content_list.append(full_prompt)
            
            response = model.generate_content(content_list)
            if response and response.text:
                return response.text
        except Exception as e:
            last_error = e
            logging.error(f"Gemini {i+1}-kalit xatosi: {e}")
            continue
            
    raise last_error or Exception("Barcha Gemini kalitlar limiti tugadi yoki ishlamadi.")

async def send_long_message(message: types.Message, text: str):
    max_length = 4000
    if len(text) <= max_length:
        await message.answer(text, parse_mode="Markdown")
        return
    
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
        "Assalomu alaykum! Meni Sardorbek Khudoyberdiyev Dasturchi yaratgan. "
        "Menga matnli savol, dasturlash kodi yoki rasm yuboring, tahlil qilib beraman."
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
                f"📊 **Bot statistikasi:**\n\n"
                f"Jami foydalanuvchilar: {total_users} ta\n\n"
                f"Oxirgi foydalanuvchilar ID lari:\n{users_list}"
            )
        else:
            await message.answer("Hozircha foydalanuvchilar yo'q.")
    except Exception as e:
        await message.answer(f"Xatolik: {e}")

# Rasmlar kelganda GEMINI ishlaydi
@dp.message(F.photo)
async def photo_handler(message: types.Message):
    save_user(message.from_user.id)
    wait_msg = await message.answer("⏳ Rasm tahlil qilinmoqda...")
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_path = file.file_path
        
        file_bytes_io = await bot.download_file(file_path)
        photo_bytes = file_bytes_io.read()
        
        image_part = {
            'mime_type': 'image/jpeg',
            'data': photo_bytes
        }
        
        caption = message.caption or ""
        answer_text = await ask_gemini_with_fallback(caption, image_parts=image_part)
        
        try:
            await wait_msg.delete()
        except Exception:
            pass
            
        await send_long_message(message, answer_text)
        
    except Exception as e:
        logging.error(f"Rasm xatosi: {e}")
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await message.answer(f"❌ Xatolik yuz berdi: {str(e)}")

# Matnli xabarlar kelganda GROQ ishlaydi
@dp.message(F.text & ~F.text.startswith("/"))
async def answer_question(message: types.Message):
    save_user(message.from_user.id)
    wait_msg = await message.answer("⏳ O'ylayapman...")
    answer_text = ""
    try:
        answer_text = await ask_groq_with_fallback(message.text.strip())
        
        try:
            await wait_msg.delete()
        except Exception:
            pass
            
        await send_long_message(message, answer_text)
        
    except Exception as e:
        logging.error(f"Xatolik tafsiloti: {e}")
        try:
            await wait_msg.delete()
        except Exception:
            pass
        try:
            if answer_text:
                await send_long_message(message, answer_text)
            else:
                await message.answer(f"❌ Xatolik yuz berdi: {str(e)}")
        except Exception:
            await message.answer("❌ Xatolik yuz berdi.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
