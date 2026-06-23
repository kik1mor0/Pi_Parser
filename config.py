from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    base_url: str = "https://stopgame.ru"
    reviews_url: str = "/review"
    request_timeout: int = 15
    request_delay: float = 1.0
    max_retries: int = 3
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    max_workers: int = 1
    max_pages: int = 0
    
    output_dir: str = "output"
    log_file: str = "parser.log"
    
    def __post_init__(self):
        Path(self.output_dir).mkdir(exist_ok=True)


default_config = Config()