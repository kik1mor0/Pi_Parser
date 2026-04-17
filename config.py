from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    """Конфигурация парсера"""
    # Сетевые настройки
    base_url: str = "https://stopgame.ru"
    reviews_url: str = "/review"
    request_timeout: int = 15
    request_delay: float = 1.0
    max_retries: int = 3
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    # Кэширование
    cache_enabled: bool = True
    cache_dir: str = "cache"
    
    # Прогресс
    save_progress: bool = True
    progress_file: str = "progress.json"
    
    # Многопоточность
    max_workers: int = 1
    
    # Вывод
    output_dir: str = "output"
    log_file: str = "parser.log"
    
    def __post_init__(self):
        """Создание необходимых директорий"""
        Path(self.cache_dir).mkdir(exist_ok=True)
        Path(self.output_dir).mkdir(exist_ok=True)


# Конфигурация по умолчанию
default_config = Config()