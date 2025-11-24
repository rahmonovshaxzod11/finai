import asyncio
import json
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
import requests

# .env faylini yuklash
load_dotenv()

# Environment variables dan tokenni olish
API_TOKEN = os.getenv("API_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Tokenlarni tekshirish
if not API_TOKEN:
    raise ValueError("API_TOKEN .env faylda topilmadi!")

# JSON fayl nomi
USER_DATA_FILE = "user_data.json"

# User ma'lumotlarini saqlash uchun lug'at
user_data = {}

REQUIRED_CHANNELS = [
    ("1-kanal", "https://t.me/aaadhhaha1")
]

# Banklar bazasi
BANKS_DATA = {
    "NBU": {"name": "NBU", "rate": 18.5, "min_amount": 1000000},
    "kapitalbank": {"name": "Kapitalbank", "rate": 17.0, "min_amount": 500000},
    "ipoteka": {"name": "Ipoteka bank", "rate": 16.5, "min_amount": 1000000},
    "xalq": {"name": "Xalq banki", "rate": 15.0, "min_amount": 500000},
    "agro": {"name": "Agrobank", "rate": 14.5, "min_amount": 1000000},
}

class ProfileForm(StatesGroup):
    age = State()
    job = State()
    income = State()
    interest = State()
    business = State()

class CreditForm(StatesGroup):
    amount = State()
    interest_rate = State()
    term = State()
    start_date = State()

class DepositForm(StatesGroup):
    amount = State()
    term = State()
    bank_choice = State()
    capitalization = State()

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# JSON fayldan ma'lumotlarni o'qish
def load_user_data():
    global user_data
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                user_data = json.load(f)
        except Exception as e:
            print(f"Faylni o'qishda xatolik: {e}")
            user_data = {}

# JSON faylga ma'lumotlarni yozish
def save_user_data():
    try:
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Faylga yozishda xatolik: {e}")

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
    keyboard = []
    for name, link in REQUIRED_CHANNELS:
        keyboard.append([InlineKeyboardButton(text=name, url=link)])
    keyboard.append([InlineKeyboardButton(text="🔄 Tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Asosiy menyu
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Moliyachi AI bilan maslahat", callback_data="ai_consultation")],
        [InlineKeyboardButton(text="👤 Mening profilim", callback_data="show_profile")],
        [InlineKeyboardButton(text="📊 Kredit grafigi", callback_data="credit_graph")],
        [InlineKeyboardButton(text="🏦 Depozit kalkulyatori", callback_data="deposit_calc")],
    ])

# Bank tanlash klaviaturasi
def banks_keyboard():
    buttons = []
    for bank_id, bank_info in BANKS_DATA.items():
        buttons.append([
            InlineKeyboardButton(
                text=f"{bank_info['name']} ({bank_info['rate']}%)",
                callback_data=f"bank_{bank_id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Kapitalizatsiya tanlash
def capitalization_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha (Murakkab foiz)", callback_data="cap_yes")],
        [InlineKeyboardButton(text="❌ Yo'q (Oddiy foiz)", callback_data="cap_no")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")],
    ])

# OpenAI bilan ishlash funksiyasi
async def ask_openai(user_id: str, user_question: str) -> str:
    try:
        if not OPENAI_API_KEY:
            return "🤖 **Moliyaviy Maslahat**\n\n" \
                   "Hozircha AI xizmati mavjud emas. Quyidagi maslahatlarimiz bilan tanishing:\n\n" \
                   "💡 **Umumiy moliyaviy maslahatlar:**\n" \
                   "• Har oy daromadingizning kamida 20% ni tejashing\n" \
                   "• Favqulodda vaziyatlar uchun 3-6 oylik daromad miqdorida jamg'arma yarating\n" \
                   "• Kredit olishdan oldin bir nechta banklarni solishtiring\n" \
                   "• Depozit ochishda foiz stavkasi va muddatiga e'tibor bering"

        # User ma'lumotlarini olish
        user_context = ""
        if user_id in user_data:
            user_info = user_data[user_id]["profile"]
            user_context = f"Yosh: {user_info[0]}, Kasb: {user_info[1]}, Daromad: {user_info[2]}, Qiziqishlar: {user_info[3]}, Biznes: {user_info[4]}"
            
            if user_data[user_id]["credit_info"]:
                credit_info = user_data[user_id]["credit_info"]
                user_context += f", Kredit: {credit_info['amount']:,.0f} so'm, Foiz: {credit_info['interest_rate']}%, Muddati: {credit_info['term']} oy"

        # To'liq prompt tayyorlash
        system_prompt = """Siz moliyaviy maslahatchi AI siz. O'zbekiston bozoriga mos maslahatlar bering."""

        full_prompt = f"User: {user_context}\nSavol: {user_question}\n\nMaslahat bering:"

        # OpenAI API ga so'rov
        url = "https://api.openai.com/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 800
        }

        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            return "🤖 AI xizmatida vaqtinchalik muammo. Iltimos, keyinroq urinib ko'ring."
                    
    except Exception as e:
        return f"🤖 Xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring."

# Depozit hisoblash funksiyasi
def calculate_deposit(amount, annual_rate, term_months, capitalization=True, tax_rate=12):
    try:
        monthly_rate = annual_rate / 100 / 12

        if capitalization:
            total_amount = amount * (1 + monthly_rate) ** term_months
            total_interest = total_amount - amount
        else:
            total_interest = amount * monthly_rate * term_months
            total_amount = amount + total_interest

        monthly_income = total_interest / term_months
        tax_amount = total_interest * (tax_rate / 100)
        net_interest = total_interest - tax_amount
        net_amount = amount + net_interest

        return {
            'initial_amount': amount,
            'annual_rate': annual_rate,
            'term_months': term_months,
            'capitalization': capitalization,
            'total_interest': round(total_interest, 2),
            'total_amount': round(total_amount, 2),
            'monthly_income': round(monthly_income, 2),
            'tax_amount': round(tax_amount, 2),
            'net_interest': round(net_interest, 2),
            'net_amount': round(net_amount, 2),
            'tax_rate': tax_rate
        }
    except Exception as e:
        print(f"Depozit hisobida xatolik: {e}")
        return None

# Depozit natijasini formatda
def format_deposit_result(result, bank_name):
    if not result:
        return "Xatolik: Hisoblab bo'lmadi"

    cap_text = "Murakkab foiz" if result['capitalization'] else "Oddiy foiz"

    message = (
        f"🏦 **DEPOZIT HISOBI**\n"
        f"📊 Bank: {bank_name}\n\n"
        f"💵 Boshlang'ich summa: {result['initial_amount']:,.0f} so'm\n"
        f"📈 Yillik foiz: {result['annual_rate']}%\n"
        f"⏰ Muddat: {result['term_months']} oy\n"
        f"🔢 Foiz turi: {cap_text}\n\n"
        f"💰 Jami foiz: {result['total_interest']:,.0f} so'm\n"
        f"🏦 Jami summa: {result['total_amount']:,.0f} so'm\n"
        f"📅 Oylik daromad: {result['monthly_income']:,.0f} so'm\n\n"
        f"🧾 Soliq ({result['tax_rate']}%): {result['tax_amount']:,.0f} so'm\n"
        f"💸 Sof foiz: {result['net_interest']:,.0f} so'm\n"
        f"🏦 Sof summa: {result['net_amount']:,.0f} so'm"
    )

    return message

# Banklar solishtirish
def compare_banks(amount, term_months):
    comparison = "🏦 **BANKLAR SOLISHTIRISHI**\n\n"

    for bank_id, bank_info in BANKS_DATA.items():
        if amount >= bank_info['min_amount']:
            result = calculate_deposit(
                amount, bank_info['rate'], term_months,
                capitalization=True, tax_rate=12
            )

            if result:
                comparison += (
                    f"🏛️ **{bank_info['name']}** ({bank_info['rate']}%)\n"
                    f"💰 Sof daromad: {result['net_interest']:,.0f} so'm\n"
                    f"💳 Minimal summa: {bank_info['min_amount']:,.0f} so'm\n\n"
                )

    return comparison

# Kredit grafigini hisoblash
def calculate_credit_schedule(amount, interest_rate, term, start_date):
    try:
        start_date = datetime.strptime(start_date, "%d.%m.%Y")
        monthly_rate = interest_rate / 100 / 12
        monthly_payment = amount * (monthly_rate * (1 + monthly_rate) ** term) / ((1 + monthly_rate) ** term - 1)

        schedule = []
        remaining_balance = amount

        for i in range(1, term + 1):
            interest_payment = remaining_balance * monthly_rate
            principal_payment = monthly_payment - interest_payment
            remaining_balance -= principal_payment

            if i == term:
                monthly_payment += remaining_balance
                principal_payment += remaining_balance
                remaining_balance = 0

            payment_date = start_date + timedelta(days=30 * i)

            schedule.append({
                'number': i,
                'date': payment_date.strftime("%d.%m.%Y"),
                'interest': round(interest_payment, 2),
                'total_payment': round(monthly_payment, 2),
                'remaining_balance': round(max(remaining_balance, 0), 2)
            })

        return schedule
    except Exception as e:
        print(f"Kredit grafigini hisoblashda xatolik: {e}")
        return None

# Jadvalni matn shaklida yaratish
def create_schedule_table(schedule):
    if not schedule:
        return "Xatolik: Jadval yaratib bo'lmadi"

    table = "📊 **KREDIT TOLOV GRAFIGI**\n\n"
    table += "┌─────┬────────────┬─────────────┬──────────────┬──────────────┐\n"
    table += "│ No  │ Sana       │ Foiz        │ Jami to'lov  │ Qoldiq       │\n"
    table += "├─────┼────────────┼─────────────┼──────────────┼──────────────┤\n"

    for payment in schedule[:12]:
        table += f"│ {payment['number']:<3} │ {payment['date']} │ {payment['interest']:>11,.0f} │ {payment['total_payment']:>12,.0f} │ {payment['remaining_balance']:>12,.0f} │\n"

    table += "└─────┴────────────┴─────────────┴──────────────┴──────────────┘\n"

    total_interest = sum(payment['interest'] for payment in schedule)
    total_payments = sum(payment['total_payment'] for payment in schedule)

    table += f"\n**Umumiy foizlar:** {total_interest:,.0f} so'm\n"
    table += f"**Umumiy to'lov:** {total_payments:,.0f} so'm\n"
    table += f"**Asosiy qarz:** {schedule[0]['remaining_balance'] + schedule[0]['total_payment'] - schedule[0]['interest']:,.0f} so'm"
    
    if len(schedule) > 12:
        table += f"\n\nℹ️ Faqat birinchi 12 oy ko'rsatildi. Jami {len(schedule)} oy."

    return table

# Start handler
@dp.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    subscribed = await check_subscription(message.from_user.id)

    if not subscribed:
        await message.answer(
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇",
            reply_markup=subscription_keyboard()
        )
        return

    if user_id in user_data:
        await message.answer(
            "Assalomu alaykum! Bank xizmatlari bo'yicha yordam kerakmi?",
            reply_markup=main_menu()
        )
        return

    await message.answer("🎉 Profilingizni to'ldirishni boshlaymiz.\nYoshingizni kiriting:")
    await state.set_state(ProfileForm.age)

# Kanal tekshirish
@dp.callback_query(F.data == "check_sub")
async def check_subscription_callback(call: CallbackQuery, state: FSMContext):
    subscribed = await check_subscription(call.from_user.id)

    if not subscribed:
        await call.answer("Hali obuna bo'lmadingiz!", show_alert=True)
        await call.message.answer(
            "Iltimos, kanallarga obuna bo'ling:",
            reply_markup=subscription_keyboard()
        )
    else:
        user_id = str(call.from_user.id)
        if user_id in user_data:
            await call.message.edit_text("Obuna tasdiqlandi! Menyu:")
            await call.message.answer("Tanlang:", reply_markup=main_menu())
        else:
            await call.message.edit_text("Obuna tasdiqlandi! Profil to'ldiring.")
            await call.message.answer("Yoshingizni kiriting:")
            await state.set_state(ProfileForm.age)
    await call.answer()

# Profil to'ldirish
@dp.message(ProfileForm.age)
async def set_age(message: Message, state: FSMContext):
    if not await check_subscription(message.from_user.id):
        await message.answer("Iltimos, avval kanallarga obuna bo'ling.", reply_markup=subscription_keyboard())
        return

    user_id = str(message.from_user.id)
    if user_id not in user_data:
        user_data[user_id] = {"profile": [], "credit_info": None}

    await state.update_data(age=message.text)
    await state.set_state(ProfileForm.job)
    await message.answer("Kasbingiz yoki o'qishingiz?")

@dp.message(ProfileForm.job)
async def set_job(message: Message, state: FSMContext):
    await state.update_data(job=message.text)
    await state.set_state(ProfileForm.income)
    await message.answer("Oylik daromadingiz qancha?")

@dp.message(ProfileForm.income)
async def set_income(message: Message, state: FSMContext):
    await state.update_data(income=message.text)
    await state.set_state(ProfileForm.interest)
    await message.answer("Qiziqishlaringiz?")

@dp.message(ProfileForm.interest)
async def set_interest(message: Message, state: FSMContext):
    await state.update_data(interest=message.text)
    await state.set_state(ProfileForm.business)
    await message.answer("Hozir biznesingiz bormi? (ha/yo'q)")

@dp.message(ProfileForm.business)
async def finish_profile(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    await state.update_data(business=message.text)
    data = await state.get_data()

    user_data[user_id] = {
        "profile": [
            data.get('age', ''),
            data.get('job', ''),
            data.get('income', ''),
            data.get('interest', ''),
            data.get('business', '')
        ],
        "credit_info": None
    }

    save_user_data()

    msg = (
        "📋 Profil saqlandi!\n\n"
        f"Yosh: {data.get('age')}\n"
        f"Kasb: {data.get('job')}\n"
        f"Daromad: {data.get('income')}\n"
        f"Qiziqishlar: {data.get('interest')}\n"
        f"Biznes: {data.get('business')}"
    )

    await message.answer(msg)
    await message.answer("Quyidagi menyudan tanlang:", reply_markup=main_menu())
    await state.clear()

# Kredit grafigi
@dp.callback_query(F.data == "credit_graph")
async def start_credit_form(call: CallbackQuery, state: FSMContext):
    if not await check_subscription(call.from_user.id):
        await call.answer("Avval kanallarga obuna bo'ling!", show_alert=True)
        return

    await call.message.answer("Kredit miqdorini kiriting (so'mda):")
    await state.set_state(CreditForm.amount)
    await call.answer()

@dp.message(CreditForm.amount)
async def set_credit_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '').replace(' ', ''))
        await state.update_data(amount=amount)
        await state.set_state(CreditForm.interest_rate)
        await message.answer("Yillik foiz stavkasini kiriting (%):")
    except ValueError:
        await message.answer("Iltimos, raqam kiriting. Masalan: 10000000")

@dp.message(CreditForm.interest_rate)
async def set_interest_rate(message: Message, state: FSMContext):
    try:
        interest_rate = float(message.text.replace(',', '.'))
        await state.update_data(interest_rate=interest_rate)
        await state.set_state(CreditForm.term)
        await message.answer("Kredit muddatini kiriting (oylarda):")
    except ValueError:
        await message.answer("Iltimos, foiz stavkasini to'g'ri kiriting. Masalan: 18.5")

@dp.message(CreditForm.term)
async def set_credit_term(message: Message, state: FSMContext):
    try:
        term = int(message.text)
        if term > 360:
            await message.answer("Iltimos, 360 oydan kamroq muddat kiriting.")
            return
        await state.update_data(term=term)
        await state.set_state(CreditForm.start_date)
        await message.answer("Kredit olingan sanani kiriting (kun.oy.yil formatida):")
    except ValueError:
        await message.answer("Iltimos, butun son kiriting. Masalan: 12")

@dp.message(CreditForm.start_date)
async def finish_credit_form(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)

    try:
        start_date = message.text
        datetime.strptime(start_date, "%d.%m.%Y")

        await state.update_data(start_date=start_date)
        data = await state.get_data()

        schedule = calculate_credit_schedule(
            data['amount'],
            data['interest_rate'],
            data['term'],
            data['start_date']
        )

        if schedule:
            if user_id in user_data:
                user_data[user_id]["credit_info"] = data
            else:
                user_data[user_id] = {"profile": [], "credit_info": data}

            save_user_data()

            table = create_schedule_table(schedule)
            await message.answer(f"```\n{table}\n```", parse_mode="Markdown")
            await message.answer("✅ Kredit grafigi saqlandi!", reply_markup=main_menu())
        else:
            await message.answer("❌ Xatolik: Hisoblab bo'lmadi.")

    except ValueError:
        await message.answer("❌ Iltimos, sanani to'g'ri formatda kiriting.")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

    await state.clear()

# Depozit kalkulyatori
@dp.callback_query(F.data == "deposit_calc")
async def start_deposit_calc(call: CallbackQuery, state: FSMContext):
    if not await check_subscription(call.from_user.id):
        await call.answer("Avval kanallarga obuna bo'ling!", show_alert=True)
        return

    await call.message.answer("Depozit summasini kiriting (so'mda):")
    await state.set_state(DepositForm.amount)
    await call.answer()

@dp.message(DepositForm.amount)
async def set_deposit_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '').replace(' ', ''))
        if amount < 100000:
            await message.answer("❌ Minimal summa 100,000 so'm.")
            return

        await state.update_data(amount=amount)
        await state.set_state(DepositForm.term)
        await message.answer("Depozit muddatini kiriting (oylarda):")
    except ValueError:
        await message.answer("❌ Iltimos, raqam kiriting.")

@dp.message(DepositForm.term)
async def set_deposit_term(message: Message, state: FSMContext):
    try:
        term = int(message.text)
        if term < 1 or term > 60:
            await message.answer("❌ Muddat 1-60 oy oralig'ida bo'lishi kerak.")
            return

        await state.update_data(term=term)
        await state.set_state(DepositForm.bank_choice)

        data = await state.get_data()
        amount = data['amount']

        comparison = compare_banks(amount, term)
        await message.answer(f"{comparison}\nBank tanlang:", reply_markup=banks_keyboard())
    except ValueError:
        await message.answer("❌ Iltimos, butun son kiriting.")

# Bank tanlash
@dp.callback_query(F.data.startswith("bank_"))
async def select_bank(call: CallbackQuery, state: FSMContext):
    bank_id = call.data.replace("bank_", "")

    if bank_id in BANKS_DATA:
        bank_info = BANKS_DATA[bank_id]
        await state.update_data(bank_id=bank_id, interest_rate=bank_info['rate'])
        await state.set_state(DepositForm.capitalization)

        data = await state.get_data()

        await call.message.edit_text(
            f"🏦 Bank: {bank_info['name']}\n"
            f"💵 Summa: {data['amount']:,.0f} so'm\n"
            f"📅 Muddat: {data['term']} oy\n"
            f"📈 Foiz: {bank_info['rate']}%\n\n"
            "Foizlar kapitalizatsiyasi kerakmi?",
            reply_markup=capitalization_keyboard()
        )
    await call.answer()

# Kapitalizatsiya tanlash
@dp.callback_query(F.data.startswith("cap_"))
async def select_capitalization(call: CallbackQuery, state: FSMContext):
    capitalization = call.data == "cap_yes"
    await state.update_data(capitalization=capitalization)

    data = await state.get_data()
    bank_info = BANKS_DATA[data['bank_id']]

    result = calculate_deposit(
        data['amount'],
        data['interest_rate'],
        data['term'],
        capitalization,
        tax_rate=12
    )

    if result:
        message = format_deposit_result(result, bank_info['name'])
        await call.message.edit_text(message, parse_mode="Markdown")
        await call.message.answer("Boshqa hisob qilishni xohlaysizmi?", 
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                    [InlineKeyboardButton(text="🔄 Yangi hisob", callback_data="deposit_calc")],
                                    [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")],
                                ]))
    else:
        await call.message.edit_text("❌ Hisoblab bo'lmadi.")

    await call.answer()

# Asosiy menyu
@dp.callback_query(F.data == "main_menu")
async def back_to_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Bosh menyu:", reply_markup=main_menu())
    await call.answer()

# Profil ko'rish
@dp.callback_query(F.data == "show_profile")
async def show_profile(call: CallbackQuery):
    user_id = str(call.from_user.id)

    if user_id in user_data and user_data[user_id]["profile"]:
        user_info = user_data[user_id]["profile"]
        msg = (
            f"📋 Profil ma'lumotlari:\n\n"
            f"👤 Yosh: {user_info[0]}\n"
            f"💼 Kasb: {user_info[1]}\n"
            f"💰 Daromad: {user_info[2]}\n"
            f"🎯 Qiziqishlar: {user_info[3]}\n"
            f"🏢 Biznes: {user_info[4]}"
        )
        await call.message.answer(msg)
    else:
        await call.message.answer("❌ Profil to'ldirilmagan.")

    await call.answer()

# AI konsultatsiya
@dp.callback_query(F.data == "ai_consultation")
async def ai_consultation(call: CallbackQuery):
    await call.message.answer("Savolingizni yozing - AI maslahat beradi:")
    await call.answer()

# Asosiy handler
@dp.message()
async def main_handler(message: Message):
    user_id = str(message.from_user.id)

    if not await check_subscription(message.from_user.id):
        await message.answer("Iltimos, avval kanallarga obuna bo'ling.", reply_markup=subscription_keyboard())
        return

    if user_id not in user_data:
        await message.answer("Iltimos, avval profilingizni to'ldiring. /start buyrug'ini bosing.")
        return

    await message.answer("⏳ AI javob tayyorlayapti...")
    result = await ask_openai(user_id, message.text)
    await message.answer(result)

# Asosiy funksiya
async def main():
    load_user_data()
    print("🤖 Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
