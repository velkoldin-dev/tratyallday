import sqlite3
import logging
from datetime import datetime

# Название файла базы данных
DB_NAME = 'bot_database.db'

# Настраиваем логгер
logger = logging.getLogger(__name__)

def get_db_connection():
    """Создает подключение к базе данных"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Создает таблицы, если их нет"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 👇 НОВАЯ ТАБЛИЦА: расходы
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Индекс для быстрого поиска по user_id и дате
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_expenses_user_date 
        ON expenses(user_id, date)
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована (таблицы users и expenses созданы)")

def add_or_update_user(user_id, username, first_name):
    """Добавляет нового пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, last_active)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    ''', (user_id, username, first_name))
    
    conn.commit()
    conn.close()
    
    logger.info(f"👤 Пользователь {user_id} добавлен в БД")

def get_all_users():
    """Возвращает список всех пользователей"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, first_name FROM users')
    users = cursor.fetchall()
    conn.close()
    return [dict(user) for user in users]

# 👇 НОВАЯ ФУНКЦИЯ: сохранение расхода
def save_expense(user_id, amount, category, date):
    """Сохраняет расход в базу данных"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO expenses (user_id, amount, category, date)
            VALUES (?, ?, ?, ?)
        ''', (user_id, amount, category, date))
        
        conn.commit()
        logger.info(f"💰 Расход сохранен в БД: user={user_id}, amount={amount}, category={category}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения расхода: {e}")
        return False
    finally:
        conn.close()

def get_user_stats(user_id, days=1):
    """Возвращает статистику пользователя за последние N дней"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Вычисляем дату N дней назад
    from datetime import datetime, timedelta
    target_date = (datetime.now() - timedelta(days=days)).strftime("%d.%m")
    
    # Получаем все траты пользователя за период
    cursor.execute('''
        SELECT category, SUM(amount) as total
        FROM expenses
        WHERE user_id = ? AND date >= ?
        GROUP BY category
        ORDER BY total DESC
    ''', (user_id, target_date))
    
    categories = cursor.fetchall()
    conn.close()
    
    # Формируем результат
    if categories:
        total = sum(cat[1] for cat in categories)
        categories_list = [
            {'category': cat[0], 'total': cat[1]} 
            for cat in categories
        ]
        
        return {
            'has_data': True,
            'total': total,
            'categories': categories_list
        }
    else:
        return {
            'has_data': False,
            'total': 0,
            'categories': []
        }
    
# Функция для получения операций
def get_user_operations(user_id: int, limit: int = 30) -> list:
    """Получить последние операции пользователя"""
    conn = get_db_connection()  # ✅ Используем общую функцию
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT date, category, amount 
        FROM expenses 
        WHERE user_id = ? 
        ORDER BY id DESC 
        LIMIT ?
    ''', (user_id, limit))
    
    operations = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return operations
    
    # Общая сумма
    cursor.execute('''
        SELECT SUM(amount) as total
        FROM expenses
        WHERE user_id = ? AND date >= ?
    ''', (user_id, target_date))
    
    total_row = cursor.fetchone()
    total = total_row['total'] if total_row and total_row['total'] else 0
    
    conn.close()
    
    return {
        'total': total,
        'categories': [dict(cat) for cat in categories],
        'has_data': total > 0
    }
