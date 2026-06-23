import re
from typing import List, Optional
from bs4 import BeautifulSoup

from models import Review, ReviewStatus
from utils import TextUtils, DateUtils, UrlUtils
from config import Config


class ReviewParser:
    def __init__(self, config: Config, logger):
        self.config = config
        self.logger = logger
    
    def parse_page(self, soup: BeautifulSoup, url: str) -> List[Review]:
        articles = soup.find_all('article') or soup.find_all('div', class_=re.compile(r'article|review|item', re.I))
        reviews = []
        
        for article in articles:
            review = self._extract_review(article)
            if review and review.title:
                reviews.append(review)
        
        self.logger.info(f"{url}: найдено {len(reviews)} обзоров")
        return reviews
    
    def _extract_review(self, article) -> Optional[Review]:
        try:
            review = Review()
            
            title_elem = article.find('h2') or article.find('h3') or article.find('a', class_=re.compile(r'title|name', re.I))
            if title_elem:
                review.title = TextUtils.clean(title_elem.get_text())
                link_elem = title_elem if title_elem.name == 'a' else title_elem.find('a')
                if link_elem and link_elem.get('href'):
                    review.link = UrlUtils.normalize(link_elem.get('href'), self.config.base_url)
            
            if not review.title:
                return None
            
            author_elem = article.find('a', class_=re.compile(r'author|user|nick', re.I))
            if author_elem:
                review.author = TextUtils.clean(author_elem.get_text())
            else:
                text = article.get_text()
                match = re.search(r'(?:автор|от)\s*[:]?\s*([^\n,]+)', text, re.I)
                if match:
                    review.author = TextUtils.clean(match.group(1))
            
            date_elem = article.find('time') or article.find('span', class_=re.compile(r'date|time', re.I))
            if date_elem:
                date_text = date_elem.get_text()
            else:
                date_text = article.get_text()
            review.date = DateUtils.parse(date_text, review.link)
            
            review.comments = 0
            
            img = article.find('img')
            if img:
                img_url = img.get('src') or img.get('data-src')
                if img_url:
                    review.image = UrlUtils.normalize(img_url, self.config.base_url)
            
            review.status = ReviewStatus.SUCCESS
            return review
            
        except Exception as e:
            self.logger.debug(f"Ошибка извлечения: {e}")
            return None
    
    def get_total_pages(self, soup: BeautifulSoup) -> int:
        try:
            pagination = soup.find('div', class_=re.compile(r'pagination|pages|nav', re.I))
            if pagination:
                numbers = []
                for link in pagination.find_all('a'):
                    text = link.get_text(strip=True)
                    if text.isdigit():
                        numbers.append(int(text))
                if numbers:
                    return max(numbers)
            
            for link in soup.find_all('a', href=re.compile(r'/review/p?\d+')):
                match = re.search(r'/p(\d+)', link.get('href', ''))
                if match:
                    page_num = int(match.group(1))
                    if page_num > 1:
                        return page_num
            
            return 1
        except Exception as e:
            self.logger.warning(f"Ошибка определения пагинации: {e}")
            return 1