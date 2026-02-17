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
