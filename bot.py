import logging
import asyncio
from datetime import datetime, timedelta, time
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ConversationHandler, filters, ContextTypes
)
import os
from collections import defaultdict
from database import (
    init_database, add_or_update_user, get_all_users, 
    save_expense, get_user_stats
)
# Переменные окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ Установите BOT_TOKEN в Railway Variables")
TIMEZONE_OFFSET = int(os.environ.get("TIMEZONE_OFFSET", 3))
ADMIN_ID = int(os.environ.get("ADMIN_ID", 37888528))
# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
# Этапы разговора
AMOUNT, CATEGORY = range(2)
# Категории трат
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
# ==================== УТИЛИТЫ ====================
def get_moscow_time():
    """Возвращает текущее время по Москве"""
    return datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
def format_date(dt=None):
    """Форматирует дату в DD.MM"""
    if dt is None:
        dt = get_moscow_time()
    return dt.strftime("%d.%m")
def clean_category(category: str) -> str:
    """Убирает эмодзи из названия категории"""
    return category.split(' ', 1)[1] if ' ' in category else category
# ==================== ЕЖЕДНЕВНЫЙ ОТЧЁТ ====================
async def send_daily_report(context: ContextTypes.DEFAULT_TYPE):
    """Отправляет ежедневный отчёт всем пользователям"""
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
            categories_text = "\n".join(
                f"• {cat['category']}: {cat['total']:.2f} руб."
                for cat in top_categories
            )
            
            message = (
                f"☀️ Доброе утро, {first_name}!\n\n"
                f"📊 Вчера ты потратил: {stats['total']:.2f} руб.\n\n"
                f"🏆 Топ категории:\n{categories_text}"
            )
        else:
            message = (
                f"☀️ Доброе утро, {first_name}!\n\n"
                f"📊 Вчера у тебя не было трат.\n"
                f"Отличный день для экономии! 💪"
            )
        
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
            logger.info(f"✅ Отчёт отправлен пользователю {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки пользователю {user_id}: {e}")
        
        await asyncio.sleep(0.5)
# ==================== ОБРАБОТЧИКИ КОМАНД ====================
async def operations_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать последние 30 операций"""
    user_id = update.effective_user.id
    
    # Получаем операции из БД
    from database import get_user_operations  # ✅ Импорт внутри функции
    operations = get_user_operations(user_id, limit=30)
    
    if not operations:
        await update.message.reply_text(
            "📭 У вас пока нет операций.\n"
            "Используйте кнопку «Добавить траты» для начала учёта.",
            reply_markup=get_main_menu()
        )
        return
    
    # Форматируем список операций
    message = "📋 Последние 30 операций:\n\n"
    for op in operations:
        message += f"• {op['date']} | {op['category']} | {op['amount']:.2f} руб.\n"
    
    await update.message.reply_text(message, reply_markup=get_main_menu())
    
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    add_or_update_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name
    )
    
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "💰 Я помогу тебе вести учёт трат.\n"
        "Выбери действие из меню ниже:",
        reply_markup=get_main_menu()
    )
    
    await update.message.reply_text(
        "💰 Бот учета трат\n\n"
        "Выберите действие:",
        reply_markup=get_main_menu()
    )
    return ConversationHandler.END  # ✅ Изменено: выходим из диалога

async def begin_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало диалога добавления траты"""
    await update.message.reply_text(
        "💰 Введите сумму траты (только число, например: 1200):",
        reply_markup=ReplyKeyboardRemove()
    )
    return AMOUNT
    
async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем сумму траты от пользователя"""
    try:
        amount = float(update.message.text.replace(',', '.'))
        
        if amount <= 0:
            await update.message.reply_text(
                "❌ Сумма должна быть положительной. Попробуйте еще раз:"
            )
            return AMOUNT
        
        context.user_data['amount'] = amount
        
        await update.message.reply_text(
            f"💵 Сумма: {amount:.2f} руб.\n"
            "Выберите категорию:",
            reply_markup=ReplyKeyboardMarkup(
                CATEGORIES, 
                one_time_keyboard=True,
                resize_keyboard=True
            )
        )
        return CATEGORY
        
    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введите число (например: 500 или 75.50).\n"
            "Попробуйте еще раз:"
        )
        return AMOUNT
async def get_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем категорию и сохраняем данные"""
    category = update.message.text
    amount = context.user_data.get('amount', 0)
    user_id = update.effective_user.id
    
    date_today = format_date()
    clean_cat = clean_category(category)
    
    success = save_expense(
        user_id=user_id,
        amount=amount,
        category=clean_cat,
        date=date_today
    )
    
    if success:
        await update.message.reply_text(
            f"✅ Запись добавлена!\n\n"
            f"📅 Дата: {date_today}\n"
            f"💸 Сумма: {amount:.2f} руб.\n"
            f"📂 Категория: {clean_cat}"
        )
    else:
        await update.message.reply_text(
            "❌ Ошибка при сохранении! Попробуйте еще раз."
        )
    
    context.user_data.clear()
    
    # ✅ Возвращаемся в главное меню
    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=get_main_menu()
    )
    return ConversationHandler.END # ✅ Возвращаемся в меню 
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик отмены"""
    await update.message.reply_text(
        "❌ Операция отменена. Используйте /start для начала учета трат.",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    await update.message.reply_text(
        "*Помощь по боту:*\n\n"
        "📌 /start - начать добавление трат\n"
        "📌 /stats - показать статистику за сегодня\n"
        "📌 /myid - показать ваш user_id\n"
        "📌 /testreport - протестировать отчёт (отправить сейчас)\n"
        "📌 /help - эта справка\n"
        "📌 /cancel - отменить текущую операцию\n\n"
        "*Как пользоваться:*\n"
        "1. Введите сумму траты (например: 350)\n"
        "2. Выберите категорию из списка\n"
        "3. Бот автоматически сохранит данные\n\n"
        "*Ежедневные отчеты:*\n"
        "📨 Каждый день в 9:00 (МСК) бот пришлет отчет о вчерашних тратах",
    )
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику за сегодня"""
    user_id = update.effective_user.id
    stats = get_user_stats(user_id, days=0)
    
    date_today = format_date()
    
    if stats['has_data']:
        top_categories = stats['categories'][:3]
        categories_text = "\n".join(
            f"• {cat['category']}: {cat['total']:.2f} руб."
            for cat in top_categories
        )
        
        message = (
            f"📊 *Статистика за сегодня ({date_today}):*\n\n"
            f"💰 Общие траты: {stats['total']:.2f} руб.\n\n"
            f"🏆 Топ категории:\n{categories_text}"
        )
    else:
        message = (
            f"📊 *Статистика за сегодня ({date_today}):*\n\n"
            f"💰 Общие траты: 0 руб.\n\n"
            f"Пока нет трат. Используйте /start для добавления."
        )
    
    await update.message.reply_text(message)
async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает user_id пользователя"""
    user_id = update.effective_user.id
    await update.message.reply_text(
        f"📋 *Ваш user\\_id:* `{user_id}`\n\nПоздравляю :\\)",
    )
async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список пользователей (только для админа)"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Эта команда только для админа")
        return
    
    users = get_all_users()
    if not users:
        await update.message.reply_text("📭 Пользователей пока нет")
        return
    
    message = "👥 *Список пользователей:*\n\n"
    for user in users:
        username = user['username'] or 'нет username'
        message += f"• {user['first_name']} (@{username}) - `{user['user_id']}`\n"
    
    await update.message.reply_text(message)
async def test_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестовая отправка отчёта прямо сейчас"""
    await update.message.reply_text(
        "🔄 Отправляю тестовый отчёт...\n"
        "(Все пользователи получат отчёт за вчера)"
    )
    
    try:
        await send_daily_report(context)
        await update.message.reply_text(
            "✅ Отчёт успешно отправлен!\n"
            "Проверь, что все пользователи получили сообщение."
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при отправке: {str(e)}")
        logger.error(f"Ошибка в test_report_command: {e}")

# ==================== ГЛАВНОЕ МЕНЮ ====================
def get_main_menu():
    """Возвращает клавиатуру главного меню"""
    keyboard = [
        ["💸 Добавить траты"],
        ["📈 Статистика", "📄 Операции"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок главного меню"""
    text = update.message.text
    
    if text == "💸 Добавить траты":
        return await begin_expense(update, context)
    
    elif text == "📈 Статистика":
        await stats_command(update, context)
        return ConversationHandler.END
    
    elif text == "📄 Операции":
        await operations_command(update, context)
        return ConversationHandler.END
    
    else:
        await update.message.reply_text(
            "❌ Неизвестная команда. Используйте кнопки меню.",
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END

def main():
    """Основная функция запуска бота"""
    init_database()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # ✅ ПЛАНИРОВЩИК ЕЖЕДНЕВНЫХ ОТЧЁТОВ
    job_queue = application.job_queue
    job_queue.run_daily(
        send_daily_report,
        time=time(hour=(9 - TIMEZONE_OFFSET) % 24, minute=0)
    )
def main():
    """Основная функция запуска бота"""
    init_database()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # ✅ ПЛАНИРОВЩИК ЕЖЕДНЕВНЫХ ОТЧЁТОВ
    job_queue = application.job_queue
    job_queue.run_daily(
        send_daily_report,
        time=time(hour=(9 - TIMEZONE_OFFSET) % 24, minute=0)
    )
    
    # ✅ Команда /start (вне диалога)
    application.add_handler(CommandHandler("start", start))
    
    # Диалог добавления трат
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💸 Добавить траты$"), begin_expense),
        ],
        states={
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_category)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CommandHandler('help', help_command),
            CommandHandler('stats', stats_command),
            CommandHandler('myid', myid_command),
        ],
    )

    # Диалог добавления трат
conv_handler = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex("^💸 Добавить траты$"), begin_expense),  # ✅ Напрямую
    ],
        states={
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_category)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CommandHandler('help', help_command),
            CommandHandler('stats', stats_command),
            CommandHandler('myid', myid_command),
        ],
    )
    
    # Регистрация обработчиков
    application.add_handler(conv_handler)
    
    # Обработчик кнопок меню (вне диалога)
    application.add_handler(MessageHandler(
        filters.Regex("^(📈 Статистика|📄 Операции)$"),  # ✅ Исправлены эмодзи
        menu_handler
    ))
    
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("myid", myid_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("testreport", test_report_command))
    
    logger.info("=" * 50)
    logger.info("🤖 Бот учета трат запущен!")
    logger.info("⏰ Ежедневные отчеты будут приходить в 9:00 по Москве")
    logger.info("💾 Данные сохраняются в базу данных")
    logger.info("🧪 Для теста используйте команду /testreport")
    logger.info("=" * 50)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)
if __name__ == '__main__':
    main()
