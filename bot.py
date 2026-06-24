import logging
import sqlite3
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# ===== КОНФИГУРАЦИЯ =====
TOKEN = "ЗАМЕНИ_НА_СВОЙ_ТОКЕН"
ADMIN_ID = 123456789  # ТВОЙ ID (узнать у @userinfobot)
PRICE = 125  # руб

bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# ===== БАЗА ДАННЫХ =====
def init_db():
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        registered_at TEXT,
        subscription_end TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT,
        category TEXT,
        done INTEGER DEFAULT 0,
        added_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS meals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        calories INTEGER,
        protein REAL,
        fat REAL,
        carbs REAL,
        added_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS water (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        added_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS workouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        wtype TEXT,
        duration INTEGER,
        date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        user_id INTEGER PRIMARY KEY,
        water_norm INTEGER DEFAULT 2500
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT,
        author TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

# ===== ДОБАВЛЕНИЕ СТАНДАРТНЫХ ФРАЗ =====
def seed_quotes():
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM quotes")
    if c.fetchone()[0] == 0:
        quotes = [
            ("Ты не обязан быть великим, но ты обязан начать.", "Зиг Зиглар"),
            ("Дисциплина — это мост между целями и достижениями.", "Джим Рон"),
            ("Каждое утро у тебя есть два выбора: продолжать спать и мечтать, или встать и воплощать мечты в реальность.", "Неизвестный"),
            ("Маленькие ежедневные усилия суммируются в огромные результаты.", "Робин Шарма"),
            ("Если ты устал начинать сначала, перестань сдаваться.", "Неизвестный"),
            ("Твоя единственная конкуренция — это ты вчерашний.", "Неизвестный"),
            ("Ты можешь всё, что захочешь, если готов заплатить цену.", "Арнольд Шварценеггер"),
            ("Сложно не значит невозможно.", "Неизвестный"),
            ("Сделай сегодня больше, чем вчера, и завтра будет лучше.", "Неизвестный"),
            ("Ты — сумма твоих привычек.", "Уильям Джеймс"),
        ]
        c.executemany("INSERT INTO quotes (text, author) VALUES (?, ?)", quotes)
        conn.commit()
    conn.close()

seed_quotes()

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
def register_user(user_id, username):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, registered_at) VALUES (?, ?, ?)",
              (user_id, username, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def is_subscribed(user_id):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("SELECT subscription_end FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0]:
        end_date = datetime.fromisoformat(row[0])
        return end_date > datetime.now()
    return False

def set_subscription(user_id, days=30):
    end = datetime.now() + timedelta(days=days)
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("UPDATE users SET subscription_end=? WHERE user_id=?", (end.isoformat(), user_id))
    conn.commit()
    conn.close()

def add_task(user_id, text, category="Общее"):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("INSERT INTO tasks (user_id, text, category, added_at) VALUES (?, ?, ?, ?)",
              (user_id, text, category, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_tasks(user_id):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("SELECT id, text, category, done FROM tasks WHERE user_id=? ORDER BY done, id", (user_id,))
    tasks = c.fetchall()
    conn.close()
    return tasks

def mark_done(user_id, task_id):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("UPDATE tasks SET done=1 WHERE id=? AND user_id=?", (task_id, user_id))
    conn.commit()
    conn.close()

def add_meal(user_id, name, calories, protein, fat, carbs):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("INSERT INTO meals (user_id, name, calories, protein, fat, carbs, added_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (user_id, name, calories, protein, fat, carbs, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_today_meals(user_id):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("SELECT name, calories, protein, fat, carbs FROM meals WHERE user_id=? AND date(added_at)=date(?)",
              (user_id, datetime.now().isoformat()))
    meals = c.fetchall()
    conn.close()
    return meals

def add_water(user_id, amount):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("INSERT INTO water (user_id, amount, added_at) VALUES (?, ?, ?)",
              (user_id, amount, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_today_water(user_id):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("SELECT SUM(amount) FROM water WHERE user_id=? AND date(added_at)=date(?)", (user_id, datetime.now().isoformat()))
    total = c.fetchone()[0] or 0
    conn.close()
    return total

def get_water_norm(user_id):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("SELECT water_norm FROM settings WHERE user_id=?", (user_id,))
    norm = c.fetchone()[0]
    conn.close()
    return norm

def set_water_norm(user_id, norm):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("UPDATE settings SET water_norm=? WHERE user_id=?", (norm, user_id))
    conn.commit()
    conn.close()

def add_workout(user_id, wtype, duration):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("INSERT INTO workouts (user_id, wtype, duration, date) VALUES (?, ?, ?, ?)",
              (user_id, wtype, duration, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_today_workout_count(user_id):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM workouts WHERE user_id=? AND date(date)=date(?)", (user_id, datetime.now().isoformat()))
    count = c.fetchone()[0] or 0
    conn.close()
    return count

def get_random_quote():
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("SELECT text, author FROM quotes ORDER BY RANDOM() LIMIT 1")
    row = c.fetchone()
    conn.close()
    if row:
        return row[0], row[1]
    else:
        return "У тебя всё получится!", "Неизвестный"

def get_all_users():
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("SELECT user_id, subscription_end FROM users")
    users = c.fetchall()
    conn.close()
    return users

# ===== КЛАВИАТУРА ГЛАВНОГО МЕНЮ =====
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Мой план"), KeyboardButton(text="➕ Добавить задачу")],
        [KeyboardButton(text="🍽️ Добавить еду"), KeyboardButton(text="💧 Вода")],
        [KeyboardButton(text="🏋️ Тренировка"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="🌟 Мотивация"), KeyboardButton(text="💳 Подписка")],
        [KeyboardButton(text="⚙️ Настройки")]
    ],
    resize_keyboard=True
)

# ===== ХЕНДЛЕРЫ =====
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    register_user(user_id, username)
    await message.answer(
        "🔥 Добро пожаловать в 520 System!\n"
        "Твой помощник для дисциплины и здоровья.\n\n"
        "⚠️ Бот работает в демо-режиме. Для доступа ко всем функциям оформи подписку 125 ₽/мес.\n"
        "Нажми '💳 Подписка' для оплаты.\n\n"
        "🌟 Каждое утро в 7:00 я буду присылать тебе мотивирующую фразу!",
        reply_markup=main_kb
    )

@dp.message(lambda m: m.text == "💳 Подписка")
async def subscribe(message: types.Message):
    user_id = message.from_user.id
    if is_subscribed(user_id):
        await message.answer("✅ У тебя уже есть активная подписка! Пользуйся.")
        return
    await message.answer(
        f"💳 ОФОРМЛЕНИЕ ПОДПИСКИ ({PRICE} ₽/мес):\n\n"
        "1️⃣ Переведи сумму на карту: **XXXX XXXX XXXX XXXX** (ВСТАВЬ СВОЙ НОМЕР)\n"
        "2️⃣ В назначении платежа укажи свой Telegram ID: " + str(user_id) + "\n"
        "3️⃣ После оплаты напиши администратору → @YourAdminUsername\n"
        "✅ Подписка активируется вручную в течение 1 часа.\n\n"
        "📌 Если у тебя нет ID, напиши @userinfobot — он покажет."
    )

@dp.message(lambda m: m.text == "🌟 Мотивация")
async def send_motivation(message: types.Message):
    text, author = get_random_quote()
    await message.answer(f"🌟 {text}\n— {author}")

# Админ-команда для активации подписки
@dp.message(Command("confirm"))
async def confirm_payment(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет прав для этой команды.")
        return
    try:
        user_id = int(message.text.split()[1])
        set_subscription(user_id)
        await message.answer(f"✅ Подписка для пользователя {user_id} активирована на 30 дней.")
    except:
        await message.answer("⚠️ Неверный формат. Используй: /confirm 123456789")

# Админ-команда для добавления новой фразы
@dp.message(Command("addquote"))
async def add_quote(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет прав.")
        return
    try:
        parts = message.text.split('/addquote', 1)[1].strip().split('|')
        if len(parts) == 2:
            text = parts[0].strip()
            author = parts[1].strip()
            conn = sqlite3.connect('user_data.db')
            c = conn.cursor()
            c.execute("INSERT INTO quotes (text, author) VALUES (?, ?)", (text, author))
            conn.commit()
            conn.close()
            await message.answer("✅ Фраза добавлена!")
        else:
            await message.answer("⚠️ Используй: /addquote Текст фразы | Автор")
    except:
        await message.answer("⚠️ Ошибка. Используй: /addquote Текст фразы | Автор")

# ===== ЗАЩИЩЁННЫЕ ФУНКЦИИ (только для подписчиков) =====
async def check_subscription(message: types.Message):
    user_id = message.from_user.id
    if not is_subscribed(user_id):
        await message.answer(
            "⛔ Эта функция доступна только подписчикам.\n"
            "Оформи подписку за 125 ₽ через кнопку '💳 Подписка'.",
            reply_markup=main_kb
        )
        return False
    return True

@dp.message(lambda m: m.text == "📋 Мой план")
async def show_plan(message: types.Message):
    if not await check_subscription(message): return
    user_id = message.from_user.id
    tasks = get_tasks(user_id)
    if not tasks:
        await message.answer("📭 У тебя пока нет задач. Добавь через '➕ Добавить задачу'.")
        return
    text = "📋 ТВОЙ ПЛАН:\n\n"
    for task in tasks:
        status = "✅" if task[3] else "⬜"
        text += f"{status} {task[1]} (id:{task[0]})\n"
    inline_kb = InlineKeyboardMarkup()
    for task in tasks:
        if not task[3]:
            inline_kb.add(InlineKeyboardButton(f"✅ {task[1][:15]}...", callback_data=f"done_{task[0]}"))
    if inline_kb.inline_keyboard:
        await message.answer(text, reply_markup=inline_kb)
    else:
        await message.answer(text + "\n\n🎯 Все задачи выполнены! Отлично!")

@dp.callback_query(lambda c: c.data.startswith("done_"))
async def callback_done(call: types.CallbackQuery):
    if not await check_subscription(call.message): 
        await call.answer("Нужна подписка", show_alert=True)
        return
    task_id = int(call.data.split("_")[1])
    user_id = call.from_user.id
    mark_done(user_id, task_id)
    await call.answer("✅ Выполнено!", show_alert=False)
    await call.message.delete()

@dp.message(lambda m: m.text == "➕ Добавить задачу")
async def add_task_prompt(message: types.Message):
    if not await check_subscription(message): return
    await message.answer("✏️ Напиши текст задачи. Можно указать категорию через ' / ' (например: Утро / Зарядка)")

@dp.message(lambda m: m.text and m.text not in ["📋 Мой план", "➕ Добавить задачу", "🍽️ Добавить еду", "💧 Вода", "🏋️ Тренировка", "📊 Статистика", "🌟 Мотивация", "💳 Подписка", "⚙️ Настройки"])
async def handle_text(message: types.Message):
    if not await check_subscription(message): return
    user_id = message.from_user.id
    text = message.text.strip()
    if " / " in text:
        category, task = text.split(" / ", 1)
    else:
        category = "Общее"
        task = text
    add_task(user_id, task, category)
    await message.answer(f"✅ Задача '{task}' добавлена в категорию '{category}'!", reply_markup=main_kb)

@dp.message(lambda m: m.text == "🍽️ Добавить еду")
async def add_meal_prompt(message: types.Message):
    if not await check_subscription(message): return
    await message.answer("🍽️ Введи приём пищи в формате:\nНазвание, калории, белки, жиры, углеводы\nПример: Гречка с яйцом, 400, 20, 10, 45")

@dp.message(lambda m: m.text and m.text not in ["📋 Мой план", "➕ Добавить задачу", "🍽️ Добавить еду", "💧 Вода", "🏋️ Тренировка", "📊 Статистика", "🌟 Мотивация", "💳 Подписка", "⚙️ Настройки"])
async def handle_meal_or_workout(message: types.Message):
    if not await check_subscription(message): return
    user_id = message.from_user.id
    # Проверяем, похоже на еду
    try:
        parts = message.text.split(',')
        if len(parts) >= 2:
            name = parts[0].strip()
            calories = int(parts[1].strip())
            protein = float(parts[2]) if len(parts) > 2 else 0
            fat = float(parts[3]) if len(parts) > 3 else 0
            carbs = float(parts[4]) if len(parts) > 4 else 0
            add_meal(user_id, name, calories, protein, fat, carbs)
            await message.answer(f"✅ Записано: {name} ({calories} ккал, б:{protein} ж:{fat} у:{carbs})", reply_markup=main_kb)
            return
    except:
        pass
    # Если не еда, считаем тренировкой
    duration = 30  # по умолчанию
    add_workout(user_id, message.text, duration)
    await message.answer(f"🏋️ Тренировка '{message.text}' засчитана (30 мин)!", reply_markup=main_kb)

@dp.message(lambda m: m.text == "💧 Вода")
async def water_menu(message: types.Message):
    if not await check_subscription(message): return
    user_id = message.from_user.id
    today = get_today_water(user_id)
    norm = get_water_norm(user_id)
    await message.answer(
        f"💧 Вода сегодня: {today} мл из {norm} мл ({int(today/norm*100)}%)\n\n"
        f"Напиши количество выпитой воды в мл (например: 250)",
        reply_markup=main_kb
    )

@dp.message(lambda m: m.text and m.text.isdigit() and int(m.text) > 0)
async def handle_water(message: types.Message):
    if not await check_subscription(message): return
    user_id = message.from_user.id
    amount = int(message.text)
    add_water(user_id, amount)
    today = get_today_water(user_id)
    norm = get_water_norm(user_id)
    await message.answer(f"✅ Добавлено {amount} мл воды. Всего сегодня: {today} мл из {norm} мл", reply_markup=main_kb)

@dp.message(lambda m: m.text == "🏋️ Тренировка")
async def workout_prompt(message: types.Message):
    if not await check_subscription(message): return
    await message.answer("🏋️ Напиши тип тренировки (например: Турники, Силовая, Бег).\nДлительность по умолчанию 30 мин.")

@dp.message(lambda m: m.text == "📊 Статистика")
async def show_stats(message: types.Message):
    if not await check_subscription(message): return
    user_id = message.from_user.id
    tasks = get_tasks(user_id)
    total = len(tasks)
    done = sum(1 for t in tasks if t[3])
    meals = get_today_meals(user_id)
    total_cal = sum(m[1] for m in meals)
    water = get_today_water(user_id)
    water_norm = get_water_norm(user_id)
    w_count = get_today_workout_count(user_id)
    stats = (
        f"📊 СТАТИСТИКА ЗА СЕГОДНЯ:\n\n"
        f"📝 Задачи: {done}/{total} выполнено\n"
        f"🍽️ Калории: {total_cal} ккал\n"
        f"💧 Вода: {water} мл из {water_norm} мл ({int(water/water_norm*100)}%)\n"
        f"🏋️ Тренировок: {w_count}\n\n"
    )
    if meals:
        stats += "🍲 Детально по еде:\n"
        for m in meals:
            stats += f"• {m[0]} – {m[1]} ккал (б:{m[2]} ж:{m[3]} у:{m[4]})\n"
    await message.answer(stats, reply_markup=main_kb)

@dp.message(lambda m: m.text == "⚙️ Настройки")
async def settings_menu(message: types.Message):
    if not await check_subscription(message): return
    user_id = message.from_user.id
    norm = get_water_norm(user_id)
    await message.answer(
        f"⚙️ НАСТРОЙКИ:\n"
        f"Норма воды: {norm} мл\n"
        f"Чтобы изменить, напиши: вода 3000 (например)",
        reply_markup=main_kb
    )

@dp.message(lambda m: m.text and m.text.startswith("вода"))
async def change_water_norm(message: types.Message):
    if not await check_subscription(message): return
    try:
        user_id = message.from_user.id
        norm = int(message.text.split()[1])
        if norm >= 1000:
            set_water_norm(user_id, norm)
            await message.answer(f"✅ Норма воды установлена: {norm} мл", reply_markup=main_kb)
        else:
            await message.answer("⚠️ Норма должна быть не менее 1000 мл.")
    except:
        await message.answer("⚠️ Неверный формат. Пример: вода 3000")

# ===== ЕЖЕДНЕВНАЯ РАССЫЛКА МОТИВАЦИИ =====
async def send_daily_motivation():
    users = get_all_users()
    for user_id, sub_end in users:
        if sub_end and datetime.fromisoformat(sub_end) > datetime.now():
            text, author = get_random_quote()
            try:
                await bot.send_message(user_id, f"🌅 ДОБРОЕ УТРО!\n\n🌟 {text}\n— {author}\n\nУдачи в новом дне! 💪")
            except:
                pass

# Планируем задачу на 7:00 каждый день
scheduler.add_job(send_daily_motivation, CronTrigger(hour=7, minute=0))
scheduler.start()

# ===== ЗАПУСК =====
if __name__ == "__main__":
    print("🚀 Бот 520 System с мотивацией запущен!")
    dp.run_polling(bot)
