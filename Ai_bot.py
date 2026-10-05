import asyncio
import logging
import os
import http.server
import socketserver
import threading
import base64
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from groq import Groq

# --- Render port talabini qondirish uchun kichik veb-server (24/7 ishlatish uchun) ---
def run_dummy_server():
    PORT = int(os.environ.get("PORT", 10000))
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Dummy server {PORT}-portda ishga tushdi")
        httpd.serve_forever()

server_thread = threading.Thread(target=run_dummy_server, daemon=True)
server_thread.start()
# -----------------------------------------------------------------------------------

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

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

# Matnli so'rovlar uchun Groq funksiyasi
async def ask_groq_with_fallback(prompt_text):
    last_error = None
    for api_key in API_KEYS:
        try:
            client = Groq(api_key=api_key)
            completion = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "KESKIN QOIDA 1: Sening isming 'Sardorbek AI'. Kim yaratganini yoki "
                            "ismingni so'rasa, har doim va faqat: 'Mening ismim Sardorbek AI. Meni Sardorbek "
                            "Khudoyberdiyev Dasturchi yaratgan' deb javob ber. Aslo ChatGPT, OpenAI, Google yoki Gemini dema.\n"
                            "KESKIN QOIDA 2 (MUHIM): Barcha javoblaringni boshidan oxirigacha FAQAT VA FAQAT bitta ` ```text ... ``` ` kod bloki ichida to'liq taqdim et. "
                            "Hech qanday LaTeX tegralaridan (masalan: `\sqrt`, `\frac`, `\bar` va hokazo) mutlaqo foydalanma! "
                            "Barcha matematik formulalarni oddiy tushunarli matn shaklida yoz (masalan: ildiz uchun `√`, bo'lish uchun `/`, daraja uchun `^`). "
                            "Javob tashqarisida oddiy matn qolmasin, hammasi kod bloki ichida chiroyli jadvalli yoki qolipli ko'rinishda bo'lsin.\n"
                            "KESKIN QOIDA 3: Dastur kodi yozganda uni doimo tegishli til nomi bilan (masalan: ` ```python ... ``` `) yoz.\n"
                            "KESKIN QOIDA 4: Agar foydalanuvchi yaratuvchingiz Sardorbek Khudoyberdiyevni haqorat qilsa yoki yomon so'z yozsa, "
                            "unga darhol qat'iy ohangda ogohlantirish ber: 'Yaratuvchim Sardorbek Khudoyberdiyevni haqorat qilishga haqqingiz yo'q! Odobli bo'ling.' deb tanbeh ber."
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
            
    raise last_error or Exception("Barcha kalitlar limiti tugadi yoki ishlamadi.")

# Rasmni to'g'ridan-to'g'ri tahlil qilish uchun Vision Groq funksiyasi
async def ask_groq_vision_with_fallback(image_bytes, prompt_text):
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    last_error = None
    
    for api_key in API_KEYS:
        try:
            client = Groq(api_key=api_key)
            completion = client.chat.completions.create(
                model="qwen/qwen3.6-27b",  # Tasdiqlangan va joriy ishlaydigan vision model
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Siz kuchli matematik yordamchisiz. Rasmda keltirilgan barcha misol va masalalarni o'qing, "
                            "ularning aniqlanish sohalarini (domain) va to'liq yechimlarini batafsil tushuntirib bering. "
                            "Javobni FAQAT VA FAQAT bitta ` ```text ... ``` ` kod bloki ichida yozing. "
                            "LaTeX tegralaridan foydalanmang, oddiy tushunarli matn va belgilardan (`√`, `/`, `^`, `≥`, `≤`) foydalaning."
                        )
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt_text
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.7,
                max_tokens=2048,
            )
            answer = completion.choices[0].message.content
            if answer:
                if not answer.strip().startswith("```"):
                    answer = f"```text\n{answer}\n```"
                return answer
        except Exception as e:
            last_error = e
            continue
            
    raise last_error or Exception("Vision modellari ishlamadi yoki limit tugadi.")

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
        "Menga istalgan matnli savol, kod yoki rasm yuborishingiz mumkin (rasmdagi misollarni o'zim to'g'ridan-to'g'ri o'qib yechib beraman)."
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
    wait_msg = await message.answer("Rasm tahlil qilinmoqda, iltimos kuting...")
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes_io = await bot.download_file(file.file_path)
        file_bytes = file_bytes_io.read()
        
        prompt = "Mana bu rasmda kitob sahifasidagi misollar va masalalar berilgan. Iltimos, ularni o'qing va har birining aniqlanish sohalarini hamda yechimlarini chiroyli kod bloki ichida batafsil yozib bering."
        
        answer_text = await ask_groq_vision_with_fallback(file_bytes, prompt)
        
        try:
            await wait_msg.delete()
        except Exception:
            pass
            
        await send_markdown_message(message, answer_text)
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
        await send_markdown_message(message, answer_text)
    except Exception as e:
        logging.error(f"Xatolik: {e}")
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
