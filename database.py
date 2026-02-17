import sqlite3
import logging
from datetime import datetime

# Название файла базы данных
DB_NAME = 'bot_database.db'

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
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

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
    
    # Создаем логгер внутри функции, чтобы избежать ошибки импорта
    logger = logging.getLogger(__name__)
    logger.info(f"👤 Пользователь {user_id} добавлен в БД")

def get_all_users():
    """Возвращает список всех пользователей"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, first_name FROM users')
    users = cursor.fetchall()
    conn.close()
    return [dict(user) for user in users]
