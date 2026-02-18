import logging
import asyncio
from datetime import datetime, timedelta, time
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
Application, CommandHandler, MessageHandler,
ConversationHandler, filters, ContextTypes
)
import os
from database import (
init_database, add_or_update_user, get_all_users,
save_expense, get_user_stats, get_user_operations,
delete_expense, get_expense_by_id # ✅ Новые функции для /fix
)

==================== НАСТРОЙКИ ====================
Переменные окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
raise ValueError("❌ Установите BOT_TOKEN в Railway Variables")

TIMEZONE_OFFSET = int(os.environ.get("TIMEZONE_OFFSET", 3))
ADMIN_ID = int(os.environ.get("ADMIN_ID", 37888528))

Логирование
logging.basicConfig(
format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
level=logging.INFO
)
logger = logging.getLogger(name)

==================== СОСТОЯНИЯ ДИАЛОГОВ ====================
Диалог добавления трат
AMOUNT, CATEGORY = range(2)

Диалог исправления трат
FIX_SELECT, FIX_ACTION, FIX_AMOUNT, FIX_CATEGORY = range(2, 6)

==================== КАТЕГОРИИ ====================
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

==================== УТИЛИТЫ ====================
def get_moscow_time():
"""Возвращает текущее время по Москве"""
from datetime import timezone
return datetime.now(timezone.utc) + timedelta(hours=TIMEZONE_OFFSET)

def format_date(dt=None):
"""Форматирует дату в DD.MM"""
if dt is None:
dt = get_moscow_time()
return dt.strftime("%d.%m")

def clean_category(category: str) -> str:
"""Убирает эмодзи из названия категории"""
return category.split(' ', 1)[1] if ' ' in category else category

def get_main_menu():
"""Клавиатура главного меню"""
keyboard = [
["💸 Добавить траты"],
["📈 Статистика", "📄 Операции"]
]
return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

==================== ЕЖЕДНЕВНЫЙ ОТЧЁТ ====================
async def send_daily_report(context: ContextTypes.DEFAULT_TYPE):
"""Отправляет ежедневный отчёт всем пользователям в 9:00 МСК"""
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
    await asyncio.sleep(0.5)  # Защита от флуда
==================== КОМАНДЫ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
"""Команда /start — приветствие и главное меню"""
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
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
"""Команда /help — справка по боту"""
await update.message.reply_text(
"📖 Помощь по боту:\n\n"
"📌 /start - главное меню\n"
"📌 /stats - статистика за сегодня\n"
"📌 /fix - исправить последние траты\n"
"📌 /myid - показать ваш user\_id\n"
"📌 /testreport - тестовый отчёт (только админ)\n"
"📌 /cancel - отменить операцию\n\n"
"Как пользоваться:\n"
"1️⃣ Нажми «💸 Добавить траты»\n"
"2️⃣ Введи сумму (например: 350)\n"
"3️⃣ Выбери категорию\n\n"
"Ежедневные отчеты:\n"
"📨 Каждый день в 9:00 (МСК) бот пришлёт отчёт о вчерашних тратах",
parse_mode="Markdown"
)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
"""Команда /stats — статистика за сегодня"""
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
        f"Пока нет трат. Используй кнопку «💸 Добавить траты»"
    )
await update.message.reply_text(message, parse_mode="Markdown")

async def operations_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
"""Команда /operations — показать последние 30 трат"""
user_id = update.effective_user.id
operations = get_user_operations(user_id, limit=30)
if not operations:
    await update.message.reply_text(
        "📭 У вас пока нет операций.\n"
        "Используй кнопку «💸 Добавить траты» для начала учёта.",
        reply_markup=get_main_menu()
    )
    return
message = "📋 Последние 30 операций:\n\n"
for op in operations:
    message += f"• {op['date']} | {op['category']} | {op['amount']:.2f} руб.\n"
await update.message.reply_text(message, reply_markup=get_main_menu())

async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
"""Команда /myid — показать user_id"""
user_id = update.effective_user.id
await update.message.reply_text(
f"📋 Ваш user\_id: {user_id}",
parse_mode="Markdown"
)

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
"""Команда /users — список всех пользователей (только админ)"""
if update.effective_user.id != ADMIN_ID:
await update.message.reply_text("❌ Эта команда только для админа")
return

sers = get_all_users()
if not users:
    await update.message.reply_text("📭 Пользователей пока нет")
    return
message = "👥 *Список пользователей:*\n\n"
for user in users:
    username = user['username'] or 'нет username'
    message += f"• {user['first_name']} (@{username}) - `{user['user_id']}`\n"
await update.message.reply_text(message, parse_mode="Markdown")

async def test_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
"""Команда /testreport — тестовая отправка отчёта (только админ)"""
if update.effective_user.id != ADMIN_ID:
await update.message.reply_text("❌ Эта команда только для админа")
return

await update.message.reply_text(
    "🔄 Отправляю тестовый отчёт...\n"
    "(Все пользователи получат отчёт за вчера)"
)
try:
    await send_daily_report(context)
    await update.message.reply_text("✅ Отчёт успешно отправлен!")
except Exception as e:
    await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    ==================== ДИАЛОГ: ДОБАВЛЕНИЕ ТРАТ ====================
async def begin_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
"""Начало диалога добавления траты"""
user = update.effective_user
add_or_update_user(
user_id=user.id,
username=user.username,
first_name=user.first_name
)

await update.message.reply_text(
    "💰 Введи сумму траты (только число, например: 1200):",
    reply_markup=ReplyKeyboardRemove()
)
return AMOUNT

async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
"""Обработчик ввода суммы"""
text = update.message.text.strip()
try:
    amount = float(text.replace(',', '.'))
    if amount <= 0:
        raise ValueError("Сумма должна быть положительной")
    context.user_data['amount'] = amount
    await update.message.reply_text(
        f"💵 Сумма: {amount:.2f} руб.\n"
        "Выбери категорию:",
        reply_markup=ReplyKeyboardMarkup(
            CATEGORIES, 
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return CATEGORY
except ValueError:
    await update.message.reply_text(
        "❌ Неверный формат! Введи число (например: 500 или 75.50):",
        reply_markup=ReplyKeyboardRemove()
    )
    return AMOUNT
    async def get_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора категории и сохранение траты"""
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
            f"📂 Категория: {clean_cat}",
            reply_markup=get_main_menu()
        )
    else:
        await update.message.reply_text(
            "❌ Ошибка при сохранении! Попробуй еще раз.",
            reply_markup=get_main_menu()
        )
    
    context.user_data.clear()
    return ConversationHandler.END
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена любого диалога"""
    await update.message.reply_text(
        "❌ Операция отменена.",
        reply_markup=get_main_menu()
    )
    context.user_data.clear()
    return ConversationHandler.END

# ==================== ДИАЛОГ: ИСПРАВЛЕНИЕ ТРАТ (/fix) ====================
async def fix_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /fix — показать последние 5 трат для исправления"""
    user_id = update.effective_user.id
    operations = get_user_operations(user_id, limit=5)
    
    if not operations:
        await update.message.reply_text(
            "📭 У тебя пока нет трат для исправления.\n"
            "Используй кнопку «💸 Добавить траты» для начала учёта.",
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END
    
    # Сохраняем список операций в контекст
    context.user_data['fix_operations'] = operations
    
    # Формируем сообщение со списком
    message = "🔧 Последние 5 трат:\n\n"
    for idx, op in enumerate(operations, start=1):
        message += (
            f"{idx}. {op['date']} | {op['category']} | "
            f"{op['amount']:.2f} руб.\n"
        )
    
    message += "\n💬 Введи номер траты (1-5):"
    
    await update.message.reply_text(
        message,
        reply_markup=ReplyKeyboardRemove()
    )
    return FIX_SELECT
async def fix_select_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора номера траты"""
    text = update.message.text.strip()
    
    try:
        number = int(text)
        operations = context.user_data.get('fix_operations', [])
        
        if number < 1 or number > len(operations):
            raise ValueError("Неверный номер")
        
        # Сохраняем выбранную трату
        selected = operations[number - 1]
        context.user_data['selected_expense'] = selected
        
        # Показываем кнопки действий
        keyboard = [
            ["🔄 Перезаписать"],
            ["🗑️ Удалить"],
            ["❌ Отмена"]
        ]
        
        await update.message.reply_text(
            f"✅ Выбрана трата:\n\n"
            f"📅 {selected['date']}\n"
            f"📂 {selected['category']}\n"
            f"💸 {selected['amount']:.2f} руб.\n\n"
            f"Что делаем?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return FIX_ACTION
        
    except (ValueError, IndexError):
        await update.message.reply_text(
            "❌ Неверный номер! Введи число от 1 до 5:",
            reply_markup=ReplyKeyboardRemove()
        )
        return FIX_SELECT

async def fix_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора действия (Удалить/Перезаписать/Отмена)"""
    action = update.message.text
    
    # ========== ОТМЕНА ==========
    if action == "❌ Отмена":
        await update.message.reply_text(
            "❌ Операция отменена.",
            reply_markup=get_main_menu()
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    # ========== УДАЛИТЬ ==========
    elif action == "🗑️ Удалить":
        selected = context.user_data.get('selected_expense')
        
        if not selected:
            await update.message.reply_text(
                "❌ Ошибка! Трата не найдена.",
                reply_markup=get_main_menu()
            )
            context.user_data.clear()
            return ConversationHandler.END
        
        # Удаляем из БД
        success = delete_expense(selected['id'])
        
        if success:
            await update.message.reply_text(
                f"✅ Трата удалена!\n\n"
                f"📅 {selected['date']}\n"
                f"📂 {selected['category']}\n"
                f"💸 {selected['amount']:.2f} руб.",
                reply_markup=get_main_menu()
            )
        else:
            await update.message.reply_text(
                "❌ Ошибка при удалении! Попробуй позже.",
                reply_markup=get_main_menu()
            )
        
        context.user_data.clear()
        return ConversationHandler.END
    
    # ========== ПЕРЕЗАПИСАТЬ ==========
    elif action == "🔄 Перезаписать":
        await update.message.reply_text(
            "💰 Введи новую сумму траты (например: 1200):",
            reply_markup=ReplyKeyboardRemove()
        )
        return FIX_AMOUNT
    
    # ========== НЕВЕРНАЯ КОМАНДА ==========
    else:
        keyboard = [
            ["🔄 Перезаписать"],
            ["🗑️ Удалить"],
            ["❌ Отмена"]
        ]
        await update.message.reply_text(
            "❌ Используй кнопки для выбора действия:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return FIX_ACTION
async def fix_get_new_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода новой суммы при перезаписи"""
    text = update.message.text.strip()
    
    try:
        amount = float(text.replace(',', '.'))
        if amount <= 0:
            raise ValueError("Сумма должна быть положительной")
        
        context.user_data['new_amount'] = amount
        
        await update.message.reply_text(
            f"💵 Новая сумма: {amount:.2f} руб.\n"
            "Выбери категорию:",
            reply_markup=ReplyKeyboardMarkup(
                CATEGORIES, 
                one_time_keyboard=True,
                resize_keyboard=True
            )
        )
        return FIX_CATEGORY
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат! Введи число (например: 500 или 75.50):",
            reply_markup=ReplyKeyboardRemove()
        )
        return FIX_AMOUNT
async def fix_get_new_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора новой категории и обновление записи"""
    category = update.message.text
    new_amount = context.user_data.get('new_amount', 0)
    selected = context.user_data.get('selected_expense')
    user_id = update.effective_user.id
    
    if not selected:
        await update.message.reply_text(
            "❌ Ошибка! Трата не найдена.",
            reply_markup=get_main_menu()
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    clean_cat = clean_category(category)
    
    # Удаляем старую запись
    delete_expense(selected['id'])
    
    # Добавляем новую
    date_today = format_date()
    success = save_expense(
        user_id=user_id,
        amount=new_amount,
        category=clean_cat,
        date=date_today
    )
    
    if success:
        await update.message.reply_text(
            f"✅ Готово! Запись обновлена:\n\n"
            f"📅 Дата: {date_today}\n"
            f"💸 Сумма: {new_amount:.2f} руб.\n"
            f"📂 Категория: {clean_cat}",
            reply_markup=get_main_menu()
        )
    else:
        await update.message.reply_text(
            "❌ Ошибка при обновлении! Попробуй позже.",
            reply_markup=get_main_menu()
        )
    
    context.user_data.clear()
    return ConversationHandler.END

# ==================== ОБРАБОТЧИК ГЛАВНОГО МЕНЮ ====================
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
            "❌ Неизвестная команда. Используй кнопки меню.",
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END

# ==================== ГЛАВНАЯ ФУНКЦИЯ ====================
def main():
    """Основная функция запуска бота"""
    init_database()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # ========== ПЛАНИРОВЩИК ЕЖЕДНЕВНЫХ ОТЧЁТОВ ==========
    job_queue = application.job_queue
    job_queue.run_daily(
        send_daily_report,
        time=time(hour=(9 - TIMEZONE_OFFSET) % 24, minute=0)
    )
    
    # ========== КОМАНДЫ ВНЕ ДИАЛОГОВ ==========
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("myid", myid_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("testreport", test_report_command))
    
    # ========== ДИАЛОГ: ДОБАВЛЕНИЕ ТРАТ ==========
    conv_handler_expense = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💸 Добавить траты$"), begin_expense),
        ],
        states={
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_category)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
        ],
    )
    
    # ========== ДИАЛОГ: ИСПРАВЛЕНИЕ ТРАТ (/fix) ==========
    conv_handler_fix = ConversationHandler(
        entry_points=[
            CommandHandler("fix", fix_start),
        ],
        states={
            FIX_SELECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fix_select_expense)
            ],
            FIX_ACTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fix_action_handler)
            ],
            FIX_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fix_get_new_amount)
            ],
            FIX_CATEGORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fix_get_new_category)
            ],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
        ],
    )
    
    # ========== РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ ==========
    application.add_handler(conv_handler_expense)
    application.add_handler(conv_handler_fix)
    
    # Обработчик кнопок меню (вне диалогов)
    application.add_handler(MessageHandler(
        filters.Regex("^(📈 Статистика|📄 Операции)$"),
        menu_handler
    ))
    
    # ========== ЗАПУСК БОТА ==========
    logger.info("=" * 50)
    logger.info("🤖 Бот учета трат запущен!")
    logger.info("⏰ Ежедневные отчеты: 9:00 по Москве")
    logger.info("💾 База данных: PostgreSQL")
    logger.info("🔧 Доступна команда /fix для исправления трат")
    logger.info("=" * 50)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)
if __name__ == '__main__':
    main()
