import asyncio
import logging
import os
import http.server
import socketserver
import threading
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

# Token va kalitlarni serverning o'zidan o'qiymiz
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEYS_ENV = os.getenv("API_KEYS", "")
API_KEYS = [k.strip() for k in API_KEYS_ENV.split(",") if k.strip()]

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
                            "KESKIN QOIDA 1: Sening isming 'Sardorbek AI'. Kim yaratganini yoki "
                            "ismingni so'rasa, har doim va faqat: 'Mening ismim Sardorbek AI. Meni Sardorbek "
                            "Khudoyberdiyev Dasturchi yaratgan' deb javob ber. Aslo ChatGPT, OpenAI, Google yoki Gemini dema.\n"
                            "KESKIN QOIDA 2: Matematika, fizika, kimyo va boshqa barcha fanlarning formulalarini va hisob-kitoblarini yozganda, "
                            "ularni albatta ` ```text ... ``` ` kod bloki ichiga olib yoz. Aslo LaTeX tegralaridan foydalanma.\n"
                            "KESKIN QOIDA 3: Dastur kodi yozganda uni doimo ` ```til ... ``` ` bloklari ichiga olib yoz.\n"
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
                return answer
        except Exception as e:
            last_error = e
            continue
            
    raise last_error or Exception("Barcha kalitlar limiti tugadi yoki ishlamadi.")

async def send_long_message(message: types.Message, text: str):
    max_length = 4000
    lines = text.split('\n')
    current_chunk = ""
    in_code_block = False
    code_lang = ""

    for line in lines:
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            if in_code_block:
                code_lang = line.strip()
            else:
                code_lang = ""

        if len(current_chunk) + len(line) + 1 > max_length:
            if in_code_block:
                current_chunk += "\n```"
            await message.answer(current_chunk, parse_mode="Markdown")
            current_chunk = ""
            if in_code_block:
                current_chunk += f"{code_lang}\n"
        
        current_chunk += line + "\n"

    if current_chunk.strip():
        await message.answer(current_chunk, parse_mode="Markdown")

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "Assalomu alaykum! Mening ismim Sardorbek AI. Meni Sardorbek Khudoyberdiyev Dasturchi yaratgan. "
        "Menga istalgan matnli savol yoki dasturlash kodi yuboring, yechib beraman."
    )

@dp.message(F.text & ~F.text.startswith("/"))
async def answer_question(message: types.Message):
    wait_msg = await message.answer("⏳ O'ylayapman...")
    try:
        answer_text = await ask_groq_with_fallback(message.text.strip())
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await send_long_message(message, answer_text)
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
