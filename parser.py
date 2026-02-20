import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import logging
import json
import re
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class StopGameReviewParser:
    BASE_URL = "https://stopgame.ru"
    REVIEWS_URL = urljoin(BASE_URL, "/review")

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    }

    def __init__(self, delay: float = 1.0):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.delay = delay

    def _make_request(self, url: str) -> Optional[BeautifulSoup]:
        try:
            logging.info(f"Загрузка страницы: {url}")
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return BeautifulSoup(response.text, 'html.parser')
        except requests.exceptions.RequestException as e:
            logging.error(f"Ошибка при загрузке {url}: {e}")
            return None

    def _extract_review_data(self, article) -> Optional[Dict]:
        try:
            links = article.find_all('a', href=True)

            if len(links) < 4:
                return None

            data = {}

            # Заголовок и ссылка на обзор
            title_link = links[2]
            data['title'] = title_link.get_text(strip=True)
            href = title_link.get('href', '')
            data['link'] = href if href.startswith('http') else urljoin(self.BASE_URL, href)

            # Автор
            author_link = links[1]
            data['author'] = author_link.get_text(strip=True)

            # Комментарии
            comments_link = links[3]
            comments_text = comments_link.get_text(strip=True)
            comments_numbers = re.findall(r'\d+', comments_text)
            data['comments'] = comments_numbers[0] if comments_numbers else "0"

            # Дата
            article_text = article.get_text()
            date_pattern = re.compile(
                r'(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(\d{4})',
                re.IGNORECASE
            )
            date_match = date_pattern.search(article_text)
            if date_match:
                day, month, year = date_match.groups()
                data['date'] = f"{day} {month} {year}"
            else:
                data['date'] = "Дата не указана"

            # Изображение
            img = article.find('img')
            if img:
                img_url = img.get('src') or img.get('data-src')
                if img_url:
                    if img_url.startswith('//'):
                        img_url = 'https:' + img_url
                    elif img_url.startswith('/'):
                        img_url = urljoin(self.BASE_URL, img_url)
                    data['image'] = img_url
                else:
                    data['image'] = None
            else:
                data['image'] = None

            return data

        except Exception as e:
            logging.error(f"Ошибка при извлечении данных: {e}")
            return None

    def parse_page(self, url: str) -> List[Dict]:
        soup = self._make_request(url)
        if not soup:
            return []

        articles = soup.find_all('article')
        logging.info(f"Найдено статей на странице: {len(articles)}")

        reviews = []
        for article in articles:
            review_data = self._extract_review_data(article)
            if review_data:
                reviews.append(review_data)

        logging.info(f"Извлечено обзоров: {len(reviews)}")
        return reviews

    def get_total_pages(self, soup: BeautifulSoup) -> int:
        try:
            pagination = soup.find('div', class_=re.compile(r'pagination', re.I))
            if pagination:
                page_links = pagination.find_all('a')
                numbers = []
                for link in page_links:
                    text = link.get_text(strip=True)
                    if text.isdigit():
                        numbers.append(int(text))
                if numbers:
                    return max(numbers)

            last_link = soup.find('a', string=re.compile(r'последняя|last|\d+', re.I))
            if last_link:
                href = last_link.get('href', '')
                page_match = re.search(r'/p(\d+)', href)
                if page_match:
                    return int(page_match.group(1))

            return 1
        except Exception as e:
            logging.warning(f"Не удалось определить количество страниц: {e}")
            return 1

    def parse_all(self, max_pages: Optional[int] = None) -> List[Dict]:
        all_reviews = []

        first_page_soup = self._make_request(self.REVIEWS_URL)
        if not first_page_soup:
            logging.error("Не удалось загрузить первую страницу")
            return []

        first_page_reviews = self.parse_page(self.REVIEWS_URL)
        all_reviews.extend(first_page_reviews)

        total_pages = self.get_total_pages(first_page_soup)
        if max_pages:
            total_pages = min(total_pages, max_pages)

        logging.info(f"Всего страниц для парсинга: {total_pages}")

        for page_num in range(2, total_pages + 1):
            time.sleep(self.delay)
            page_url = f"{self.REVIEWS_URL}/p{page_num}"
            logging.info(f"Парсинг страницы {page_num}: {page_url}")

            page_reviews = self.parse_page(page_url)
            if page_reviews:
                all_reviews.extend(page_reviews)
                logging.info(f"Страница {page_num}: собрано {len(page_reviews)} обзоров")

        return all_reviews

    def save_to_json(self, reviews: List[Dict], filename: str = "stopgame_reviews.json"):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(reviews, f, ensure_ascii=False, indent=2)
            logging.info(f"Сохранено {len(reviews)} обзоров в {filename}")
        except Exception as e:
            logging.error(f"Ошибка при сохранении файла: {e}")

if __name__ == "__main__":
    parser = StopGameReviewParser(delay=1.5)
    reviews = parser.parse_all(max_pages=2)

    print(f"\nВсего собрано обзоров: {len(reviews)}")

    if reviews:
        parser.save_to_json(reviews, "stopgame_reviews.json")
        print("Готово. Файл: stopgame_reviews.json")
    else:
        print("Обзоры не найдены.")