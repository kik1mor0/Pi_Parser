import re
from datetime import datetime, timedelta
from typing import Optional


class TextUtils:
    """Утилиты для обработки текста"""
    
    @staticmethod
    def clean(text: str) -> str:
        """Очищает текст от лишних пробелов"""
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text).strip()
    
    @staticmethod
    def extract_comments(text: str) -> int:
        """Извлекает количество комментариев"""
        nums = re.findall(r'\d+', text)
        return int(nums[0]) if nums else 0


class DateUtils:
    """Утилиты для обработки дат"""
    
    # Месяцы для парсинга
    MONTHS_RU = 'января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря'
    
    @classmethod
    def parse(cls, text: str) -> str:
        """Извлекает дату из текста"""
        now = datetime.now()
        
        # Относительные даты
        if 'сегодня' in text.lower():
            return now.strftime('%d %B %Y')
        if 'вчера' in text.lower():
            return (now - timedelta(days=1)).strftime('%d %B %Y')
        
        # Формат: "25 ноября 2025"
        match = re.search(rf'(\d{{1,2}})\s+({cls.MONTHS_RU})\s+(\d{{4}})', text, re.I)
        if match:
            return f"{match.group(1)} {match.group(2)} {match.group(3)}"
        
        # Формат: "25.11.2025"
        match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', text)
        if match:
            return f"{match.group(1)}.{match.group(2)}.{match.group(3)}"
        
        # Формат: "2025-11-25"
        match = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
        if match:
            return f"{match.group(3)}.{match.group(2)}.{match.group(1)}"
        
        return "Дата не указана"


class RatingUtils:
    """Утилиты для обработки рейтингов"""
    
    @staticmethod
    def extract(text: str) -> str:
        """Извлекает рейтинг обзора"""
        # Формат: "8.5/10" или "8/10"
        match = re.search(r'(\d+(?:\.\d+)?)\s*(?:/|из)\s*(\d+)', text, re.I)
        if match:
            return f"{match.group(1)}/{match.group(2)}"
        
        # Формат: "8.5★" или "9★"
        match = re.search(r'(\d+(?:\.\d+)?)\s*★', text)
        if match:
            return f"{match.group(1)}★"
        
        return ""


class UrlUtils:
    """Утилиты для обработки URL"""
    
    @staticmethod
    def normalize(url: str, base_url: str) -> str:
        """Нормализует URL (добавляет https, base_url)"""
        if not url:
            return ""
        
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            from urllib.parse import urljoin
            return urljoin(base_url, url)
        
        return url