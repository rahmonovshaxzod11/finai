import asyncio
import json
import os
import uuid
import aiohttp
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

# .env faylini yuklash
load_dotenv()

# Environment variables dan tokenni olish
API_TOKEN = os.getenv("API_TOKEN")
GIGA_TOKEN = os.getenv("GIGA_TOKEN")

# Tokenlarni tekshirish
if not API_TOKEN:
    raise ValueError("API_TOKEN .env faylda topilmadi!")
if not GIGA_TOKEN:
    raise ValueError("GIGA_TOKEN .env faylda topilmadi!")

print("✅ Tokenlar muvaffaqiyatli yuklandi!")

# JSON fayl nomi
USER_DATA_FILE = "user_data.json"
PREMIUM_DATA_FILE = "premium_data.json"

# User ma'lumotlarini saqlash uchun lug'at
user_data = {}
premium_data = {}

# To'lov ma'lumotlari
PREMIUM_PRICE = 1000  # 1000 so'm

# Majburiy kanallar
REQUIRED_CHANNELS = [
    ("1-kanal", "https://t.me/aaadhhaha1")
]


class ProfileForm(StatesGroup):
    age = State()
    job = State()
    income = State()
    interest = State()
    business = State()


class PaymentForm(StatesGroup):
    waiting_phone = State()


bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# JSON fayldan ma'lumotlarni o'qish
def load_user_data():
    global user_data, premium_data
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                user_data = json.load(f)
        except Exception as e:
            print(f"Faylni o'qishda xatolik: {e}")
            user_data = {}
    
    if os.path.exists(PREMIUM_DATA_FILE):
        try:
            with open(PREMIUM_DATA_FILE, 'r', encoding='utf-8') as f:
                premium_data = json.load(f)
        except Exception as e:
            print(f"Premium faylni o'qishda xatolik: {e}")
            premium_data = {}


# JSON faylga ma'lumotlarni yozish
def save_user_data():
    try:
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Faylga yozishda xatolik: {e}")


def save_premium_data():
    try:
        with open(PREMIUM_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(premium_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Premium faylga yozishda xatolik: {e}")


# Premium obuna tekshirish
def is_premium(user_id: str) -> bool:
    if user_id in premium_data:
        expiry_date = datetime.fromisoformat(premium_data[user_id]['expiry_date'])
        return datetime.now() < expiry_date
    return False


# Premium obuna muddatini qo'shish
def add_premium(user_id: str, days: int = 30):
    expiry_date = datetime.now() + timedelta(days=days)
    premium_data[user_id] = {
        'purchase_date': datetime.now().isoformat(),
        'expiry_date': expiry_date.isoformat(),
        'active': True
    }
    save_premium_data()


# Gigachat API bilan ishlash (requests orqali)
async def ask_gigachat(user_id: str, user_question: str) -> str:
    try:
        # User ma'lumotlarini olish
        if user_id in user_data:
            user_info = user_data[user_id]
            user_context = f"Yosh: {user_info[0]}, Kasb: {user_info[1]}, Daromad: {user_info[2]}, Qiziqishlar: {user_info[3]}, Biznes: {user_info[4]}"
        else:
            user_context = "Foydalanuvchi ma'lumotlari topilmadi"

        # To'liq prompt tayyorlash
        full_prompt = f"""
        Siz moliyaviy maslahatchi AI siz. 
        Foydalanuvchi ma'lumotlari: {user_context}
        
        Foydalanuvchi savoli: {user_question}
        
        Iltimos, quyidagilarga e'tibor bering:
        - Aniq va amaliy maslahatlar bering
        - Moliyaviy jihatdan xavfsiz tavsiyalar
        - O'zbekiston bozoriga moslashtirilgan
        - Batafsil va tushunarli javob
        - Maxfiylikni saqlang
        """

        # Gigachat API ga so'rov
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {GIGA_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "GigaChat",
            "messages": [
                {
                    "role": "user",
                    "content": full_prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 1000
        }

        # Sync request ni async ga o'girish
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: requests.post(url, json=payload, headers=headers, verify=False)
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            return f"❌ API xatosi: {response.status_code}. Iltimos, keyinroq urinib ko'ring."

    except Exception as e:
        return f"❌ Xatolik yuz berdi: {str(e)}. Iltimos, keyinroq urinib ko'ring."


# Kanalga a'zolikni tekshirish
async def check_subscription(user_id: int) -> bool:
    for name, link in REQUIRED_CHANNELS:
        try:
            username = link.split("/")[-1]
            if not username.startswith("@"):
                username = "@" + username

            member = await bot.get_chat_member(chat_id=username, user_id=user_id)
            if member.status not in ("member", "administrator", "creator"):
                return False
        except Exception as e:
            print(f"Kanal tekshirishda xatolik: {e}")
            return False
    return True


# A'zo bo'lish uchun klaviatura
def subscription_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, url=link)]
            for name, link in REQUIRED_CHANNELS
        ] + [
            [InlineKeyboardButton(text="🔄 Tekshirish", callback_data="check_sub")]
        ]
    )


# Asosiy menyu
def main_menu(user_id: str):
    premium_status = "✅ PREMIUM" if is_premium(user_id) else "❌ Oddiy"
    
    buttons = [
        [InlineKeyboardButton(text="🤖 Moliyachi AI bilan maslahat", callback_data="ai_consultation")],
        [InlineKeyboardButton(text="👤 Mening profilim", callback_data="show_profile")],
        [InlineKeyboardButton(text=f"💎 Premium obuna - {premium_status}", callback_data="premium_info")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Premium obuna klaviaturasi
def premium_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 To'lov qilish (1000 so'm)", callback_data="make_payment")],
            [InlineKeyboardButton(text="📋 Premium afzalliklari", callback_data="premium_benefits")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")],
        ]
    )


# To'lov klaviaturasi
def payment_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Karta raqamini ko'rsatish", callback_data="show_card")],
            [InlineKeyboardButton(text="📸 Screenshot yuborish", callback_data="send_screenshot")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="premium_info")],
        ]
    )


@dp.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)

    # Kanalga a'zolikni tekshirish
    subscribed = await check_subscription(message.from_user.id)

    if not subscribed:
        await message.answer(
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇",
            reply_markup=subscription_keyboard()
        )
        return

    # Agar user allaqachon mavjud bo'lsa, menyuni ko'rsat
    if user_id in user_data:
        await message.answer(
            "🎉 Obuna tasdiqlandi! Quyidagi menyudan birini tanlang:",
            reply_markup=main_menu(user_id)
        )
        return

    # Yangi user uchun profil to'ldirishni boshlash
    await message.answer("🎉 Obuna tasdiqlandi! Profilingizni to'ldirishni boshlaymiz.")
    await message.answer("Yoshingizni kiriting:")
    await state.set_state(ProfileForm.age)


@dp.callback_query(F.data == "check_sub")
async def check_subscription_callback(call: CallbackQuery, state: FSMContext):
    subscribed = await check_subscription(call.from_user.id)

    if not subscribed:
        await call.answer("🚫 Hali obuna bo'lmadingiz. Iltimos, kanallarga obuna bo'ling.", show_alert=True)
        await call.message.answer(
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇",
            reply_markup=subscription_keyboard()
        )
    else:
        user_id = str(call.from_user.id)

        # Agar user allaqachon mavjud bo'lsa, menyuni ko'rsat
        if user_id in user_data:
            await call.message.edit_text(
                "🎉 Obuna tasdiqlandi! Quyidagi menyudan birini tanlang:"
            )
            await call.message.answer(
                "Menyu:",
                reply_markup=main_menu(user_id)
            )
        else:
            # Yangi user uchun profil to'ldirishni boshlash
            await call.message.edit_text("🎉 Obuna tasdiqlandi! Profilingizni to'ldirishni boshlaymiz.")
            await call.message.answer("Yoshingizni kiriting:")
            await state.set_state(ProfileForm.age)

    await call.answer()


# ... (Profil to'ldirish funksiyalari o'zgarmaydi) ...

@dp.message(ProfileForm.age)
async def set_age(message: Message, state: FSMContext):
    # Kanalga a'zolikni tekshirish
    subscribed = await check_subscription(message.from_user.id)
    if not subscribed:
        await message.answer(
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇",
            reply_markup=subscription_keyboard()
        )
        return

    user_id = str(message.from_user.id)

    # Ma'lumotlarni saqlash
    if user_id not in user_data:
        user_data[user_id] = []

    await state.update_data(age=message.text)
    await state.set_state(ProfileForm.job)
    await message.answer("Kasbingiz yoki o'qishingiz?")


@dp.message(ProfileForm.job)
async def set_job(message: Message, state: FSMContext):
    # Kanalga a'zolikni tekshirish
    subscribed = await check_subscription(message.from_user.id)
    if not subscribed:
        await message.answer(
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇",
            reply_markup=subscription_keyboard()
        )
        return

    await state.update_data(job=message.text)
    await state.set_state(ProfileForm.income)
    await message.answer("Oylik daromadingiz qancha?")


@dp.message(ProfileForm.income)
async def set_income(message: Message, state: FSMContext):
    # Kanalga a'zolikni tekshirish
    subscribed = await check_subscription(message.from_user.id)
    if not subscribed:
        await message.answer(
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇",
            reply_markup=subscription_keyboard()
        )
        return

    await state.update_data(income=message.text)
    await state.set_state(ProfileForm.interest)
    await message.answer("Qiziqishlaringiz?")


@dp.message(ProfileForm.interest)
async def set_interest(message: Message, state: FSMContext):
    # Kanalga a'zolikni tekshirish
    subscribed = await check_subscription(message.from_user.id)
    if not subscribed:
        await message.answer(
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇",
            reply_markup=subscription_keyboard()
        )
        return

    await state.update_data(interest=message.text)
    await state.set_state(ProfileForm.business)
    await message.answer("Hozir biznesingiz bormi? (ha/yo'q)")


@dp.message(ProfileForm.business)
async def finish_profile(message: Message, state: FSMContext):
    # Kanalga a'zolikni tekshirish
    subscribed = await check_subscription(message.from_user.id)
    if not subscribed:
        await message.answer(
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇",
            reply_markup=subscription_keyboard()
        )
        return

    user_id = str(message.from_user.id)

    # So'nggi ma'lumotni saqlash
    await state.update_data(business=message.text)
    data = await state.get_data()

    # Lug'atga qo'shish
    user_data[user_id] = [
        data.get('age', ''),
        data.get('job', ''),
        data.get('income', ''),
        data.get('interest', ''),
        data.get('business', '')
    ]

    # JSON faylga saqlash
    save_user_data()

    msg = (
        "📋 Profil saqlandi!\n\n"
        f"Yosh: {data.get('age')}\n"
        f"Kasb: {data.get('job')}\n"
        f"Daromad: {data.get('income')}\n"
        f"Qiziqishlar: {data.get('interest')}\n"
        f"Biznes bor: {data.get('business')}"
    )

    await message.answer(msg)
    await message.answer(
        "Quyidagi menyudan birini tanlang:",
        reply_markup=main_menu(user_id)
    )
    await state.clear()


# Premium obuna callback'lari
@dp.callback_query(F.data == "premium_info")
async def premium_info(call: CallbackQuery):
    user_id = str(call.from_user.id)
    
    if is_premium(user_id):
        expiry_date = datetime.fromisoformat(premium_data[user_id]['expiry_date'])
        days_left = (expiry_date - datetime.now()).days
        
        message_text = (
            f"💎 Sizda PREMIUM obuna mavjud!\n\n"
            f"⏳ Muddat: {days_left} kun qoldi\n"
            f"📅 Tugash sanasi: {expiry_date.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Premium afzalliklari:\n"
            f"• Cheksiz AI maslahatlari\n"
            f"• Yuqori sifatli javoblar\n"
            f"• Birinchi navbatda xizmat\n"
            f"• Maxsus kontent"
        )
    else:
        message_text = (
            f"💎 PREMIUM OBUNA\n\n"
            f"💰 Narxi: {PREMIUM_PRICE} so'm\n"
            f"⏳ Muddat: 30 kun\n\n"
            f"Premium afzalliklari:\n"
            f"• Cheksiz AI maslahatlari\n"
            f"• Yuqori sifatli javoblar\n"
            f"• Birinchi navbatda xizmat\n"
            f"• Maxsus kontent\n\n"
            f"To'lov qilish uchun quyidagi tugmani bosing 👇"
        )
    
    await call.message.edit_text(message_text)
    await call.message.edit_reply_markup(reply_markup=premium_keyboard())
    await call.answer()


@dp.callback_query(F.data == "premium_benefits")
async def premium_benefits(call: CallbackQuery):
    benefits_text = (
        "💎 PREMIUM AFZALLIKLARI:\n\n"
        "🤖 Cheksiz AI maslahatlari\n"
        "✅ Yuqori sifatli batafsil javoblar\n"
        "⚡ Birinchi navbatda xizmat\n"
        "🎯 Shaxsiylashtirilgan kontent\n"
        "📊 Moliyaviy tahlillar\n"
        "💼 Biznes maslahatlari\n"
        "🔔 Yangiliklar birinchi bo'lib\n"
        "🎁 Maxsus takliflar\n\n"
        f"💰 Faqat {PREMIUM_PRICE} so'm - 30 kun"
    )
    
    await call.message.edit_text(benefits_text)
    await call.message.edit_reply_markup(reply_markup=premium_keyboard())
    await call.answer()


@dp.callback_query(F.data == "make_payment")
async def make_payment(call: CallbackQuery):
    payment_instructions = (
        f"💳 PREMIUM OBUNA TO'LOVI\n\n"
        f"💰 Summa: {PREMIUM_PRICE} so'm\n\n"
        f"To'lov qilish tartibi:\n"
        f"1. Karta raqamini olish uchun '💳 Karta raqamini ko'rsatish' tugmasini bosing\n"
        f"2. Karta raqamiga {PREMIUM_PRICE} so'm o'tkazing\n"
        f"3. To'lov chekini (screenshot) yuboring\n"
        f"4. Tekshiruvdan so'ng premium faollashtiriladi"
    )
    
    await call.message.edit_text(payment_instructions)
    await call.message.edit_reply_markup(reply_markup=payment_keyboard())
    await call.answer()


@dp.callback_query(F.data == "show_card")
async def show_card(call: CallbackQuery):
    card_info = (
        f"💳 TO'LOV QILISH UCHUN:\n\n"
        f"Karta raqami: `8600 4901 2345 6789`\n"
        f"Summa: {PREMIUM_PRICE} so'm\n"
        f"Karta egasi: [Ismingiz]\n\n"
        f"💡 Eslatma:\n"
        f"• To'lov qilgach, chek screenshotini yuboring\n"
        f"• To'lov tekshirilgach, premium faollashtiriladi\n"
        f"• Muammo bo'lsa, administrator bilan bog'laning"
    )
    
    await call.message.edit_text(card_info)
    await call.message.edit_reply_markup(reply_markup=payment_keyboard())
    await call.answer()


@dp.callback_query(F.data == "send_screenshot")
async def send_screenshot(call: CallbackQuery, state: FSMContext):
    await call.message.answer(
        "📸 Iltimos, to'lov chekini (screenshot) yuboring:\n\n"
        "Yuborish kerak:\n"
        "• To'lov muvaffaqiyatli amalga oshirilganligi\n"
        "• Karta raqami ko'rinishi\n"
        "• Summa ko'rinishi\n"
        "• Vaqt ko'rinishi"
    )
    await state.set_state(PaymentForm.waiting_phone)  # Nomini o'zgartirdik
    await call.answer()


@dp.message(PaymentForm.waiting_phone)
async def process_screenshot(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    
    # Screenshot yuborilganini tekshirish
    if message.photo or message.document:
        # Demo uchun avtomatik tasdiqlaymiz
        # Haqiqiy loyihada bu yerda to'lovni tekshirish kerak
        
        add_premium(user_id)
        
        await message.answer(
            "✅ To'lov muvaffaqiyatli tasdiqlandi!\n\n"
            "💎 Siz endi PREMIUM foydalanuvchisiz!\n"
            "⏳ Premium obuna: 30 kun\n\n"
            "Endi barcha funksiyalardan cheksiz foydalanishingiz mumkin!"
        )
        
        # Asosiy menyuga qaytish
        await message.answer(
            "Asosiy menyu:",
            reply_markup=main_menu(user_id)
        )
        
    else:
        await message.answer(
            "❌ Iltimos, to'lov chekining screenshotini yuboring!\n"
            "Rasm yoki fayl shaklida yuboring."
        )
        return
    
    await state.clear()


@dp.callback_query(F.data == "main_menu")
async def back_to_main(call: CallbackQuery):
    user_id = str(call.from_user.id)
    await call.message.edit_text("Asosiy menyu:")
    await call.message.edit_reply_markup(reply_markup=main_menu(user_id))
    await call.answer()


@dp.callback_query()
async def callbacks(call: CallbackQuery, state: FSMContext):
    data = call.data
    user_id = str(call.from_user.id)

    # Kanalga a'zolikni tekshirish
    subscribed = await check_subscription(call.from_user.id)
    if not subscribed:
        await call.answer("🚫 Iltimos, avval kanallarga obuna bo'ling.", show_alert=True)
        await call.message.answer(
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇",
            reply_markup=subscription_keyboard()
        )
        return

    if data == "ai_consultation":
        # Premium tekshirish
        if not is_premium(user_id):
            await call.answer("🚫 Bu funksiya faqat premium foydalanuvchilar uchun!", show_alert=True)
            await call.message.answer(
                "🤖 AI maslahatidan foydalanish uchun premium obuna kerak!",
                reply_markup=premium_keyboard()
            )
            return
        
        await call.message.answer("💎 Premium: Savolingizni yozing - Moliyachi AI sizga batafsil maslahat beradi:")
        await call.answer()
        return

    if data == "show_profile":
        if user_id in user_data:
            user_info = user_data[user_id]
            premium_status = "✅ PREMIUM" if is_premium(user_id) else "❌ Oddiy"
            
            msg = (
                f"📋 Profil ma'lumotlari:\n\n"
                f"Yosh: {user_info[0]}\n"
                f"Kasb: {user_info[1]}\n"
                f"Daromad: {user_info[2]}\n"
                f"Qiziqishlar: {user_info[3]}\n"
                f"Biznes bor: {user_info[4]}\n"
                f"Status: {premium_status}"
            )
            await call.message.answer(msg)
        else:
            await call.message.answer("Profil to'ldirilmagan. /start buyrug'ini bosing.")

        await call.answer()
        return


@dp.message()
async def main_handler(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)

    # Kanalga a'zolikni tekshirish
    subscribed = await check_subscription(message.from_user.id)
    if not subscribed:
        await message.answer(
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇",
            reply_markup=subscription_keyboard()
        )
        return

    # Agar user profilingiz to'ldirmagan bo'lsa
    if user_id not in user_data:
        await message.answer("Iltimos, avval profilingizni to'ldiring. /start buyrug'ini bosing.")
        return

    # Premium tekshirish
    if not is_premium(user_id):
        await message.answer(
            "🤖 AI maslahatidan foydalanish uchun premium obuna kerak!\n\n"
            f"💰 Narxi: {PREMIUM_PRICE} so'm - 30 kun\n"
            "Cheksiz maslahatlar va batafsil javoblar!",
            reply_markup=premium_keyboard()
        )
        return

    # AI konsultatsiya rejimi
    await message.answer("💎 Premium: Moliyachi AI javob tayyorlayapti...")
    result = await ask_gigachat(user_id, message.text)
    await message.answer(result)


async def main():
    # Ma'lumotlarni yuklash
    load_user_data()
    print("Bot ishga tushdi...")
    print(f"Yuklangan userlar soni: {len(user_data)}")
    print(f"Premium foydalanuvchilar: {len(premium_data)}")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
