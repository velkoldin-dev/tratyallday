# daily_report.py - отдельный файл для отправки ежедневных отчетов всем пользователям
import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta
import requests
from pathlib import Path

# Добавляем путь к проекту, чтобы импортировать наши модули
sys.path.append(str(Path(__file__).parent))

# Импортируем ТОЛЬКО функции из базы данных (НЕ импортируем bot.py!)
from database import get_all_users, get_user_stats, init_database

# Получаем токен из переменных окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ Установите BOT_TOKEN в переменные окружения Railway")
    sys.exit(1)

# Настройка логирования для этого файла (СВОЙ логгер, не из bot.py)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def send_daily_reports():
    """Отправляет ежедневные отчеты всем пользователям"""
    
    logger.info("🚀 Запуск ежедневной рассылки отчетов...")
    
    # Инициализируем базу данных (на всякий случай)
    init_database()
    
    # Получаем всех пользователей
    users = get_all_users()
    
    if not users:
        logger.info("📭 Нет пользователей для рассылки")
        return
    
    logger.info(f"📨 Начинаю рассылку для {len(users)} пользователей")
    
    successful = 0
    failed = 0
    
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
            
            # Вчерашняя дата для заголовка
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%d.%m")
            
            message = (
                f"☀️ Доброе утро, {first_name}!\n\n"
                f"📊 За вчера ({yesterday}) ты потратил: {stats['total']:.2f} руб.\n\n"
                f"🏆 Топ категории:\n{categories_text}\n"
                f"Хорошего дня! 💫"
            )
        else:
            message = (
                f"☀️ Доброе утро, {first_name}!\n\n"
                f"📊 Вчера у тебя не было трат.\n"
                f"Отличный день для экономии! 💪"
            )
        
        # Отправляем через Telegram API
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            data = {
                "chat_id": user_id,
                "text": message
                # parse_mode не используем, чтобы избежать ошибок
            }
            
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"✅ Отчёт отправлен пользователю {user_id} ({first_name})")
                successful += 1
            else:
                logger.error(f"❌ Ошибка отправки пользователю {user_id}: {response.status_code}")
                failed += 1
                
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке пользователю {user_id}: {e}")
            failed += 1
        
        # Небольшая задержка, чтобы не спамить Telegram
        await asyncio.sleep(0.3)
    
    logger.info(f"📊 Рассылка завершена: успешно={successful}, ошибок={failed}")

def main():
    """Точка входа"""
    try:
        asyncio.run(send_daily_reports())
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
