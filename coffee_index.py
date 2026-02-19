import os
import random
from PIL import Image, ImageDraw, ImageFont
import logging
logger = logging.getLogger(__name__)
# Папка с шаблонами кофе
COFFEE_DIR = "coffee_templates"
# Константа: цена чашки кофе
COFFEE_PRICE = 213
def get_random_coffee_template():
    """Выбирает случайную картинку с кофе"""
    if not os.path.exists(COFFEE_DIR):
        raise FileNotFoundError(f"❌ Папка {COFFEE_DIR} не найдена!")
    
    templates = [f for f in os.listdir(COFFEE_DIR) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
    if not templates:
        raise FileNotFoundError(f"❌ Нет картинок в папке {COFFEE_DIR}/")
    
    return os.path.join(COFFEE_DIR, random.choice(templates))
def get_coffee_emoji(cups: int) -> str:
    """Возвращает эмодзи в зависимости от количества чашек"""
    if cups <= 10:
        return "❤️"
    elif cups <= 50:
        return "👍"
    elif cups <= 100:
        return "🤯"
    else:
        return "😱"
def calculate_coffee_index(amount: float) -> dict:
    """
    Рассчитывает индекс кофе
    
    Args:
        amount: Сумма трат
    
    Returns:
        dict с данными: cups (количество чашек), emoji
    """
    cups = round(amount / COFFEE_PRICE)
    emoji = get_coffee_emoji(cups)
    
    return {
        'cups': cups,
        'emoji': emoji,
        'amount': amount
    }
def generate_coffee_image(date: str, cups: int, emoji: str, output_path: str = "coffee_output.jpg") -> str:
    """
    Генерирует картинку с индексом кофе
    
    Args:
        date: Дата (например, "17.02")
        cups: Количество чашек
        emoji: Эмодзи
        output_path: Путь для сохранения
    
    Returns:
        Путь к сгенерированной картинке
    """
    try:
        # Загружаем случайный шаблон
        template_path = get_random_coffee_template()
        logger.info(f"☕ Используется шаблон: {template_path}")
        
        img = Image.open(template_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        
        width, height = img.size
        
        # Размеры шрифтов
        title_font_size = int(height * 0.08)
        cups_font_size = int(height * 0.15)
        
        # Загружаем шрифты
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", title_font_size)
            cups_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", cups_font_size)
        except:
            title_font = ImageFont.load_default()
            cups_font = ImageFont.load_default()
            logger.warning("⚠️ Используется стандартный шрифт")
        
        # Текст сверху
        title_text = f"Твои траты за {date}"
        
        # Основной текст (большой)
        main_text = f"{cups} чашек кофе {emoji}"
        
        # Позиции
        y_title = height * 0.1
        y_main = height * 0.4
        
        # Рисуем заголовок
        bbox = draw.textbbox((0, 0), title_text, font=title_font)
        text_width = bbox[2] - bbox[0]
        x_title = (width - text_width) / 2
        
        # Контур заголовка
        for adj in range(-2, 3):
            for adj_y in range(-2, 3):
                draw.text((x_title + adj, y_title + adj_y), title_text, font=title_font, fill="black")
        draw.text((x_title, y_title), title_text, font=title_font, fill="white")
        
        # Рисуем основной текст
        bbox = draw.textbbox((0, 0), main_text, font=cups_font)
        text_width = bbox[2] - bbox[0]
        x_main = (width - text_width) / 2
        
        # Контур основного текста
        for adj in range(-3, 4):
            for adj_y in range(-3, 4):
                draw.text((x_main + adj, y_main + adj_y), main_text, font=cups_font, fill="black")
        draw.text((x_main, y_main), main_text, font=cups_font, fill="white")
        
        # Сохраняем
        img.save(output_path, quality=95)
        logger.info(f"✅ Картинка с индексом кофе сгенерирована: {output_path}")
        
        return output_path
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации картинки с кофе: {e}")
        raise
