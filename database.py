import os
import logging
import psycopg
from psycopg.rows import dict_row
logger = logging.getLogger(__name__)
# Получаем URL БД из переменных Railway
DATABASE_URL = os.environ.get("DATABASE_URL")
def get_db_connection():
    """Подключение к PostgreSQL"""
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)
def init_database():
    """Инициализация таблиц в PostgreSQL"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username VARCHAR(255),
            first_name VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица трат
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            amount DECIMAL(10, 2) NOT NULL,
            category VARCHAR(255) NOT NULL,
            date VARCHAR(10) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    conn.commit()
    cursor.close()
    conn.close()
    logger.info("✅ База данных PostgreSQL инициализирована")
def add_or_update_user(user_id, username, first_name):
    """Добавляет или обновляет пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO users (user_id, username, first_name)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id) 
        DO UPDATE SET username = %s, first_name = %s
    ''', (user_id, username, first_name, username, first_name))
    
    conn.commit()
    cursor.close()
    conn.close()
def get_all_users():
    """Возвращает список всех пользователей"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id, username, first_name FROM users')
    users = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return users
def save_expense(user_id, amount, category, date):
    """Сохраняет трату в базу"""
    try:
        logger.info(f"📝 Попытка сохранения: user={user_id}, amount={amount}, category={category}, date={date}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # ✅ Убедимся, что пользователь существует (на случай если не вызывался /start)
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO NOTHING
        ''', (user_id, 'unknown', 'Unknown'))
        
        # Сохраняем трату
        cursor.execute('''
            INSERT INTO expenses (user_id, amount, category, date)
            VALUES (%s, %s, %s, %s)
        ''', (user_id, amount, category, date))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"💰 Расход сохранен: user={user_id}, amount={amount}, category={category}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения: {type(e).__name__}: {e}")
        logger.exception("Полный traceback:")
        return False
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения: {type(e).__name__}: {e}")
        logger.exception("Полный traceback:")  # Покажет весь стек ошибки
        return False
        
def get_user_stats(user_id, days=1):
    """Статистика пользователя за N дней"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    from datetime import datetime, timedelta
    target_date = (datetime.now() - timedelta(days=days)).strftime("%d.%m")
    
    cursor.execute('''
        SELECT category, SUM(amount) as total
        FROM expenses
        WHERE user_id = %s AND date >= %s
        GROUP BY category
        ORDER BY total DESC
    ''', (user_id, target_date))
    
    categories = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if categories:
        total = sum(cat['total'] for cat in categories)
        return {
            'has_data': True,
            'total': float(total),
            'categories': [
                {'category': cat['category'], 'total': float(cat['total'])}
                for cat in categories
            ]
        }
    else:
        return {
            'has_data': False,
            'total': 0,
            'categories': []
        }
def get_user_operations(user_id: int, limit: int = 30) -> list:
    """Последние операции пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT date, category, amount 
        FROM expenses 
        WHERE user_id = %s 
        ORDER BY id DESC 
        LIMIT %s
    ''', (user_id, limit))
    
    operations = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return operations
