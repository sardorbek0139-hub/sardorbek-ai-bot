import asyncio
import logging
import os
import http.server
import socketserver
import threading
import aiohttp
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

# Foydalanuvchilarni users.txt fayliga saqlash funksiyasi
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

# Token va kalitlarni serverning o'zidan o'qiymiz
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEYS_ENV = os.getenv("API_KEYS", "")
API_KEYS = [k.strip() for k in API_KEYS_ENV.split(",") if k.strip()]

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

# Matnli xabarlar uchun Groq funksiyasi
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

# Rasmdagi matnni avtomatik o'qib beruvchi funksiya (OCR)
async def extract_text_from_image(file_bytes):
    try:
        url = "https://api.ocr.space/parse/image"
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field('apikey', 'K81459419388957')  # Bepul ochiq OCR kalit
            form.add_field('file', file_bytes, filename='image.jpg', content_type='image/jpeg')
            form.add_field('language', 'eng')  # Inglizcha/Matematik belgilar uchun
            
            async with session.post(url, data=form) as response:
                result = await response.json()
                if result.get("ParsedResults"):
                    extracted_text = result["ParsedResults"][0].get("ParsedText", "")
                    return extracted_text.strip()
    except Exception as e:
        print(f"OCR xatoligi: {e}")
    return ""

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
    save_user(message.from_user.id)
    await message.answer(
        "Assalomu alaykum! Mening ismim Sardorbek AI. Meni Sardorbek Khudoyberdiyev Dasturchi yaratgan. "
        "Menga istalgan matnli savol, kod yoki **rasm** yuborishingiz mumkin (rasmdagi misollarni avtomatik o'qib yechib beraman)."
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
                f"👥 Jami foydalanuvchilar: <b>{total_users}</b> ta\n\n"
                f"Oxirgi foydalanuvchi ID lari:\n<code>{users_list}</code>",
                parse_mode="HTML"
            )
        else:
            await message.answer("📊 Hozircha foydalanuvchilar yo'q yoki fayl yaratilmadi.")
    except Exception as e:
        await message.answer(f"Xatolik: {e}")

# Rasm yuborilganda uni avtomatik matnga o'tkazib ishlaydigan qism
@dp.message(F.photo)
async def photo_handler(message: types.Message):
    save_user(message.from_user.id)
    wait_msg = await message.answer("🔍 Rasmdagi matn va misollarni o'qib chiqyapman...")
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes_io = await bot.download_file(file.file_path)
        file_bytes = file_bytes_io.read()
        
        # Rasmdan matnni ajratib olamiz
        img_text = await extract_text_from_image(file_bytes)
        
        if not img_text or len(img_text) < 3:
            await wait_msg.edit_text("❌ Rasmdan matn topib bo'lmadi. Iltimos, matnliroq yoki aniqroq rasm yuboring.")
            return
        
        await wait_msg.edit_text(f"📝 **Topilgan matn:**\n<code>{img_text}</code>\n\n⏳ Endi buni yechib beraman...", parse_mode="HTML")
        
        # Topilgan matnni AI ga uzatamiz
        prompt = f"Mana bu rasmdan o'qib olingan shart va misollar:\n{image_caption := message.caption or ''}\n{img_text}\n\nIltimos, buni to'liq tushuntirib va qoidaga amal qilgan holda yechib ber."
        answer_text = await ask_groq_with_fallback(prompt)
        
        try:
            await wait_msg.delete()
        except Exception:
            pass
            
        await send_long_message(message, answer_text)
    except Exception as e:
        logging.error(f"Rasm avto-tex xatoligi: {e}")
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await message.answer(f"Xatolik yuz berdi: {str(e)}")

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
