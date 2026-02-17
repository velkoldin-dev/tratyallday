import sqlite3
import os
from datetime import datetime, timedelta

# Название файла базы данных
DB_NAME = 'bot_database.db'

def get_db_connection():
    """Создает подключение к базе данных"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Чтобы обращаться к колонкам по имени
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
    
    # Индекс для быстрого поиска по user_id
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id)
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована (таблица users создана)")

def add_or_update_user(user_id, username, first_name):
    """Добавляет нового пользователя или обновляет время активности существующего"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # INSERT OR REPLACE - если пользователь есть, обновляем, если нет - вставляем
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, last_active)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    ''', (user_id, username, first_name))
    
    conn.commit()
    conn.close()
    logger.info(f"👤 Пользователь {user_id} ({first_name}) добавлен/обновлен в БД")

def get_all_users():
    """Возвращает список всех пользователей (для будущих рассылок)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, first_name FROM users')
    users = cursor.fetchall()
    conn.close()
    return [dict(user) for user in users]

# Импортируем logger из основного файла (добавим позже)
logger = logging.getLogger(__name__)
