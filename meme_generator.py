import os
import random
from PIL import Image, ImageDraw, ImageFont
import logging
logger = logging.getLogger(__name__)
# Папка с шаблонами
MEME_DIR = "meme_templates"
# Смешные фразы для мемов
MEME_PHRASES = {
    "category": [
        "Потратился на {category} и не жалею",
        "Когда снова увидел '{category}' в чеке",
        "Мой кошелёк после '{category}':",
        "{category} — это не зависимость, это образ жизни",
        "Обещал себе меньше тратить на {category}, но...",
        "Опять {category}? Да я не могу остановиться!",
        "Когда друзья спрашивают, куда деньги: {category}",
        "{category} стоит каждого рубля!",
        "Я контролирую расходы... кроме {category}",
        "Финансовый план? Какой план? {category}!"
    ],
    "amount": [
        "Потратил {amount} руб. и чувствую себя прекрасно",
        "Мой кошелёк после {amount} руб.:",
        "{amount} руб.? Это инвестиция в счастье!",
        "Когда увидел баланс после {amount} руб.",
        "Обещал экономить, но потратил {amount} руб.",
        "Друзья: Ты богатый?\nЯ: Потратил {amount} руб. вчера",
        "{amount} руб. — это не много, правда?",
        "Финансовая грамотность? Не слышал.\n{amount} руб. вчера.",
        "Когда планировал потратить 1000,\nа потратил {amount} руб.",
        "Зарплата: приходит\n{amount} руб.: уходят"
    ]
}
def get_random_template():
    """Выбирает случайный шаблон из папки"""
    if not os.path.exists(MEME_DIR):
        raise FileNotFoundError(f"❌ Папка {MEME_DIR} не найдена!")
    
    templates = [f for f in os.listdir(MEME_DIR) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
    if not templates:
        raise FileNotFoundError(f"❌ Нет картинок в папке {MEME_DIR}/")
    
    return os.path.join(MEME_DIR, random.choice(templates))
def generate_meme(text: str, output_path: str = "meme_output.jpg") -> str:
    """
    Генерирует мем с текстом на случайном шаблоне
    
    Args:
        text: Текст для наложения на мем
        output_path: Путь для сохранения результата
    
    Returns:
        Путь к сгенерированному мему
    """
    try:
        # Загружаем случайный шаблон
        template_path = get_random_template()
        logger.info(f"📸 Используется шаблон: {template_path}")
        
        img = Image.open(template_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        
        # Параметры текста
        width, height = img.size
        font_size = int(height * 0.08)  # 8% от высоты
        
        # Загружаем шрифт
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                font = ImageFont.load_default()
                logger.warning("⚠️ Используется стандартный шрифт")
        
        # Разбиваем текст на строки
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            current_line.append(word)
            test_line = ' '.join(current_line)
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] > width * 0.85:  # Если строка > 85% ширины
                current_line.pop()
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        # Позиция текста (сверху по центру)
        y_offset = height * 0.05  # 5% отступ сверху
        
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            x = (width - text_width) / 2
            
            # Рисуем контур (чёрный)
            outline_width = 3
            for adj_x in range(-outline_width, outline_width + 1):
                for adj_y in range(-outline_width, outline_width + 1):
                    draw.text((x + adj_x, y_offset + adj_y), line, font=font, fill="black")
            
            # Рисуем основной текст (белый)
            draw.text((x, y_offset), line, font=font, fill="white")
            
            y_offset += text_height + 10
        
        # Сохраняем результат
        img.save(output_path, quality=95)
        logger.info(f"✅ Мем сгенерирован: {output_path}")
        
        return output_path
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации мема: {e}")
        raise
def create_meme_for_stats(amount: float = None, category: str = None) -> str:
    """
    Создаёт мем на основе статистики пользователя
    
    Args:
        amount: Общая сумма трат за день
        category: Самая дорогая категория
    
    Returns:
        Путь к сгенерированному мему
    """
    if amount is not None:
        phrase_template = random.choice(MEME_PHRASES["amount"])
        phrase = phrase_template.format(amount=f"{amount:.0f}")
    elif category:
        phrase_template = random.choice(MEME_PHRASES["category"])
        phrase = phrase_template.format(category=category)
    else:
        raise ValueError("❌ Нужно указать либо amount, либо category")
    
    output_path = f"meme_{random.randint(1000, 9999)}.jpg"
    return generate_meme(phrase, output_path)
