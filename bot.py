import logging
import requests
from datetime import datetime, timedelta
import asyncio  # 👈 ЭТА СТРОКА НОВАЯ
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ConversationHandler, filters, ContextTypes
)
import os
import csv
from collections import defaultdict
import sqlite3

from database import init_database, add_or_update_user, get_all_users, save_expense, get_user_stats

# Получаем данные из переменных окружения Railway
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ Установите BOT_TOKEN в Railway Variables")

TIMEZONE_OFFSET = int(os.environ.get("TIMEZONE_OFFSET", 3))

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Определяем этапы разговора
AMOUNT, CATEGORY = range(2)

# Категории трат с эмодзи
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

# ==================== CSV ФУНКЦИИ ====================

def get_today_date():
    """Возвращает сегодняшнюю дату в формате день.месяц по GMT+3"""
    moscow_time = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
    return moscow_time.strftime("%d.%m")

def save_expense_to_csv(date, amount, category):
    """Сохраняет трату в CSV файл (локальная копия для статистики)"""
    try:
        # Убираем эмодзи из категории
        clean_category = category.split(' ', 1)[1] if ' ' in category else category
        
        # Проверяем, существует ли файл
        file_exists = os.path.exists('expenses.csv')
        
        # Открываем файл для добавления данных
        with open('expenses.csv', 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Если файл новый, добавляем заголовки
            if not file_exists:
                writer.writerow(['Дата', 'Трата', 'Категория'])
            
            # Добавляем запись
            writer.writerow([date, f"{amount:.2f}", clean_category])
        
        logger.info(f"Сохранено в CSV: {date}, {amount} руб., {clean_category}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении в CSV: {e}")
        return False

def get_yesterday_date():
    """Возвращает вчерашнюю дату в формате день.месяц по GMT+3"""
    moscow_time = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
    yesterday = moscow_time - timedelta(days=1)
    return yesterday.strftime("%d.%m")

def get_yesterday_stats():
    """Получает статистику за вчера из CSV файла"""
    try:
        date_yesterday = get_yesterday_date()
        
        # Проверяем, существует ли файл
        if not os.path.exists('expenses.csv'):
            return {
                "date": date_yesterday,
                "total": 0,
                "top_category": "Нет трат",
                "has_data": False
            }
        
        total = 0
        category_totals = defaultdict(float)
        
        # Читаем CSV файл
        with open('expenses.csv', 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # Пропускаем заголовок
            
            for row in reader:
                if len(row) >= 3 and row[0] == date_yesterday:  # Только вчерашние
                    try:
                        amount = float(row[1])
                        category = row[2]
                        total += amount
                        category_totals[category] += amount
                    except (ValueError, TypeError):
                        continue
        
        # Определяем топ-категорию
        top_category = "Нет трат"
        if category_totals:
            top_category = max(category_totals.items(), key=lambda x: x[1])[0]
        
        return {
            "date": date_yesterday,
            "total": total,
            "top_category": top_category,
            "has_data": total > 0
        }
        
    except Exception as e:
        logger.error(f"Ошибка при чтении статистики: {e}")
        return {
            "date": get_yesterday_date(),
            "total": 0,
            "top_category": "Ошибка",
            "has_data": False
        }

# ==================== ФУНКЦИИ СОХРАНЕНИЯ ====================

def save_expense_to_db(date, amount, category, user_id):
    """Сохраняет трату в базу данных"""
    try:
        # Убираем эмодзи из категории
        clean_category = category.split(' ', 1)[1] if ' ' in category else category
        
        # Сохраняем в БД через нашу функцию
        success = save_expense(
            user_id=user_id,
            amount=amount,
            category=clean_category,
            date=date
        )
        
        if success:
            logger.info(f"💰 Данные сохранены в БД: {date}, {amount}, {clean_category}")
            return True
        else:
            logger.error("❌ Ошибка сохранения в БД")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении: {e}")
        return False

# ==================== ЕЖЕДНЕВНЫЙ ОТЧЕТ ====================

async def send_daily_report(context: ContextTypes.DEFAULT_TYPE):
    """Отправляет ежедневный отчёт ВСЕМ пользователям"""
    
    # Получаем всех пользователей из БД
    users = get_all_users()
    
    if not users:
        logger.info("📭 Нет пользователей для отчёта")
        return
    
    logger.info(f"📨 Начинаю рассылку отчётов для {len(users)} пользователей")
    
    for user in users:
        user_id = user['user_id']
        first_name = user['first_name']
        
        # Получаем статистику за вчера (days=1)
        stats = get_user_stats(user_id, days=1)
        
        # Формируем сообщение
        if stats['has_data']:
            # Берём топ-3 категории
            top_categories = stats['categories'][:3]
            categories_text = ""
            for cat in top_categories:
                categories_text += f"• {cat['category']}: {cat['total']:.2f} руб.\n"
            
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
            await context.bot.send_message(
                chat_id=user_id,
                text=message
            )
            logger.info(f"✅ Отчёт отправлен пользователю {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки пользователю {user_id}: {e}")
        
        # Небольшая задержка между отправками
        await asyncio.sleep(0.5)
        
        # ⚠️ ВАЖНО: ЗАМЕНИТЕ ЭТОТ USER_ID НА ВАШ РЕАЛЬНЫЙ!
        YOUR_USER_ID = 37888528  # <-- ЗАМЕНИТЕ НА ВАШ USER_ID!
        
        await context.bot.send_message(
            chat_id=YOUR_USER_ID,
            text=message
        )
        
        logger.info(f"📨 Отправлен ежедневный отчет для {37888528}")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке отчета: {e}")

# ==================== ОБРАБОТЧИКИ КОМАНД ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    
    user = update.effective_user
    add_or_update_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name
    )
    
    await update.message.reply_text(
        "💰 *Бот учета трат*\n\n"
        "Введите сумму траты (только число, например: 1500.50):"
    )
    return AMOUNT

async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем сумму траты от пользователя"""
    try:
        amount = float(update.message.text.replace(',', '.'))
        
        if amount <= 0:
            await update.message.reply_text(
                "Сумма должна быть положительной. Попробуйте еще раз:"
            )
            return AMOUNT
        
        # Сохраняем сумму в контексте
        context.user_data['amount'] = amount
        
        # Создаем клавиатуру с категориями
        reply_keyboard = CATEGORIES
        
        await update.message.reply_text(
            f"💵 Сумма: {amount:.2f} руб.\n"
            "Выберите категорию:",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, 
                one_time_keyboard=True,
                resize_keyboard=True
            )
        )
        return CATEGORY
    except ValueError:
        await update.message.reply_text(
            "Пожалуйста, введите число (например: 500 или 75.50). "
            "Попробуйте еще раз:"
        )
        return AMOUNT

async def get_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем категорию и сохраняем данные"""
    category = update.message.text
    amount = context.user_data.get('amount', 0)
    user_id = update.effective_user.id  # 👈 получаем ID пользователя
    
    # Получаем сегодняшнюю дату
    date_today = get_today_date()
    
    # 👇 СОХРАНЯЕМ В БД
    success = save_expense_to_db(date_today, amount, category, user_id)
    
    # 👇 ОТВЕЧАЕМ ПОЛЬЗОВАТЕЛЮ
    if success:
        await update.message.reply_text(
            f"✅ Запись добавлена!\n\n"
            f"📅 Дата: {date_today}\n"
            f"💸 Сумма: {amount:.2f} руб.\n"
            f"📂 Категория: {category}",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await update.message.reply_text(
            "❌ Ошибка при сохранении!\n\n"
            "Пожалуйста, попробуйте еще раз.",
            reply_markup=ReplyKeyboardRemove()
        )
    
    # Очищаем данные пользователя
    context.user_data.clear()
    
    # Предлагаем ввести новую трату
    await update.message.reply_text(
        "Введите сумму следующей траты (или /cancel для отмены):"
    )
    return AMOUNT

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик отмены"""
    await update.message.reply_text(
        "Операция отменена. Используйте /start для начала учета трат.",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    await update.message.reply_text(
        "*Помощь по боту:*\n\n"
        "📌 */start* - начать добавление траты\n"
        "📌 */stats* - показать статистику за сегодня\n"
        "📌 */myid* - показать ваш user_id\n"
        "📌 */help* - эта справка\n"
        "📌 */cancel* - отменить текущую операцию\n\n"
        "*Как пользоваться:*\n"
        "1. Введите сумму траты (например: 350 или 1299.50)\n"
        "2. Выберите категорию из списка\n"
        "3. Бот автоматически сохранит данные\n\n"
        "*Ежедневные отчеты:*\n"
        "📨 Каждый день в 9:00 (МСК) бот пришлет отчет о вчерашних тратах",
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику за сегодня"""
    date_today = get_today_date()
    
    # Читаем статистику за сегодня из CSV
    try:
        total_today = 0
        if os.path.exists('expenses.csv'):
            with open('expenses.csv', 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)
                
                for row in reader:
                    if len(row) >= 3 and row[0] == date_today:
                        try:
                            total_today += float(row[1])
                        except (ValueError, TypeError):
                            continue
        
        await update.message.reply_text(
            f"📊 *Статистика за сегодня ({date_today}):*\n\n"
            f"*Общие траты:* {total_today:.2f} руб.\n\n"
            "Используйте /start для добавления новой траты."
        )
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        await update.message.reply_text(
            "❌ Ошибка при получении статистики. Попробуйте позже."
        )

async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает user_id пользователя"""
    user_id = update.effective_user.id
    await update.message.reply_text(
        f"📋 *Ваш user_id:* `{user_id}`\n\n"
        f"Сохраните этот номер. Он нужен для:\n"
        f"• Настройки ежедневных отчетов\n"
        f"• Будущих уведомлений\n\n"
        f"Чтобы изменить user_id в боте, найдите в коде строку:\n"
        f"`YOUR_USER_ID = 37888528`\n"
        f"и замените `37888528` на `{user_id}`"
    )
async def test_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестовая отправка отчета прямо сейчас"""
    try:
        await update.message.reply_text("🔄 Тестирую отправку отчета...")
        
        # Импортируем нужные функции
        from datetime import datetime, timedelta
        import os
        import csv
        from collections import defaultdict
        
        # Функция для получения вчерашней даты
        def get_yesterday_date_test():
            moscow_time = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
            yesterday = moscow_time - timedelta(days=1)
            return yesterday.strftime("%d.%m")
        
        # Получаем вчерашнюю дату
        date_yesterday = get_yesterday_date_test()
        await update.message.reply_text(f"📅 Ищу данные за: {date_yesterday}")
        
        # Проверяем файл
        if not os.path.exists('expenses.csv'):
            await update.message.reply_text("❌ Файл expenses.csv не найден!")
            return
        
        # Читаем данные
        total = 0
        category_totals = defaultdict(float)
        
        with open('expenses.csv', 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                await update.message.reply_text("❌ Файл expenses.csv пустой!")
                return
            
            found = 0
            for row in reader:
                if len(row) >= 3 and row[0] == date_yesterday:
                    try:
                        amount = float(row[1])
                        category = row[2]
                        total += amount
                        category_totals[category] += amount
                        found += 1
                    except (ValueError, TypeError):
                        continue
        
        # Формируем отчет
        if total > 0:
            top_category = max(category_totals.items(), key=lambda x: x[1])[0]
            message = (
                f"✅ *Тестовый отчет:*\n\n"
                f"📅 *Дата:* {date_yesterday}\n"
                f"💰 *Сумма:* {total:.2f} руб.\n"
                f"📊 *Записей найдено:* {found}\n"
                f"🏆 *Топ-категория:* {top_category}\n\n"
                f"Если этот отчет отображается корректно,\n"
                f"ежедневные отчеты в 9:00 тоже будут работать!"
            )
        else:
            message = (
                f"ℹ️ *Тестовый отчет:*\n\n"
                f"📅 *Дата:* {date_yesterday}\n"
                f"💰 *Сумма:* 0 руб.\n"
                f"📊 *Записей найдено:* {found}\n\n"
                f"⚠️ *Внимание:* Нет данных за вчера!\n"
                f"Добавьте траты через /start, чтобы завтра\n"
                f"получить полноценный отчет."
            )
        
        await update.message.reply_text(message)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список пользователей (только для админа)"""
    # Проверяем, что это ты
    if update.effective_user.id != 37888528:
        await update.message.reply_text("❌ Эта команда только для админа")
        return
    
    users = get_all_users()
    if not users:
        await update.message.reply_text("📭 Пользователей пока нет")
        return
    
    message = "👥 *Список пользователей:*\n\n"
    for user in users:
        message += f"• {user['first_name']} (@{user['username']}) - `{user['user_id']}`\n"
    
    await update.message.reply_text(message)
# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================

def main():
    """Основная функция запуска бота"""
    init_database()
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Создаем обработчик диалога
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_category)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Добавляем обработчики
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("myid", myid_command))
    application.add_handler(CommandHandler("testreport", test_report_command)) 
    application.add_handler(CommandHandler("users", users_command))
    
    # Запускаем бота
    print("=" * 50)
    print("🤖 Бот учета трат запущен!")
    print("⏰ Ежедневные отчеты будут приходить в 9:00 по Москве или по запросу")
    print("💾 Данные сохраняются в базу данных")
    print("🆔 Напишите боту /myid чтобы узнать ваш user_id (вдруг вам интересно)")
    print("=" * 50)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
