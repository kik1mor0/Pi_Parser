import time
import hashlib
from pathlib import Path
from typing import Optional
import requests
from bs4 import BeautifulSoup

from config import Config
from utils import UrlUtils


class HttpClient:
    """HTTP клиент с поддержкой кэширования и retry"""
    
    def __init__(self, config: Config, logger):
        self.config = config
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': config.user_agent})
    
    def get(self, url: str, retry: int = 0) -> Optional[BeautifulSoup]:
        """Выполняет HTTP запрос с повторными попытками"""
        try:
            self.logger.debug(f"Запрос: {url} (попытка {retry + 1})")
            resp = self.session.get(url, timeout=self.config.request_timeout)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
            return BeautifulSoup(resp.text, 'html.parser')
        
        except requests.exceptions.Timeout:
            self.logger.warning(f"Таймаут: {url}")
        except requests.exceptions.ConnectionError:
            self.logger.warning(f"Ошибка соединения: {url}")
        except requests.exceptions.HTTPError as e:
            self.logger.warning(f"HTTP {e.response.status_code}: {url}")
        except Exception as e:
            self.logger.warning(f"Ошибка: {e} на {url}")
        
        if retry < self.config.max_retries:
            wait = self.config.request_delay * (retry + 1)
            self.logger.info(f"Повтор через {wait:.1f} сек")
            time.sleep(wait)
            return self.get(url, retry + 1)
        
        self.logger.error(f"Не удалось загрузить: {url}")
        return None
    
    def get_cached(self, url: str) -> Optional[BeautifulSoup]:
        """Получает страницу из кэша или с сайта"""
        if not self.config.cache_enabled:
            return self.get(url)
        
        # Генерация ключа кэша
        cache_key = hashlib.md5(url.encode()).hexdigest()
        cache_path = Path(self.config.cache_dir) / f"{cache_key}.html"
        
        # Проверка кэша
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    self.logger.debug(f"Кэш: {url}")
                    return BeautifulSoup(f.read(), 'html.parser')
            except Exception as e:
                self.logger.warning(f"Ошибка чтения кэша: {e}")
        
        # Загрузка с сайта
        soup = self.get(url)
        if soup:
            try:
                with open(cache_path, 'w', encoding='utf-8') as f:
                    f.write(str(soup))
                self.logger.debug(f"Сохранено в кэш: {cache_path}")
            except Exception as e:
                self.logger.warning(f"Ошибка сохранения кэша: {e}")
        
        return soup
    
    def build_url(self, page: int = 1) -> str:
        """Формирует URL для страницы"""
        from urllib.parse import urljoin
        base = urljoin(self.config.base_url, self.config.reviews_url)
        
        if page == 1:
            return base
        return f"{base}/p{page}"