import time
import requests
from bs4 import BeautifulSoup

from config import Config


class HttpClient:
    def __init__(self, config: Config, logger):
        self.config = config
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': config.user_agent})
    
    def get(self, url: str, retry: int = 0):
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
    
    def build_url(self, page: int = 1) -> str:
        from urllib.parse import urljoin
        base = urljoin(self.config.base_url, self.config.reviews_url)
        
        if page == 1:
            return base
        return f"{base}/p{page}"