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

# Xabarlarni xavfsiz yuborish (parse_mode xatolik chiqarmasligi uchun)
async def send_safe_message(message: types.Message, text: str):
    max_length = 4000
    for i in range(0, len(text), max_length):
        chunk = text[i:i + max_length]
        try:
            # Markdown yoki parse_mode ishlatmasdan oddiy matn sifatida yuboramiz (xatolik chiqmaydi)
            await message.answer(chunk)
        except Exception as e:
            # Agar oddiy matnda ham muammo bo'lsa, belgili qismlarini tozalab yuboramiz
            await message.answer(chunk.replace("<", "&lt;").replace(">", "&gt;"))

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    save_user(message.from_user.id)
    await message.answer(
        "Assalomu alaykum! Mening ismim Sardorbek AI. Meni Sardorbek Khudoyberdiyev Dasturchi yaratgan. "
        "Menga istalgan matnli savol, kod yoki rasm yuborishingiz mumkin (rasmdagi misollarni avtomatik o'qib yechib beraman)."
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

# Rasm yuborilganda ishlaydigan qism
@dp.message(F.photo)
async def photo_handler(message: types.Message):
    save_user(message.from_user.id)
    wait_msg = await message.answer("Rasmdagi matn va misollarni o'qib chiqyapman...")
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes_io = await bot.download_file(file.file_path)
        file_bytes = file_bytes_io.read()
        
        # Rasmdan matnni ajratib olamiz
        img_text = await extract_text_from_image(file_bytes)
        
        if not img_text or len(img_text) < 3:
            await wait_msg.edit_text("Rasmdan matn topib bo'lmadi. Iltimos, aniqroq rasm yuboring.")
            return
        
        await wait_msg.edit_text("Matn o'qildi. Endi buni yechib beraman...")
        
        # Topilgan matnni AI ga uzatamiz
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
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
