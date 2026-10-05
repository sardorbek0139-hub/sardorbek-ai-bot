import asyncio
import logging
import os
import http.server
import socketserver
import threading
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
import aiohttp
from groq import Groq

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
API_KEYS_ENV = os.getenv("API_KEYS", "")
API_KEYS = [k.strip() for k in API_KEYS_ENV.split(",") if k.strip()]
OCR_API_KEY = os.getenv("OCR_API_KEY", "KXYZ...")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

async def extract_text_from_image(file_bytes):
    url = "https://api.ocr.space/parse/image"
    async with aiohttp.ClientSession() as session:
        form = aiohttp.FormData()
        form.add_field('apikey', OCR_API_KEY)
        form.add_field('file', file_bytes, filename='image.jpg', content_type='image/jpeg')
        form.add_field('language', 'eng')
        
        try:
            async with session.post(url, data=form) as response:
                result = await response.json()
                if result.get("ParsedResults"):
                    extracted_text = result["ParsedResults"][0].get("ParsedText", "")
                    return extracted_text.strip()
        except Exception as e:
            print(f"OCR xatoligi: {e}")
        return ""

async def ask_groq_with_fallback(prompt_text):
    if not API_KEYS:
        raise Exception("Groq API kalitlari topilmadi!")
    
    last_error = None
    for api_key in API_KEYS:
        try:
            client = Groq(api_key=api_key)
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",  # Hamma kalitda ishlaydigan tezkor va barqaror model
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Sening isming 'Sardorbek AI'. Kim yaratganini yoki ismingni so'rasa, "
                            "har doim va faqat: 'Mening ismim Sardorbek AI. Meni Sardorbek Khudoyberdiyev Dasturchi yaratgan' deb javob ber. "
                            "Barcha javoblaringni oddiy tushunarli matn va belgilar shaklida yoz."
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
    raise last_error or Exception("Groq kalitlari ishlamadi.")

async def send_safe_message(message: types.Message, text: str):
    max_length = 4000
    for i in range(0, len(text), max_length):
        chunk = text[i:i + max_length]
        try:
            await message.answer(chunk)
        except Exception:
            await message.answer(chunk.replace("<", "&lt;").replace(">", "&gt;"))

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    save_user(message.from_user.id)
    await message.answer(
        "Assalomu alaykum! Mening ismim Sardorbek AI. Meni Sardorbek Khudoyberdiyev Dasturchi yaratgan. "
        "Menga istalgan matnli savol, kod yoki rasm yuborishingiz mumkin."
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

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    save_user(message.from_user.id)
    wait_msg = await message.answer("Rasmdagi matn va misollarni o'qib chiqyapman...")
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes_io = await bot.download_file(file.file_path)
        file_bytes = file_bytes_io.read()
        
        img_text = await extract_text_from_image(file_bytes)
        
        if not img_text or len(img_text) < 3:
            await wait_msg.edit_text("Rasmdan matn topib bo'lmadi. Iltimos, aniqroq rasm yuboring.")
            return
        
        await wait_msg.edit_text("Matn o'qildi. Endi buni yechib beraman...")
        
        prompt = f"Mana bu rasmda quyidagi misollar yozilgan:\n{img_text}\n\nIltimos, bularning aniqlanish sohalarini va yechimlarini to'liq va tushunarli qilib yozib ber."
        answer_text = await ask_groq_with_fallback(prompt)
        
        try:
            await wait_msg.delete()
        except Exception:
            pass
            
        await send_safe_message(message, answer_text)
    except Exception as e:
        logging.error(f"Rasm xatoligi: {e}")
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await message.answer(f"Xatolik yuz berdi: {str(e)}")

@dp.message(F.text & ~F.text.startswith("/"))
async def answer_question(message: types.Message):
    save_user(message.from_user.id)
    wait_msg = await message.answer("O'ylayapman...")
    try:
        answer_text = await ask_groq_with_fallback(message.text.strip())
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await send_safe_message(message, answer_text)
    except Exception as e:
        logging.error(f"Xatolik: {e}")
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await message.answer(f"Xatolik yuz berdi: {str(e)}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
