import asyncio
import logging
import os
import http.server
import socketserver
import threading
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from groq import Groq

# Render uchun dummy server (port band bo'lib qolmasligi uchun)
def run_dummy_server():
    PORT = int(os.environ.get("PORT", 10000))
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Dummy server {PORT}-portda ishga tushdi")
        httpd.serve_forever()

server_thread = threading.Thread(target=run_dummy_server, daemon=True)
server_thread.start()

# Foydalanuvchilarni saqlash uchun funksiya
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

API_KEYS = [
    "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",
    "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",
    "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"
]

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

async def ask_groq_with_fallback(prompt_text):
    last_error = None
    for i, api_key in enumerate(API_KEYS):
        if not api_key:
            continue
        try:
            client = Groq(api_key=api_key)
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",  # Ishlayotgan to'g'ri model nomi
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "KESKIN QOIDA 1: Seni Sardorbek Khudoyberdiyev Dasturchi yaratgan. "
                            "Kim yaratganini so'rasa har doim va faqat shu javobni ber. Aslo Google yoki Gemini dema.\n"
                            "KESKIN QOIDA 2: Agar foydalanuvchi dasturlash kodi yoki shunga oid savol so'rasa, "
                            "javobdagi barcha kodlarni Telegram'da chiroyli ko'rinishi uchun alohida kod oynasiga "
                            "(markdown formatidagi ```til ... ``` bloklariga) olib yoz."
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
            print(f"Diqqat! {i+1}-kalit xato berdi: {e}")
            logging.warning(f"{i+1}-kalit xato berdi: {e}")
            continue
            
    raise last_error or Exception("Barcha kalitlar limiti tugadi yoki ishlamadi.")

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    save_user(message.from_user.id)
    await message.answer(
        "Assalomu alaykum! Meni Sardorbek Khudoyberdiyev Dasturchi yaratgan. "
        "Menga istalgan matnli savol yoki dasturlash kodi yuboring, yechib beraman."
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

@dp.message(F.text & ~F.text.startswith("/"))
async def answer_question(message: types.Message):
    save_user(message.from_user.id)
    wait_msg = await message.answer("⏳ O'ylayapman...")
    try:
        answer_text = await ask_groq_with_fallback(message.text.strip())
        
        try:
            await wait_msg.delete()
        except Exception:
            pass
            
        await message.answer(answer_text, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Xatolik tafsiloti: {e}")
        try:
            await wait_msg.delete()
        except Exception:
            pass
        # Agar markdown formatida xatolik chiqib qolsa, oddiy matn sifatida yuborish uchun guard
        try:
            await message.answer(answer_text)
        except Exception:
            await message.answer(f"❌ Xatolik yuz berdi: {str(e)}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
