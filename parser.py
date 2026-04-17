import re
from typing import List, Optional
from bs4 import BeautifulSoup

from models import Review, ReviewStatus
from utils import TextUtils, DateUtils, RatingUtils, UrlUtils
from config import Config


class ReviewParser:
    """Парсер карточек обзоров"""
    
    def __init__(self, config: Config, logger):
        self.config = config
        self.logger = logger
    
    def parse_page(self, soup: BeautifulSoup, url: str) -> List[Review]:
        """Парсит страницу и возвращает список обзоров"""
        articles = soup.find_all('article')
        reviews = []
        
        for article in articles:
            review = self._extract_review(article)
            if review:
                reviews.append(review)
        
        self.logger.info(f"{url}: {len(articles)} статей -> {len(reviews)} обзоров")
        return reviews
    
    def _extract_review(self, article) -> Optional[Review]:
        """Извлекает данные из одной карточки обзора"""
        try:
            links = article.find_all('a', href=True)
            if len(links) < 4:
                return None
            
            review = Review()
            
            # Заголовок и ссылка (3-я ссылка)
            title_link = links[2]
            review.title = TextUtils.clean(title_link.get_text())
            href = title_link.get('href', '')
            if not review.title or not href:
                return None
            review.link = UrlUtils.normalize(href, self.config.base_url)
            
            # Автор (2-я ссылка)
            review.author = TextUtils.clean(links[1].get_text())
            
            # Комментарии (4-я ссылка)
            review.comments = TextUtils.extract_comments(links[3].get_text())
            
            # Дата
            review.date = DateUtils.parse(article.get_text())
            
            # Изображение
            review.image = self._extract_image(article)
            
            # Описание
            review.description = self._extract_description(article, links)
            
            # Рейтинг
            review.rating = RatingUtils.extract(article.get_text())
            
            # Теги
            review.tags = self._extract_tags(article)
            
            review.status = ReviewStatus.SUCCESS
            return review
            
        except Exception as e:
            self.logger.debug(f"Ошибка извлечения: {e}")
            return None
    
    def _extract_image(self, article) -> str:
        """Извлекает URL изображения"""
        img = article.find('img')
        if not img:
            return ""
        
        img_url = img.get('src') or img.get('data-src')
        return UrlUtils.normalize(img_url, self.config.base_url)
    
    def _extract_description(self, article, links) -> str:
        """Извлекает краткое описание"""
        article_text = article.get_text()
        
        # Удаляем текст всех ссылок
        for link in links:
            article_text = article_text.replace(link.get_text(), '')
        
        # Ищем первый осмысленный абзац
        lines = [l.strip() for l in article_text.split('\n') if l.strip()]
        for line in lines:
            if len(line) > 30 and not re.match(r'^\d+$', line):
                return line[:200]
        
        return ""
    
    def _extract_tags(self, article) -> List[str]:
        """Извлекает теги/категории"""
        tags = []
        tags_container = article.find('div', class_=re.compile(r'tags|category', re.I))
        
        if tags_container:
            for tag in tags_container.find_all('a'):
                tag_text = TextUtils.clean(tag.get_text())
                if tag_text:
                    tags.append(tag_text)
        
        return tags
    
    def get_total_pages(self, soup: BeautifulSoup) -> int:
        """Определяет общее количество страниц"""
        try:
            # Поиск по пагинации
            pagination = soup.find('div', class_=re.compile(r'pagination', re.I))
            if pagination:
                numbers = []
                for link in pagination.find_all('a'):
                    text = link.get_text(strip=True)
                    if text.isdigit():
                        numbers.append(int(text))
                if numbers:
                    return max(numbers)
            
            # Поиск по URL
            for link in soup.find_all('a', href=re.compile(r'/review/p\d+')):
                match = re.search(r'/p(\d+)', link.get('href', ''))
                if match:
                    return int(match.group(1))
            
            return 1
        except Exception as e:
            self.logger.warning(f"Ошибка определения пагинации: {e}")
            return 1