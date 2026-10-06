import asyncio
import logging
import os
import http.server
import socketserver
import threading
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from groq import Groq
import google.generativeai as genai

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

# Groq API kalitlari (Render'dan o'qiladi)
groq_env = os.getenv("API_KEYS", "")
API_KEYS = [k.strip() for k in groq_env.split(",") if k.strip()]

# Gemini API kalitlari Render'dan o'qiladi
gemini_env = os.getenv("GEMINI_API_KEYS", "")
GEMINI_API_KEYS = [k.strip() for k in gemini_env.split(",") if k.strip()]

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

async def ask_groq_with_fallback(prompt_text):
    last_error = None
    for i, api_key in enumerate(API_KEYS):
        try:
            client = Groq(api_key=api_key)
            completion = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "KESKIN QOIDA 1: Seni Sardorbek Khudoyberdiyev Dasturchi yaratgan. "
                            "Kim yaratganini so'rasa har doim va faqat shu javobni ber. Aslo Google yoki Gemini dema.\n"
                            "KESKIN QOIDA 2: Aslo LaTeX belgilaridan foydalanma!\n"
                            "KESKIN QOIDA 3: Dasturlash kodlari yoki javoblarni markdown formatidagi ```til ... ``` bloklariga olib yoz."
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
                return answer
        except Exception as e:
            last_error = e
            continue
            
    raise last_error or Exception("Barcha Groq kalitlar limiti tugadi yoki ishlamadi.")

async def analyze_image_with_gemini(photo_bytes, caption_text):
    last_error = None
    for i, api_key in enumerate(GEMINI_API_KEYS):
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = caption_text if caption_text else "Bu rasmdagi ma'lumotni, matnni yoki matematik masalani tushuntirib ber."
            
            image_part = {
                'mime_type': 'image/jpeg',
                'data': photo_bytes
            }
            
            response = model.generate_content([prompt, image_part])
            if response and response.text:
                return response.text
        except Exception as e:
            last_error = e
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
        
        caption = message.caption or ""
        answer_text = await analyze_image_with_gemini(photo_bytes, caption)
        
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
