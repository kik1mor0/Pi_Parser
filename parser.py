import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import logging
import json
import re
import csv
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

class Config:
    BASE_URL = "https://stopgame.ru"
    REVIEWS_URL = "/review"
    REQUEST_TIMEOUT = 15
    REQUEST_DELAY = 1.0
    MAX_RETRIES = 3
    CACHE_ENABLED = True
    CACHE_DIR = "cache"
    SAVE_PROGRESS = True
    PROGRESS_FILE = "progress.json"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('parser.log', encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class StopGameParser:
    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.config.USER_AGENT})
        
        if self.config.CACHE_ENABLED:
            self.cache_dir = Path(self.config.CACHE_DIR)
            self.cache_dir.mkdir(exist_ok=True)
        
        logger.info("Парсер инициализирован")

    def _request(self, url: str, retry: int = 0) -> Optional[BeautifulSoup]:
        """Выполняет запрос с повторными попытками"""
        try:
            resp = self.session.get(url, timeout=self.config.REQUEST_TIMEOUT)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
            return BeautifulSoup(resp.text, 'html.parser')
        except Exception as e:
            if retry < self.config.MAX_RETRIES:
                wait = self.config.REQUEST_DELAY * (retry + 1)
                logger.warning(f"Ошибка {url}, повтор через {wait}s: {e}")
                time.sleep(wait)
                return self._request(url, retry + 1)
            logger.error(f"Не удалось загрузить {url}: {e}")
            return None

    def _get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Получает страницу из кэша или с сайта"""
        if not self.config.CACHE_ENABLED:
            return self._request(url)
        
        key = hashlib.md5(url.encode()).hexdigest()
        cache_path = self.cache_dir / f"{key}.html"
        
        if cache_path.exists():
            with open(cache_path, 'r', encoding='utf-8') as f:
                return BeautifulSoup(f.read(), 'html.parser')
        
        soup = self._request(url)
        if soup:
            with open(cache_path, 'w', encoding='utf-8') as f:
                f.write(str(soup))
        return soup

    def _clean_text(self, text: str) -> str:
        """Очищает текст от лишних пробелов"""
        return re.sub(r'\s+', ' ', text).strip() if text else ""

    def _parse_date(self, text: str) -> str:
        """Извлекает дату из текста"""
        # Относительные даты
        now = datetime.now()
        if 'сегодня' in text.lower():
            return now.strftime('%d %B %Y')
        if 'вчера' in text.lower():
            return (now - timedelta(days=1)).strftime('%d %B %Y')
        
        # Формат: "25 ноября 2025"
        match = re.search(r'(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(\d{4})', text, re.I)
        if match:
            return f"{match.group(1)} {match.group(2)} {match.group(3)}"
        
        # Формат: "25.11.2025"
        match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', text)
        if match:
            return f"{match.group(1)}.{match.group(2)}.{match.group(3)}"
        
        return "Дата не указана"

    def _parse_comments(self, text: str) -> int:
        """Извлекает количество комментариев"""
        nums = re.findall(r'\d+', text)
        return int(nums[0]) if nums else 0

    def _extract_review(self, article) -> Optional[Dict]:
        """Извлекает данные из одной карточки обзора"""
        try:
            links = article.find_all('a', href=True)
            if len(links) < 4:
                return None
            
            # Заголовок и ссылка (3-я ссылка)
            title_link = links[2]
            title = self._clean_text(title_link.get_text())
            href = title_link.get('href', '')
            if not title or not href:
                return None
            link = href if href.startswith('http') else urljoin(self.config.BASE_URL, href)
            
            # Автор (2-я ссылка)
            author = self._clean_text(links[1].get_text())
            
            # Комментарии (4-я ссылка)
            comments = self._parse_comments(links[3].get_text())
            
            # Дата
            date = self._parse_date(article.get_text())
            
            # Изображение
            img = article.find('img')
            img_url = None
            if img:
                img_url = img.get('src') or img.get('data-src')
                if img_url:
                    if img_url.startswith('//'):
                        img_url = 'https:' + img_url
                    elif img_url.startswith('/'):
                        img_url = urljoin(self.config.BASE_URL, img_url)
            
            return {
                'title': title,
                'author': author,
                'date': date,
                'comments': comments,
                'link': link,
                'image': img_url
            }
        except Exception as e:
            logger.debug(f"Ошибка извлечения: {e}")
            return None

    def parse_page(self, url: str) -> List[Dict]:
        """Парсит одну страницу"""
        soup = self._get_page(url)
        if not soup:
            return []
        
        articles = soup.find_all('article')
        reviews = []
        for article in articles:
            data = self._extract_review(article)
            if data:
                reviews.append(data)
        
        logger.info(f"{url}: найдено {len(articles)} статей, извлечено {len(reviews)} обзоров")
        return reviews

    def get_total_pages(self, soup: BeautifulSoup) -> int:
        """Определяет количество страниц"""
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
        except:
            return 1

    def save_progress(self, reviews: List[Dict], page: int):
        """Сохраняет прогресс"""
        if not self.config.SAVE_PROGRESS:
            return
        try:
            with open(self.config.PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump({'page': page, 'reviews': reviews, 'timestamp': time.time()}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения прогресса: {e}")

    def load_progress(self) -> Tuple[List[Dict], int]:
        """Загружает прогресс"""
        path = Path(self.config.PROGRESS_FILE)
        if not path.exists():
            return [], 0
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('reviews', []), data.get('page', 0)
        except:
            return [], 0

    def clear_progress(self):
        """Очищает прогресс"""
        path = Path(self.config.PROGRESS_FILE)
        if path.exists():
            path.unlink()

    def parse_all(self, max_pages: int = None, resume: bool = True) -> List[Dict]:
        """Парсит все страницы"""
        start_time = time.time()
        
        # Загрузка прогресса
        all_reviews, last_page = self.load_progress() if resume else ([], 0)
        start_page = last_page + 1 if last_page > 0 else 1
        
        # Первая страница
        first_url = urljoin(self.config.BASE_URL, self.config.REVIEWS_URL)
        
        if start_page == 1:
            logger.info("Парсинг страницы 1")
            reviews = self.parse_page(first_url)
            all_reviews.extend(reviews)
            self.save_progress(all_reviews, 1)
        
        # Определение количества страниц
        soup = self._get_page(first_url)
        total_pages = self.get_total_pages(soup) if soup else 1
        if max_pages:
            total_pages = min(total_pages, max_pages)
        
        logger.info(f"Всего страниц: {total_pages}, начинаем с {max(start_page, 2)}")
        
        # Остальные страницы
        for page_num in range(max(start_page, 2), total_pages + 1):
            time.sleep(self.config.REQUEST_DELAY)
            page_url = f"{first_url}/p{page_num}"
            logger.info(f"Страница {page_num}/{total_pages}")
            
            reviews = self.parse_page(page_url)
            if reviews:
                all_reviews.extend(reviews)
                self.save_progress(all_reviews, page_num)
                logger.info(f"Собрано {len(reviews)} обзоров, всего {len(all_reviews)}")
        
        if resume and not max_pages:
            self.clear_progress()
        
        logger.info(f"Завершено за {time.time() - start_time:.2f} сек, собрано {len(all_reviews)} обзоров")
        return all_reviews

    def save_json(self, reviews: List[Dict], filename: str = "stopgame_reviews.json"):
        """Сохраняет в JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(reviews, f, ensure_ascii=False, indent=2)
        logger.info(f"Сохранено {len(reviews)} обзоров в {filename}")

    def save_csv(self, reviews: List[Dict], filename: str = "stopgame_reviews.csv"):
        """Сохраняет в CSV"""
        if not reviews:
            return
        fields = ['title', 'author', 'date', 'comments', 'link', 'image']
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for r in reviews:
                writer.writerow({k: r.get(k, '') for k in fields})
        logger.info(f"Сохранено {len(reviews)} обзоров в {filename}")

    def print_stats(self, reviews: List[Dict]):
        """Выводит статистику"""
        if not reviews:
            return
        
        total = len(reviews)
        authors = len(set(r['author'] for r in reviews))
        dates = sum(1 for r in reviews if r['date'] != "Дата не указана")
        images = sum(1 for r in reviews if r.get('image'))
        comments = sum(r['comments'] for r in reviews)
        
        print("\n" + "=" * 50)
        print("СТАТИСТИКА")
        print("=" * 50)
        print(f"  Всего обзоров:      {total}")
        print(f"  Уникальных авторов: {authors}")
        print(f"  Обзоров с датами:   {dates} ({dates/total*100:.1f}%)")
        print(f"  Обзоров с фото:     {images} ({images/total*100:.1f}%)")
        print(f"  Всего комментариев: {comments}")
        print(f"  Ср. комментариев:   {comments/total:.1f}")
        print("=" * 50)

def main():
    print("=" * 50)
    print("ПАРСЕР STOPGAME.RU")
    print("=" * 50)
    
    parser = StopGameParser()
    
    print("\nРежимы:")
    print("  1. Собрать все обзоры")
    print("  2. Собрать первые N страниц")
    
    choice = input("\nВыбор (1/2): ").strip()
    
    try:
        if choice == "2":
            pages = int(input("Количество страниц: "))
            reviews = parser.parse_all(max_pages=pages, resume=False)
        else:
            reviews = parser.parse_all(resume=True)
    except KeyboardInterrupt:
        print("\nПрервано. Прогресс сохранён.")
        return
    
    if reviews:
        parser.save_json(reviews)
        parser.save_csv(reviews)
        parser.print_stats(reviews)
        print("\nГотово! Файлы: stopgame_reviews.json, stopgame_reviews.csv, parser.log")
    else:
        print("Обзоры не найдены.")

if __name__ == "__main__":
    main()
