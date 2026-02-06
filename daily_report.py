# daily_report.py - отдельный файл для отправки отчета
import os
import sys
import requests
from datetime import datetime, timedelta
import csv
from collections import defaultdict

# Получаем переменные из окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")  # Ваш user_id из Telegram
TIMEZONE_OFFSET = int(os.environ.get("TIMEZONE_OFFSET", 3))

def get_yesterday_date():
    """Возвращает вчерашнюю дату"""
    moscow_time = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
    yesterday = moscow_time - timedelta(days=1)
    return yesterday.strftime("%d.%m")

def get_yesterday_stats():
    """Получает статистику за вчера"""
    try:
        date_yesterday = get_yesterday_date()
        
        if not os.path.exists('expenses.csv'):
            return {"total": 0, "top_category": "Нет трат"}
        
        total = 0
        category_totals = defaultdict(float)
        
        with open('expenses.csv', 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)
            
            for row in reader:
                if len(row) >= 3 and row[0] == date_yesterday:
                    try:
                        amount = float(row[1])
                        category = row[2]
                        total += amount
                        category_totals[category] += amount
                    except (ValueError, TypeError):
                        continue
        
        top_category = "Нет трат"
        if category_totals:
            top_category = max(category_totals.items(), key=lambda x: x[1])[0]
        
        return {
            "date": date_yesterday,
            "total": total,
            "top_category": top_category
        }
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return {"date": get_yesterday_date(), "total": 0, "top_category": "Ошибка"}

def send_telegram_message():
    """Отправляет сообщение в Telegram"""
    try:
        stats = get_yesterday_stats()
        
        if stats["total"] > 0:
            message = (
                f"☀️ *Доброе утро!*\n\n"
                f"📊 *Вчера ({stats['date']}) ты потратил:* {stats['total']:.2f} руб.\n"
                f"🏆 *Больше всего в категории:* {stats['top_category']}\n\n"
                f"Хорошего дня! 💫"
            )
        else:
            message = (
                f"☀️ *Доброе утро!*\n\n"
                f"📊 *Вчера ({stats['date']}) у тебя не было трат.*\n\n"
                f"Отличное начало дня! 🌟"
            )
        
        # Отправляем сообщение
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(url, json=data)
        
        if response.status_code == 200:
            print(f"✅ Отчет отправлен для {stats['date']}")
            return True
        else:
            print(f"❌ Ошибка отправки: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        return False

if __name__ == "__main__":
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Установите BOT_TOKEN и CHAT_ID в переменные окружения Railway")
        sys.exit(1)
    
    print(f"📅 Запуск ежедневного отчета...")
    success = send_telegram_message()
    sys.exit(0 if success else 1)
