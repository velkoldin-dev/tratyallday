import logging
import asyncio
import os
from datetime import datetime, timedelta, time
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, filters, ContextTypes, InlineQueryHandler
)
from database import (
    init_database, add_or_update_user, get_all_users,
    save_expense, get_user_stats, get_user_operations,
    delete_expense, get_expense_by_id
)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ Установите BOT_TOKEN в Railway Variables")
TIMEZONE_OFFSET = int(os.environ.get("TIMEZONE_OFFSET", 3))
ADMIN_ID = int(os.environ.get("ADMIN_ID", 37888528))
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
from PIL import Image, ImageDraw, ImageFont
import random
COFFEE_DIR = "coffee_templates"
COFFEE_PRICE = 213
def get_random_coffee_template():
    if not os.path.exists(COFFEE_DIR):
        raise FileNotFoundError(f"❌ Папка {COFFEE_DIR} не найдена!")
    templates = [f for f in os.listdir(COFFEE_DIR) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
    if not templates:
        raise FileNotFoundError(f"❌ Нет картинок в папке {COFFEE_DIR}/")
    return os.path.join(COFFEE_DIR, random.choice(templates))
def get_coffee_emoji(cups: int) -> str:
    if cups <= 10:
        return "❤️"
    elif cups <= 50:
        return "👍"
    elif cups <= 100:
        return "🤯"
    else:
        return "😱"
def calculate_coffee_index(amount: float) -> dict:
    cups = round(amount / COFFEE_PRICE)
    emoji = get_coffee_emoji(cups)
    return {'cups': cups, 'emoji': emoji, 'amount': amount}
    
def generate_coffee_image(date: str, cups: int, emoji: str, output_path: str = "coffee_output.jpg") -> str:
    try:
        template_path = get_random_coffee_template()
        logger.info(f"☕ Используется шаблон: {template_path}")
        
        img = Image.open(template_path).convert("RGB")
        if img.size != (1000, 1000):
            img = img.resize((1000, 1000), Image.Resampling.LANCZOS)
        
        draw = ImageDraw.Draw(img)
        
        # Текст одной строкой
        text = f"Мои траты за {date} – это {cups} чашек кофе"
        
        # 👇 ШРИФТ ИЗ GIT-репозитория
        font_path = os.path.join(os.path.dirname(__file__), "fonts", "Arial.ttf")
        
        font_size = 43
        font = ImageFont.truetype(font_path, font_size)
        logger.info(f"✅ Arial загружен из репозитория")
        
        # Позиция: СВЕРХУ (y=140)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (1000 - text_width) / 2
        y = 140
        
        # Черный текст
        draw.text((x, y), text, font=font, fill="black")
        
        img.save(output_path, quality=95)
        logger.info(f"✅ Картинка готова: {output_path}")
        
        return output_path
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        logger.exception("Traceback:")
        raise
        
AMOUNT, CATEGORY = range(2)
FIX_SELECT, FIX_ACTION, FIX_AMOUNT, FIX_CATEGORY = range(2, 6)
CATEGORIES = [
    ["🛒 Супермаркеты и продукты питания"],
    ["🍽️ Рестораны и кафе"],
    ["🚕 Транспорт"],
    ["📦 Онлайн-шопинг"],
    ["🎭 Развлечения"],
    ["📱 Связь и интернет"],
    ["💅 Красота и уход"],
    ["💪 Фитнес и здоровье"],
    ["📌 Другое"]
]
def get_moscow_time():
    from datetime import timezone
    return datetime.now(timezone.utc) + timedelta(hours=TIMEZONE_OFFSET)
def format_date(dt=None):
    """Форматирует дату в ГГГГ-ММ-ДД для БД"""
    if dt is None:
        dt = get_moscow_time()
    return dt.strftime("%Y-%m-%d")
def clean_category(category: str) -> str:
    return category.split(' ', 1)[1] if ' ' in category else category
def get_main_menu():
    keyboard = [
        ["💸 Добавить траты"],
        ["📈 Статистика", "📄 Операции"],
        ["☕ Индекс кофе"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
async def send_daily_report(context: ContextTypes.DEFAULT_TYPE):
    users = get_all_users()
    if not users:
        logger.info("📭 Нет пользователей для отчёта")
        return
    logger.info(f"📨 Начинаю рассылку отчётов для {len(users)} пользователей")
    for user in users:
        user_id = user['user_id']
        first_name = user['first_name']
        stats = get_user_stats(user_id, days=1)
        if stats['has_data']:
            top_categories = stats['categories'][:3]
            categories_text = "\n".join(f"• {cat['category']}: {cat['total']:.2f} руб." for cat in top_categories)
            message = (f"☀️ Доброе утро, {first_name}!\n\n"
                      f"📊 Вчера ты потратил: {stats['total']:.2f} руб.\n\n"
                      f"🏆 Топ категории:\n{categories_text}")
            keyboard = [["☕ Индекс кофе"], ["🔙 Главное меню"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        else:
            message = (f"☀️ Доброе утро, {first_name}!\n\n"
                      f"📊 Вчера у тебя не было трат.\n"
                      f"Отличный день для экономии! 💪")
            reply_markup = get_main_menu()
        try:
            await context.bot.send_message(chat_id=user_id, text=message, reply_markup=reply_markup)
            logger.info(f"✅ Отчёт отправлен пользователю {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки пользователю {user_id}: {e}")
        await asyncio.sleep(0.5)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_or_update_user(user_id=user.id, username=user.username, first_name=user.first_name)
    logger.info("=" * 50)
    logger.info("🔍 ПРОВЕРКА ФАЙЛОВОЙ СИСТЕМЫ:")
    logger.info(f"📂 Текущая директория: {os.getcwd()}")
    logger.info(f"📄 Содержимое корня: {os.listdir('.')}")
    if os.path.exists('coffee_templates'):
        coffee_files = os.listdir('coffee_templates')
        logger.info(f"✅ Папка coffee_templates найдена!")
        logger.info(f"📁 Файлов внутри: {len(coffee_files)}")
        logger.info(f"📄 Список: {coffee_files}")
    else:
        logger.error("❌ Папка coffee_templates НЕ НАЙДЕНА!")
    logger.info("=" * 50)
    await update.message.reply_text(f"👋 Привет, {user.first_name}!\n\n💰 Я помогу тебе вести учёт трат.\nВыбери действие из меню ниже:", reply_markup=get_main_menu())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Помощь по боту:\n\n"
        "📌 /start - главное меню\n"
        "📌 /stats - статистика за сегодня\n"
        "📌 /fix - исправить последние траты\n"
        "📌 /myid - показать ваш user_id\n"
        "📌 /testreport - тестовый отчёт (только админ)\n"
        "📌 /cancel - отменить операцию\n\n"
        "Как пользоваться:\n"
        "1️⃣ Нажми «💸 Добавить траты»\n"
        "2️⃣ Введи сумму (например: 350)\n"
        "3️⃣ Выбери категорию\n\n"
        "Ежедневные отчеты:\n"
        "📨 Каждый день в 9:00 (МСК) бот пришлёт отчёт о вчерашних тратах"
    )
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats = get_user_stats(user_id, days=0)
    date_today = format_date()
    if stats['has_data']:
        top_categories = stats['categories'][:3]
        categories_text = "\n".join(f"• {cat['category']}: {cat['total']:.2f} руб." for cat in top_categories)
        message = f"📊 Статистика за сегодня ({date_today}):\n\n💰 Общие траты: {stats['total']:.2f} руб.\n\n🏆 Топ категории:\n{categories_text}"
    else:
        message = f"📊 Статистика за сегодня ({date_today}):\n\n💰 Общие траты: 0 руб.\n\nПока нет трат. Используй кнопку «💸 Добавить траты»"
    await update.message.reply_text(message)
async def operations_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    operations = get_user_operations(user_id, limit=30)
    if not operations:
        await update.message.reply_text("📭 У вас пока нет операций.\nИспользуй кнопку «💸 Добавить траты» для начала учёта.", reply_markup=get_main_menu())
        return
    message = "📋 Последние 30 операций:\n\n"
    for op in operations:
        message += f"• {op['date']} | {op['category']} | {op['amount']:.2f} руб.\n"
    keyboard = [["🔧 Редактировать"], ["🔙 Главное меню"]]
    await update.message.reply_text(message, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(f"📋 Ваш user_id: {user_id}")
async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Эта команда только для админа")
        return
    users = get_all_users()
    if not users:
        await update.message.reply_text("📭 Пользователей пока нет")
        return
    message = "👥 Список пользователей:\n\n"
    for user in users:
        username = user['username'] or 'нет username'
        message += f"• {user['first_name']} (@{username}) - {user['user_id']}\n"
    await update.message.reply_text(message)
async def test_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Эта команда только для админа")
        return
    await update.message.reply_text("🔄 Отправляю тестовый отчёт...\n(Все пользователи получат отчёт за вчера)")
    try:
        await send_daily_report(context)
        await update.message.reply_text("✅ Отчёт успешно отправлен!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        logger.error(f"Ошибка в test_report_command: {e}")
async def coffee_test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("🧪 КОМАНДА /coffeetest ВЫЗВАНА!")
    user_id = update.effective_user.id
    stats = get_user_stats(user_id, days=0)
    logger.info(f"📊 Статистика: {stats}")
    if not stats['has_data']:
        await update.message.reply_text("☕ Нет трат за сегодня! Добавь траты сначала.", reply_markup=get_main_menu())
        return
    try:
        coffee_data = calculate_coffee_index(stats['total'])
        await update.message.reply_text("⏳ Готовлю индекс кофе...")
        today = datetime.now().strftime("%d.%m")
        image_path = generate_coffee_image(date=today, cups=coffee_data['cups'], emoji=coffee_data['emoji'])
        share_button = InlineKeyboardButton("📤 Поделиться", switch_inline_query="Слежу за тратами в боте @tratyallday_bot и вот что он мне рассказал 😄")
        inline_keyboard = InlineKeyboardMarkup([[share_button]])
        with open(image_path, 'rb') as photo:
            await update.message.reply_photo(photo=photo, caption=f"☕ Твои траты за {today} = {coffee_data['cups']} чашек кофе {coffee_data['emoji']}", reply_markup=inline_keyboard)
        await update.message.reply_text("Выбери действие:", reply_markup=get_main_menu())
        os.remove(image_path)
        logger.info("✅ Тестовый индекс кофе отправлен")
    except Exception as e:
        logger.error(f"❌ Ошибка генерации индекса кофе: {e}")
        logger.exception("Traceback:")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}", reply_markup=get_main_menu())

async def begin_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_or_update_user(user_id=user.id, username=user.username, first_name=user.first_name)
    await update.message.reply_text("💰 Введи сумму траты (только число, например: 1200):", reply_markup=ReplyKeyboardRemove())
    return AMOUNT
async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        amount = float(text.replace(',', '.'))
        if amount <= 0:
            raise ValueError("Сумма должна быть положительной")
        context.user_data['amount'] = amount
        await update.message.reply_text(f"💵 Сумма: {amount:.2f} руб.\nВыбери категорию:", reply_markup=ReplyKeyboardMarkup(CATEGORIES, one_time_keyboard=True, resize_keyboard=True))
        return CATEGORY
    except ValueError:
        await update.message.reply_text("❌ Неверный формат! Введи число (например: 500 или 75.50):", reply_markup=ReplyKeyboardRemove())
        return AMOUNT
async def get_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = update.message.text
    amount = context.user_data.get('amount', 0)
    user_id = update.effective_user.id
    date_today = format_date()
    clean_cat = clean_category(category)
    success = save_expense(user_id=user_id, amount=amount, category=clean_cat, date=date_today)
    if success:
        await update.message.reply_text(f"✅ Запись добавлена!\n\n📅 Дата: {date_today}\n💸 Сумма: {amount:.2f} руб.\n📂 Категория: {clean_cat}", reply_markup=get_main_menu())
    else:
        await update.message.reply_text("❌ Ошибка при сохранении! Попробуй еще раз.", reply_markup=get_main_menu())
    context.user_data.clear()
    return ConversationHandler.END
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Операция отменена.", reply_markup=get_main_menu())
    context.user_data.clear()
    return ConversationHandler.END
async def coffee_index_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Индекс кофе'"""
    user_id = update.effective_user.id
    stats = get_user_stats(user_id, days=1)

    if not stats['has_data']:
        await update.message.reply_text(
            "☕ У тебя не было трат вчера, поэтому индекс кофе равен 0!",
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END

    try:
        coffee_data = calculate_coffee_index(stats['total'])
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%d.%m")

        # Генерируем картинку
        image_path = generate_coffee_image(
            date=yesterday,
            cups=coffee_data['cups'],
            emoji=coffee_data['emoji']
        )

        # 👇 БЛОК ДЛЯ КАНАЛА (получение file_id)
        CHANNEL_ID = -1003897413238  # ID МОЕГО ПРИВАТНОГО ТЕХНИЧЕСКОГО КАНАЛА
        
        # Открываем файл и отправляем в канал
        with open(image_path, 'rb') as photo:
            channel_message = await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=photo
            )
        
        # Получаем file_id (последняя версия фото — самая большая)
        photo_file_id = channel_message.photo[-1].file_id
        logger.info(f"✅ Получен file_id для канала: {photo_file_id}")
        
        # Можно сохранить в context.bot_data или в БД
        context.bot_data['coffee_file_id'] = photo_file_id
        # 👆 КОНЕЦ БЛОКА

        # Кнопка для инлайн-шеринга (используем file_id)
        share_button = InlineKeyboardButton(
            "📤 Поделиться",
            switch_inline_query=""
        )
        inline_keyboard = InlineKeyboardMarkup([[share_button]])

        # Отправляем пользователю
        with open(image_path, 'rb') as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=f"☕ Твои траты за {yesterday} = {coffee_data['cups']} чашек кофе {coffee_data['emoji']}",
                reply_markup=inline_keyboard
            )

        await update.message.reply_text(
            "Выбери действие:",
            reply_markup=get_main_menu()
        )

        # Удаляем временный файл
        os.remove(image_path)

    except Exception as e:
        logger.error(f"❌ Ошибка генерации индекса кофе: {e}")
        await update.message.reply_text(
            "❌ Ошибка генерации. Попробуй позже!",
            reply_markup=get_main_menu()
        )

    return ConversationHandler.END

# ==================== INLINE-ОБРАБОТЧИК ====================

async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик инлайн-запросов (когда жмут Поделиться)"""
    query = update.inline_query.query
    user_id = update.effective_user.id
    
    try:
        photo_file_id = context.bot_data.get('coffee_file_id')
        
        if not photo_file_id:
            await update.inline_query.answer([], cache_time=60)
            return
        
        result = InlineQueryResultCachedPhoto(
            id="1",
            photo_file_id=photo_file_id,
            title="Мой индекс кофе ☕",
            description="Нажми, чтобы поделиться картинкой с друзьями"
        )
        
        results = [result]
        await update.inline_query.answer(results, cache_time=10)
        logger.info(f"✅ Inline-запрос обработан для пользователя {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка inline-запроса: {e}")
        logger.exception("Traceback:")
        await update.inline_query.answer([], cache_time=0)
        
async def fix_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    operations = get_user_operations(user_id, limit=5)
    if not operations:
        await update.message.reply_text("📭 У тебя пока нет трат для исправления.\nИспользуй кнопку «💸 Добавить траты» для начала учёта.", reply_markup=get_main_menu())
        return ConversationHandler.END
    context.user_data['fix_operations'] = operations
    message = "🔧 Последние 5 трат:\n\n"
    for idx, op in enumerate(operations, start=1):
        message += f"{idx}. {op['date']} | {op['category']} | {op['amount']:.2f} руб.\n"
    message += "\n💬 Введи номер траты (1-5):"
    await update.message.reply_text(message, reply_markup=ReplyKeyboardRemove())
    return FIX_SELECT
async def fix_select_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        number = int(text)
        operations = context.user_data.get('fix_operations', [])
        if number < 1 or number > len(operations):
            raise ValueError("Неверный номер")
        selected = operations[number - 1]
        context.user_data['selected_expense'] = selected
        keyboard = [["🔄 Перезаписать"], ["🗑️ Удалить"], ["❌ Отмена"]]
        await update.message.reply_text(f"✅ Выбрана трата:\n\n📅 {selected['date']}\n📂 {selected['category']}\n💸 {selected['amount']:.2f} руб.\n\nЧто делаем?", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return FIX_ACTION
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Неверный номер! Введи число от 1 до 5:", reply_markup=ReplyKeyboardRemove())
        return FIX_SELECT
async def fix_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = update.message.text
    if action == "❌ Отмена":
        await update.message.reply_text("❌ Операция отменена.", reply_markup=get_main_menu())
        context.user_data.clear()
        return ConversationHandler.END
    elif action == "🗑️ Удалить":
        selected = context.user_data.get('selected_expense')
        if not selected:
            await update.message.reply_text("❌ Ошибка! Трата не найдена.", reply_markup=get_main_menu())
            context.user_data.clear()
            return ConversationHandler.END
        success = delete_expense(selected['id'])
        if success:
            await update.message.reply_text(f"✅ Трата удалена!\n\n📅 {selected['date']}\n📂 {selected['category']}\n💸 {selected['amount']:.2f} руб.", reply_markup=get_main_menu())
        else:
            await update.message.reply_text("❌ Ошибка при удалении! Попробуй позже.", reply_markup=get_main_menu())
        context.user_data.clear()
        return ConversationHandler.END
    elif action == "🔄 Перезаписать":
        await update.message.reply_text("💰 Введи новую сумму траты (например: 1200):", reply_markup=ReplyKeyboardRemove())
        return FIX_AMOUNT
    else:
        keyboard = [["🔄 Перезаписать"], ["🗑️ Удалить"], ["❌ Отмена"]]
        await update.message.reply_text("❌ Используй кнопки для выбора действия:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return FIX_ACTION
async def fix_get_new_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        amount = float(text.replace(',', '.'))
        if amount <= 0:
            raise ValueError("Сумма должна быть положительной")
        context.user_data['new_amount'] = amount
        await update.message.reply_text(f"💵 Новая сумма: {amount:.2f} руб.\nВыбери категорию:", reply_markup=ReplyKeyboardMarkup(CATEGORIES, one_time_keyboard=True, resize_keyboard=True))
        return FIX_CATEGORY
    except ValueError:
        await update.message.reply_text("❌ Неверный формат! Введи число (например: 500 или 75.50):", reply_markup=ReplyKeyboardRemove())
        return FIX_AMOUNT
async def fix_get_new_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = update.message.text
    new_amount = context.user_data.get('new_amount', 0)
    selected = context.user_data.get('selected_expense')
    user_id = update.effective_user.id
    if not selected:
        await update.message.reply_text("❌ Ошибка! Трата не найдена.", reply_markup=get_main_menu())
        context.user_data.clear()
        return ConversationHandler.END
    clean_cat = clean_category(category)
    delete_expense(selected['id'])
    date_today = format_date()
    success = save_expense(user_id=user_id, amount=new_amount, category=clean_cat, date=date_today)
    if success:
        await update.message.reply_text(f"✅ Готово! Запись обновлена:\n\n📅 Дата: {date_today}\n💸 Сумма: {new_amount:.2f} руб.\n📂 Категория: {clean_cat}", reply_markup=get_main_menu())
    else:
        await update.message.reply_text("❌ Ошибка при обновлении! Попробуй позже.", reply_markup=get_main_menu())
    context.user_data.clear()
    return ConversationHandler.END

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "💸 Добавить траты":
        return await begin_expense(update, context)
    elif text == "📈 Статистика":
        await stats_command(update, context)
        return ConversationHandler.END
    elif text == "📄 Операции":
        await operations_command(update, context)
        return ConversationHandler.END
    elif text == "☕ Индекс кофе":
        return await coffee_index_handler(update, context)
    elif text == "🔙 Главное меню":
        await update.message.reply_text("Выбери действие:", reply_markup=get_main_menu())
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ Неизвестная команда. Используй кнопки меню.", reply_markup=get_main_menu())
        return ConversationHandler.END
def main():
    init_database()
    application = Application.builder().token(BOT_TOKEN).build()
    job_queue = application.job_queue
    job_queue.run_daily(send_daily_report, time=time(hour=(9 - TIMEZONE_OFFSET) % 24, minute=0))
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("myid", myid_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("testreport", test_report_command))
    application.add_handler(CommandHandler("coffeetest", coffee_test_command))
    
    conv_handler_expense = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💸 Добавить траты$"), begin_expense)],
        states={
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_category)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    conv_handler_fix = ConversationHandler(
        entry_points=[
            CommandHandler("fix", fix_start),
            MessageHandler(filters.Regex("^🔧 Редактировать$"), fix_start),
        ],
        states={
            FIX_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, fix_select_expense)],
            FIX_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, fix_action_handler)],
            FIX_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, fix_get_new_amount)],
            FIX_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, fix_get_new_category)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    application.add_handler(conv_handler_expense)
    application.add_handler(conv_handler_fix)
    application.add_handler(MessageHandler(filters.Regex("^(📈 Статистика|📄 Операции|☕ Индекс кофе|🔙 Главное меню)$"), menu_handler))
    application.add_handler(InlineQueryHandler(inline_query_handler))

    logger.info("=" * 50)
    logger.info("🤖 Бот учета трат запущен! v2.1 COFFEE UPDATE")
    logger.info("⏰ Ежедневные отчеты: 9:00 по Москве")
    logger.info("💾 База данных: PostgreSQL")
    logger.info("🔧 Доступна команда /fix для исправления трат")
    logger.info("☕ Доступна функция 'Индекс кофе'")
    logger.info("=" * 50)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)
if __name__ == '__main__':
    main()
