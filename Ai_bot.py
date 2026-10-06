import os
import logging
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from groq import Groq

# ---------------- CONFIGURATION ----------------
TOKEN = os.getenv("TELEGRAM_TOKEN", "SIZNING_BOT_TOKENINGIZ")
GROQ_API_KEY = os.getenv("API_KEYS", "SIZNING_GROQ_API_KEY")
ADMIN_ID = 123456789  # O'zingizning Telegram ID raqamingiz

ADMIN_USERNAME_LINK = "https://t.me/@Sardorbek_Ai_admin"
BOT_IDENTITY = "Sardorbek Khudoyberdiyev Dasturchi"

user_memory = {}
vip_users = set()

bot = Bot(token=TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)

logging.basicConfig(level=logging.INFO)

def save_user(user_id):
    if user_id not in user_memory:
        user_memory[user_id] = []

# ---------------- COMMANDS ----------------
@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    save_user(user_id)
    user_memory[user_id].clear()
    
    await message.answer(
        f"Assalomu alaykum! Men — **{BOT_IDENTITY}** tomonidan yaratilgan sun'iy intellekt yordamchisiman.\n\n"
        "Menga istalgan mavzuda savol bering, suhbatni birgalikda qiziqarli davom ettiramiz!",
        parse_mode="Markdown"
    )

# ---------------- IMAGE COMMAND & VIP CHECK ----------------
@dp.message(Command("image"))
async def image_command(message: types.Message):
    user_id = message.from_user.id
    
    if user_id not in vip_users and user_id != ADMIN_ID:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 VIP huquqni olish", url=ADMIN_USERNAME_LINK)]
        ])
        await message.answer(
            "⚠️ **Rasm yaratish funksiyasi faqat VIP foydalanuvchilar uchun!**",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return

    await message.answer("🖼 Rasm yaratish so'rovi qabul qilindi.")

# ---------------- TEXT HANDLER WITH DYNAMIC CONTEXT ----------------
@dp.message(F.text)
async def text_handler(message: types.Message):
    user_id = message.from_user.id
    save_user(user_id)
    
    user_text = message.text
    user_memory[user_id].append({"role": "user", "content": user_text})
    
    if len(user_memory[user_id]) > 10:
        user_memory[user_id] = user_memory[user_id][-10:]

    try:
        # Sun'iy intellektga aniq qoida beramiz: javob oxirida JSON formatida 2 ta mos variant qaytarsin
        system_prompt = {
            "role": "system", 
            "content": (
                f"Sizning ismingiz: {BOT_IDENTITY}. O'zbek tilida muloqot qilasiz. "
                "Foydalanuvchining savoliga to'liq javob bergach, javobingiz oxirida shu mavzuni davom ettirish uchun "
                "2 ta qisqa va qiziqarli variant taklif qiling. "
                "Javobingizni quyidagi JSON formatda qaytaring (boshqa ortiqcha narsa yozmang, faqat shu formatda):\n"
                "{\n"
                "  \"text\": \"Asosiy javob matni bu yerda...\",\n"
                "  \"options\": [\"1-variant matni (masalan: G'azallarini yozaymi?)\", \"2-variant matni (masalan: Hayoti haqida aytaymi?)\"]\n"
                "}"
            )
        }

        messages_payload = [system_prompt] + user_memory[user_id]

        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages_payload,
            temperature=0.7
        )
        
        raw_response = completion.choices[0].message.content.strip()
        
        # JSON formatini tozalash (agar AI qo'shimcha belgi qo'shib yuborsa)
        if "```json" in raw_response:
            raw_response = raw_response.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_response:
            raw_response = raw_response.split("```")[1].split("```")[0].strip()

        parsed_data = json.loads(raw_response)
        reply_text = parsed_data.get("text", raw_response)
        options = parsed_data.get("options", [])

        user_memory[user_id].append({"role": "assistant", "content": reply_text})
        
        # Variantlar asosida dinamik tugmalar yasash
        keyboard_buttons = []
        for opt in options:
            keyboard_buttons.append([InlineKeyboardButton(text=opt, callback_data=f"opt_{opt[:20]}")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons) if keyboard_buttons else None
        
        await message.answer(reply_text, parse_mode="Markdown", reply_markup=keyboard)
        
    except Exception as e:
        logging.error(f"Xatolik yuz berdi: {e} | Javob: {locals().get('raw_response', '')}")
        # Agar JSON xatosi bo'lsa ham oddiy matn sifatida chiqarib yuborish uchun zaxira usul
        try:
            fallback_completion = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "system", "content": f"Siz {BOT_IDENTITY} siz. O'zbek tilida javob bering."}] + user_memory[user_id],
            )
            fallback_text = fallback_completion.choices[0].message.content
            await message.answer(fallback_text, parse_mode="Markdown")
        except Exception:
            await message.answer("Kechirasiz, so'rovni bajarishda xatolik yuz berdi. Qaytadan yozib ko'ring.")

# ---------------- CALLBACK QUERY HANDLER ----------------
@dp.callback_query(F.data.startswith("opt_"))
async def callback_handler(callback: types.CallbackQuery):
    # Tugma bosilganda foydalanuvchi tanlagan variantni go'yo o'zi yozgandek qabul qilib javob beramiz
    selected_option = callback.data[4:] # "opt_" prefiksini olib tashlaymiz
    await callback.message.answer(f"Tanlovingiz: *{selected_option}*", parse_mode="Markdown")
    await callback.answer()

# ---------------- MAIN ----------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
