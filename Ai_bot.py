import asyncio
import logging
import os
import http.server
import socketserver
import threading
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from groq import Groq
import base64

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

TELEGRAM_TOKEN = "8605848716:AAEJO1uLAjZ0O9VNBSxhACBvqMarVPMTPWw"
API_KEYS = [
    "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",
    "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",
    "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"
]

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

# 1-QADAM: Rasmdagi matn va formulalarni o'qish (Vision model)
async def extract_text_from_image(image_bytes):
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    for api_key in API_KEYS:
        if not api_key:
            continue
        try:
            client = Groq(api_key=api_key)
            completion = client.chat.completions.create(
                model="llama-3.2-11b-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text", 
                                "text": "Bu rasmda matematik darslik sahifasi yoki misollar bor. Rasmdagi barcha matnlar, formulalar va misollarni aynan qanday yozilgan bo'lsa shunday matn (text) ko'rinishiga o'tkazib ber. Hech qanday yechim yozma, faqat matn va misollarni aniq ko'chirib ber."
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
                temperature=0.1,
                max_tokens=1024
            )
            extracted_text = completion.choices[0].message.content
            if extracted_text:
                return extracted_text.strip()
        except Exception as e:
            print(f"Matnga o'girish xatoligi: {e}")
            continue
    return ""

# 2-QADAM: Matnni yechish uchun to'g'ri Groq text modeli
async def ask_groq_with_fallback(prompt_text):
    last_error = None
    for api_key in API_KEYS:
        if not api_key:
            continue
        try:
            client = Groq(api_key=api_key)
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",  # Ishlaydigan haqiqiy model
                messages=[
                    {
                        "role": "system",
                        "content": "KESKIN QOIDA: Seni Sardorbek Khudoyberdiyev Dasturchi yaratgan. Kim yaratganini so'rasa har doim va faqat shu javobni ber. Aslo Google yoki Gemini dema."
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

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    save_user(message.from_user.id)
    await message.answer(
        "Assalomu alaykum! Meni Sardorbek Khudoyberdiyev Dasturchi yaratgan. "
        "Menga istalgan darslik yoki misol tushirilgan rasm yuboring: bot uni avval matnga o'girib, keyin yechib beradi!"
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
    wait_msg = await message.answer("🔍 Rasmdagi misollar matnga o'girilmoqda...")
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes_io = await bot.download_file(file.file_path)
        file_bytes = file_bytes_io.read()
        
        # 1-Bosqich: Rasmdan matn hosil qilish
        extracted_text = await extract_text_from_image(file_bytes)
        
        if not extracted_text or len(extracted_text) < 3:
            await wait_msg.edit_text("Rasmdan matn topib bo'lmadi. Iltimos, aniqroq rasm yuboring.")
            return
        
        await wait_msg.edit_text(f"📝 **Topilgan matn:**\n`{extracted_text}`\n\n⏳ Endi buni Groq'ga yuborib yechtirayapman...")
        
        # 2-Bosqich: Matnni Groq'ga berib yechim olish
        prompt = f"Quyida kitobdan olingan matn va misollar keltirilgan:\n\n{extracted_text}\n\nIltimos, mana shu misollarning yechimini batafsil va tushunarli qilib yozib ber."
        answer_text = await ask_groq_with_fallback(prompt)
        
        try:
            await wait_msg.delete()
        except Exception:
            pass
            
        await message.answer(answer_text)
    except Exception as e:
        logging.error(f"Xatolik: {e}")
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await message.answer(f"❌ Xatolik yuz berdi: {str(e)}")

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
        await message.answer(answer_text)
    except Exception as e:
        logging.error(f"Xatolik: {e}")
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await message.answer(f"❌ Xatolik yuz berdi: {str(e)}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
