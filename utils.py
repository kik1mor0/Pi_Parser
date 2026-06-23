import re
from datetime import datetime, timedelta


class TextUtils:
    @staticmethod
    def clean(text: str) -> str:
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text).strip()
    
    @staticmethod
    def extract_comments(text: str) -> int:
        """Извлекает количество комментариев из текста"""
        if not text:
            return 0
        
        patterns = [
            r'(\d+)\s*(?:коммент|комментариев|комментария|отзывов|отзыва|ответов|ответа)',
            r'(?:коммент|комментариев|комментария|отзывов|отзыва|ответов|ответа)\s*(\d+)',
            r'(\d+)\s*💬',
            r'💬\s*(\d+)',
            r'(\d+)\s*✉',
            r'✉\s*(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return int(match.group(1))
        
        match = re.search(r'\((\d+)\)', text)
        if match:
            return int(match.group(1))
        
        return 0


class DateUtils:
    MONTHS_RU = {
        'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
        'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
        'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
    }
    
    @classmethod
    def parse(cls, text: str, url: str = "") -> str:
        if not text and not url:
            return "Дата не указана"
        
        now = datetime.now()
        
        if url:
            match = re.search(r'/articles/(\d{4})/(\d{2})/(\d{2})/', url)
            if match:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                return f"{day:02d}.{month:02d}.{year}"
        
        if not text:
            return "Дата не указана"
        
        text_lower = text.lower()
        
        if 'сегодня' in text_lower:
            return now.strftime('%d.%m.%Y')
        if 'вчера' in text_lower:
            return (now - timedelta(days=1)).strftime('%d.%m.%Y')
        
        pattern = r'(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(\d{4})'
        match = re.search(pattern, text, re.I)
        if match:
            day = int(match.group(1))
            month = cls.MONTHS_RU.get(match.group(2).lower(), 1)
            year = int(match.group(3))
            return f"{day:02d}.{month:02d}.{year}"
        
        match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', text)
        if match:
            day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f"{day:02d}.{month:02d}.{year}"
        
        match = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
        if match:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f"{day:02d}.{month:02d}.{year}"
        
        return "Дата не указана"


class UrlUtils:
    @staticmethod
    def normalize(url: str, base_url: str) -> str:
        if not url:
            return ""
        
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            from urllib.parse import urljoin
            return urljoin(base_url, url)
        
        return url