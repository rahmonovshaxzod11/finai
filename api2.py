import asyncio
import json
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from gigachat import GigaChat
from PIL import Image, ImageDraw, ImageFont
import random
from dotenv import load_dotenv

load_dotenv()

# Environment variables dan tokenni olish
API_TOKEN = os.getenv("API_TOKEN")
GIGA_TOKEN = os.getenv("GIGA_TOKEN")
user_data = {}

REQUIRED_CHANNELS = [
    ("1-kanal", "https://t.me/aaadhhaha1")
]

# Banklar bazasi
BANKS_DATA = {
    "NBU": {"name": "NBU", "rate": 18.5, "min_amount": 1000000, "color": "#4CAF50"},
    "kapitalbank": {"name": "Kapitalbank", "rate": 17.0, "min_amount": 500000, "color": "#2196F3"},
    "ipoteka": {"name": "Ipoteka bank", "rate": 16.5, "min_amount": 1000000, "color": "#FF9800"},
    "xalq": {"name": "Xalq banki", "rate": 15.0, "min_amount": 500000, "color": "#9C27B0"},
    "agro": {"name": "Agrobank", "rate": 14.5, "min_amount": 1000000, "color": "#795548"},
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
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, url=link)]
            for name, link in REQUIRED_CHANNELS
        ] + [
            [InlineKeyboardButton(text="🔄 Tekshirish", callback_data="check_sub")]
        ]
    )

# Asosiy menyu
def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🤖 Moliyachi AI bilan maslahat", callback_data="ai_consultation")],
            [InlineKeyboardButton(text="👤 Mening profilim", callback_data="show_profile")],
            [InlineKeyboardButton(text="📊 Kredit grafigi", callback_data="credit_graph")],
            [InlineKeyboardButton(text="🏦 Depozit kalkulyatori", callback_data="deposit_calc")],
        ]
    )

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
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Ha (Murakkab foiz)", callback_data="cap_yes")],
            [InlineKeyboardButton(text="❌ Yo'q (Oddiy foiz)", callback_data="cap_no")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")],
        ]
    )

# Depozit hisoblash funksiyasi
def calculate_deposit(amount, annual_rate, term_months, capitalization=True, tax_rate=12):
    try:
        monthly_rate = annual_rate / 100 / 12

        if capitalization:
            # Murakkab foiz (kapitalizatsiya bilan)
            total_amount = amount * (1 + monthly_rate) ** term_months
            total_interest = total_amount - amount
        else:
            # Oddiy foiz
            total_interest = amount * monthly_rate * term_months
            total_amount = amount + total_interest

        # Oylik daromad
        monthly_income = total_interest / term_months

        # Soliq hisobi (12% - daromad solig'i)
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

# Depozit natijasini chiroyli formatda
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
        f"📊 **HISOBNATIJALARI:**\n"
        f"💰 Jami foiz: {result['total_interest']:,.0f} so'm\n"
        f"🏦 Jami summa: {result['total_amount']:,.0f} so'm\n"
        f"📅 Oylik daromad: {result['monthly_income']:,.0f} so'm\n\n"
        f"💰 **Soliqdan keyin:**\n"
        f"🧾 Soliq ({result['tax_rate']}%): {result['tax_amount']:,.0f} so'm\n"
        f"💸 Sof foiz: {result['net_interest']:,.0f} so'm\n"
        f"🏦 Sof summa: {result['net_amount']:,.0f} so'm\n\n"
        f"💡 **Maslahat:** {get_deposit_advice(result)}"
    )

    return message

# Depozit maslahatlari
def get_deposit_advice(result):
    advice = []

    if result['annual_rate'] > 20:
        advice.append("Yuqori foiz - yuqori risk")
    elif result['annual_rate'] < 10:
        advice.append("Past foiz - kam risk")

    if result['term_months'] > 24:
        advice.append("Uzoq muddat - barqaror daromad")
    else:
        advice.append("Qisqa muddat - tez pul")

    if result['capitalization']:
        advice.append("Kapitalizatsiya - samaraliroq")
    else:
        advice.append("Oddiy foiz - oddiy hisob")

    return " | ".join(advice)

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

    for payment in schedule:
        table += f"│ {payment['number']:<3} │ {payment['date']} │ {payment['interest']:>11,.2f} │ {payment['total_payment']:>12,.2f} │ {payment['remaining_balance']:>12,.2f} │\n"

    table += "└─────┴────────────┴─────────────┴──────────────┴──────────────┘\n"

    total_interest = sum(payment['interest'] for payment in schedule)
    total_payments = sum(payment['total_payment'] for payment in schedule)

    table += f"\n**Umumiy foizlar:** {total_interest:,.2f}\n"
    table += f"**Umumiy to'lov:** {total_payments:,.2f}\n"
    table += f"**Asosiy qarz:** {schedule[0]['remaining_balance'] + schedule[0]['total_payment'] - schedule[0]['interest']:,.2f}"

    return table

# Rasm yaratish funksiyasi
def create_credit_schedule_image(schedule, credit_info):
    try:
        display_schedule = schedule[:24]
        row_height = 30
        header_height = 120
        footer_height = 60
        height = header_height + (len(display_schedule) * row_height) + footer_height
        width = 900

        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)

        try:
            title_font = ImageFont.truetype("arial.ttf", 20)
            header_font = ImageFont.truetype("arial.ttf", 14)
            text_font = ImageFont.truetype("arial.ttf", 10)
        except:
            title_font = ImageFont.load_default()
            header_font = ImageFont.load_default()
            text_font = ImageFont.load_default()

        draw.text((width // 2, 25), " KREDIT TOLOV GRAFIGI", fill='black', font=title_font, anchor='mm')
        info_text = f"Miqdor: {credit_info['amount']:,.0f} so'm | Foiz: {credit_info['interest_rate']}% | Muddati: {credit_info['term']} oy"
        draw.text((width // 2, 55), info_text, fill='darkblue', font=header_font, anchor='mm')

        headers = ["No", "Sana", "Foiz", "Jami to'lov", "Qoldiq"]
        col_widths = [50, 100, 100, 120, 120]
        x_pos = 30
        y_pos = 85

        for i, header in enumerate(headers):
            draw.rectangle([x_pos, y_pos, x_pos + col_widths[i], y_pos + 25], outline='black', fill='#e0e0e0')
            draw.text((x_pos + col_widths[i] // 2, y_pos + 12), header, fill='black', font=header_font, anchor='mm')
            x_pos += col_widths[i]

        y_pos = 110
        for payment in display_schedule:
            x_pos = 30
            row_data = [
                str(payment['number']),
                payment['date'],
                f"{payment['interest']:,.0f}",
                f"{payment['total_payment']:,.0f}",
                f"{payment['remaining_balance']:,.0f}"
            ]

            for i, data in enumerate(row_data):
                fill_color = '#f9f9f9' if payment['number'] % 2 == 0 else 'white'
                draw.rectangle([x_pos, y_pos, x_pos + col_widths[i], y_pos + row_height],
                               outline='black', fill=fill_color)
                draw.text((x_pos + col_widths[i] // 2, y_pos + 15), data, fill='black', font=text_font, anchor='mm')
                x_pos += col_widths[i]
            y_pos += row_height

        total_interest = sum(p['interest'] for p in schedule)
        total_payments = sum(p['total_payment'] for p in schedule)

        summary_y = y_pos + 10
        draw.text((30, summary_y), f"Umumiy foizlar: {total_interest:,.0f} so'm", fill='darkred', font=header_font)
        draw.text((30, summary_y + 20), f"Umumiy to'lov: {total_payments:,.0f} so'm", fill='darkgreen', font=header_font)

        if len(display_schedule) < len(schedule):
            draw.text((30, summary_y + 40), f"Faqat birinchi {len(display_schedule)} oy ko'rsatilgan",
                      fill='orange', font=header_font)

        random_suffix = random.randint(1000, 9999)
        img_path = f"credit_schedule_{credit_info['amount']}_{random_suffix}.png"
        img.save(img_path, quality=85, optimize=True)

        return img_path

    except Exception as e:
        print(f"Rasm yaratishda xatolik: {e}")
        return None

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
            "Assalomu alaykum xush kelibsiz! 😊Bank xizmatlari bo‘yicha nimadir qiziqtiryaptimi? Men shu yerda yordam berish uchun turibman. Ayting, nimadan boshlaymiz?",
            reply_markup=main_menu()
        )
        return

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
        if user_id in user_data:
            await call.message.edit_text("🎉 Obuna tasdiqlandi! Quyidagi menyudan birini tanlang:")
            await call.message.answer("Menyu:", reply_markup=main_menu())
        else:
            await call.message.edit_text("🎉 Obuna tasdiqlandi! Profilingizni to'ldirishni boshlaymiz.")
            await call.message.answer("Yoshingizni kiriting:")
            await state.set_state(ProfileForm.age)
    await call.answer()

@dp.message(ProfileForm.age)
async def set_age(message: Message, state: FSMContext):
    subscribed = await check_subscription(message.from_user.id)
    if not subscribed:
        await message.answer("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇", reply_markup=subscription_keyboard())
        return

    user_id = str(message.from_user.id)
    if user_id not in user_data:
        user_data[user_id] = {"profile": [], "credit_info": None}

    await state.update_data(age=message.text)
    await state.set_state(ProfileForm.job)
    await message.answer("Kasbingiz yoki o'qishingiz?")

@dp.message(ProfileForm.job)
async def set_job(message: Message, state: FSMContext):
    subscribed = await check_subscription(message.from_user.id)
    if not subscribed:
        await message.answer("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇", reply_markup=subscription_keyboard())
        return

    await state.update_data(job=message.text)
    await state.set_state(ProfileForm.income)
    await message.answer("Oylik daromadingiz qancha?")

@dp.message(ProfileForm.income)
async def set_income(message: Message, state: FSMContext):
    subscribed = await check_subscription(message.from_user.id)
    if not subscribed:
        await message.answer("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇", reply_markup=subscription_keyboard())
        return

    await state.update_data(income=message.text)
    await state.set_state(ProfileForm.interest)
    await message.answer("Qiziqishlaringiz?")

@dp.message(ProfileForm.interest)
async def set_interest(message: Message, state: FSMContext):
    subscribed = await check_subscription(message.from_user.id)
    if not subscribed:
        await message.answer("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇", reply_markup=subscription_keyboard())
        return

    await state.update_data(interest=message.text)
    await state.set_state(ProfileForm.business)
    await message.answer("Hozir biznesingiz bormi? (ha/yo'q)")

@dp.message(ProfileForm.business)
async def finish_profile(message: Message, state: FSMContext):
    subscribed = await check_subscription(message.from_user.id)
    if not subscribed:
        await message.answer("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇", reply_markup=subscription_keyboard())
        return

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
        f"Biznes bor: {data.get('business')}"
    )

    await message.answer(msg)
    await message.answer("Quyidagi menyudan birini tanlang:", reply_markup=main_menu())
    await state.clear()

# Kredit ma'lumotlarini olish
@dp.callback_query(F.data == "credit_graph")
async def start_credit_form(call: CallbackQuery, state: FSMContext):
    subscribed = await check_subscription(call.from_user.id)
    if not subscribed:
        await call.answer("🚫 Iltimos, avval kanallarga obuna bo'ling.", show_alert=True)
        await call.message.answer("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇", reply_markup=subscription_keyboard())
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
            await message.answer("Iltimos, 360 oydan (30 yil) kamroq muddat kiriting.")
            return
        await state.update_data(term=term)
        await state.set_state(CreditForm.start_date)
        await message.answer("Kredit olingan sanani kiriting (kun.oy.yil formatida, masalan: 01.10.2024):")
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
            if len(table) > 4000:
                parts = [table[i:i + 4000] for i in range(0, len(table), 4000)]
                for part in parts:
                    await message.answer(f"```\n{part}\n```", parse_mode="Markdown")
            else:
                await message.answer(f"```\n{table}\n```", parse_mode="Markdown")

            await message.answer("🖼️ Rasm tayyorlanmoqda...")
            img_path = create_credit_schedule_image(schedule, data)

            if img_path and os.path.exists(img_path):
                try:
                    photo = FSInputFile(img_path)
                    await message.answer_photo(
                        photo,
                        caption=f"📊 Kredit to'lov grafigi\n\n" +
                                f"💵 Miqdor: {data['amount']:,.0f} so'm\n" +
                                f"📈 Foiz: {data['interest_rate']}%\n" +
                                f"📅 Muddati: {data['term']} oy\n" +
                                f"🗓️ Boshlanish sanasi: {data['start_date']}"
                    )
                    os.remove(img_path)
                except Exception as e:
                    print(f"Rasm yuborishda xatolik: {e}")
                    await message.answer("⚠️ Rasm yuborib bo'lmadi, lekin matn shaklda mavjud")
            else:
                await message.answer("⚠️ Rasm yaratib bo'lmadi, faqat matn shaklda mavjud")

            await message.answer("✅ Kredit grafigi saqlandi! Quyidagi menyudan boshqa amalni tanlang:", reply_markup=main_menu())
        else:
            await message.answer("❌ Xatolik: Kredit grafigini hisoblab bo'lmadi. Ma'lumotlarni tekshiring.")

    except ValueError:
        await message.answer("❌ Iltimos, sanani to'g'ri formatda kiriting. Masalan: 01.10.2024")
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {str(e)}")

    await state.clear()

# Depozit kalkulyatorini boshlash
@dp.callback_query(F.data == "deposit_calc")
async def start_deposit_calc(call: CallbackQuery, state: FSMContext):
    subscribed = await check_subscription(call.from_user.id)
    if not subscribed:
        await call.answer("🚫 Iltimos, avval kanallarga obuna bo'ling.", show_alert=True)
        return

    await call.message.answer(
        "🏦 **Depozit Kalkulyatori**\n\n"
        "Depozit summasini kiriting (so'mda):",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]]
        )
    )
    await state.set_state(DepositForm.amount)
    await call.answer()

# Depozit summasini qabul qilish
@dp.message(DepositForm.amount)
async def set_deposit_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '').replace(' ', ''))
        if amount < 100000:
            await message.answer("❌ Minimal summa 100,000 so'm. Qayta kiriting:")
            return

        await state.update_data(amount=amount)
        await state.set_state(DepositForm.term)
        await message.answer(
            f"💵 Summa: {amount:,.0f} so'm\n\n"
            "Depozit muddatini kiriting (oylarda):",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="deposit_calc")]]
            )
        )
    except ValueError:
        await message.answer("❌ Iltimos, raqam kiriting. Masalan: 1000000")

# Depozit muddatini qabul qilish
@dp.message(DepositForm.term)
async def set_deposit_term(message: Message, state: FSMContext):
    try:
        term = int(message.text)
        if term < 1 or term > 60:
            await message.answer("❌ Muddat 1-60 oy oralig'ida bo'lishi kerak. Qayta kiriting:")
            return

        await state.update_data(term=term)
        await state.set_state(DepositForm.bank_choice)

        data = await state.get_data()
        amount = data['amount']

        comparison = compare_banks(amount, term)
        await message.answer(f"{comparison}\nQuyidagi banklardan birini tanlang:", reply_markup=banks_keyboard())
    except ValueError:
        await message.answer("❌ Iltimos, butun son kiriting. Masalan: 12")

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
            f"📈 Foiz stavkasi: {bank_info['rate']}%\n\n"
            "Foizlar kapitalizatsiyasi kerakmi?\n"
            "(Murakkab foiz - samaraliroq)",
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

        await call.message.answer(
            "🔄 Boshqa banklarni solishtirishni xohlaysizmi?",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Banklarni solishtirish", callback_data=f"compare_{data['amount']}_{data['term']}")],
                    [InlineKeyboardButton(text="📊 Boshqa hisob", callback_data="deposit_calc")],
                    [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")],
                ]
            )
        )
    else:
        await call.message.edit_text("❌ Hisoblab bo'lmadi. Qayta urinib ko'ring.")

    await call.answer()

# Banklarni solishtirish
@dp.callback_query(F.data.startswith("compare_"))
async def compare_banks_callback(call: CallbackQuery):
    try:
        _, amount, term = call.data.split("_")
        amount = float(amount)
        term = int(term)

        comparison = compare_banks(amount, term)
        await call.message.answer(comparison, parse_mode="Markdown")

        await call.message.answer(
            "Yana hisob qilishni xohlaysizmi?",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Yangi hisob", callback_data="deposit_calc")],
                    [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")],
                ]
            )
        )
    except Exception as e:
        await call.message.answer("❌ Xatolik yuz berdi.")

    await call.answer()

# Asosiy menyuga qaytish
@dp.callback_query(F.data == "main_menu")
async def back_to_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("🏠 Bosh menyu:", reply_markup=main_menu())
    await call.answer()

@dp.callback_query()
async def callbacks(call: CallbackQuery, state: FSMContext):
    data = call.data
    user_id = str(call.from_user.id)

    subscribed = await check_subscription(call.from_user.id)
    if not subscribed:
        await call.answer("🚫 Iltimos, avval kanallarga obuna bo'ling.", show_alert=True)
        await call.message.answer("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇", reply_markup=subscription_keyboard())
        return

    if data == "ai_consultation":
        await call.message.answer("Savolingizni yozing - Moliyachi AI sizga maslahat beradi:")
        await call.answer()
        return

    if data == "show_profile":
        if user_id in user_data and user_data[user_id]["profile"]:
            user_info = user_data[user_id]["profile"]
            msg = (
                f"📋 Profil ma'lumotlari:\n\n"
                f"👤 Yosh: {user_info[0]}\n"
                f"💼 Kasb: {user_info[1]}\n"
                f"💰 Daromad: {user_info[2]}\n"
                f"🎯 Qiziqishlar: {user_info[3]}\n"
                f"🏢 Biznes bor: {user_info[4]}"
            )
            await call.message.answer(msg)

            if user_data[user_id]["credit_info"]:
                credit_info = user_data[user_id]["credit_info"]
                credit_msg = (
                    f"\n📊 **Kredit ma'lumotlari:**\n"
                    f"💵 Miqdor: {credit_info['amount']:,.2f} so'm\n"
                    f"📈 Foiz stavkasi: {credit_info['interest_rate']}%\n"
                    f"📅 Muddati: {credit_info['term']} oy\n"
                    f"🗓️ Boshlanish sanasi: {credit_info['start_date']}"
                )
                await call.message.answer(credit_msg)
        else:
            await call.message.answer("❌ Profil to'ldirilmagan. /start buyrug'ini bosing.")

        await call.answer()
        return

    if data == "credit_graph":
        await start_credit_form(call, state)
        return

# GigaChat bilan ishlash funksiyasi
async def ask_gigachat(user_id: str, user_question: str) -> str:
    try:
        if user_id in user_data:
            user_info = user_data[user_id]["profile"]
            data = f"Yoshim: {user_info[0]}, Kasbim: {user_info[1]}, Oylik daromadim: {user_info[2]}, Qiziqishlarim: {user_info[3]}, Biznesim bor: {user_info[4]}"

            if user_data[user_id]["credit_info"]:
                credit_info = user_data[user_id]["credit_info"]
                data += f", Kredit ma'lumotlari: Miqdor: {credit_info['amount']:,.2f} so'm, Foiz: {credit_info['interest_rate']}%, Muddati: {credit_info['term']} oy"
        else:
            data = "User ma'lumotlari topilmadi"

        full_prompt = f"User ma'lumotlari: {data}\n\nUser savoli: {user_question}\n\nIltimos, moliyaviy maslahat bering:"

        with GigaChat(
                credentials="MDE5YWFjYWMtNTdmYi03NTMwLTg4MTctMTQwN2IwNTNlM2FmOjAwNmQ3ZGYwLTM4N2EtNGI2ZS05ODQxLWZhZjAyOTJjZTAyMw==",
                verify_ssl_certs=False) as giga:
            response = giga.chat(full_prompt)
            return response.choices[0].message.content

    except Exception as e:
        return f"Xatolik yuz berdi: {str(e)}"

@dp.message()
async def main_handler(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)

    subscribed = await check_subscription(message.from_user.id)
    if not subscribed:
        await message.answer("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇", reply_markup=subscription_keyboard())
        return

    if user_id not in user_data:
        await message.answer("Iltimos, avval profilingizni to'ldiring. /start buyrug'ini bosing.")
        return

    await message.answer("⏳ Moliyachi AI javob tayyorlayapti...")
    result = await ask_gigachat(user_id, message.text)
    await message.answer(result)

async def main():
    load_user_data()
    print("🤖 Bot ishga tushdi...")
    print(f"👥 Yuklangan userlar soni: {len(user_data)}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())