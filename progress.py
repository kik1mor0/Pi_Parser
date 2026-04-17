import json
import time
from pathlib import Path
from typing import List, Tuple
from datetime import datetime

from models import Review
from config import Config


class ProgressManager:
    """Управление сохранением и загрузкой прогресса"""
    
    def __init__(self, config: Config, logger):
        self.config = config
        self.logger = logger
    
    def save(self, reviews: List[Review], page: int):
        """Сохраняет прогресс"""
        if not self.config.save_progress:
            return
        
        progress_data = {
            'page': page,
            'reviews_count': len(reviews),
            'reviews': [r.to_dict() for r in reviews],
            'timestamp': time.time(),
            'date': datetime.now().isoformat()
        }
        
        try:
            path = Path(self.config.output_dir) / self.config.progress_file
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
            self.logger.debug(f"Прогресс сохранён: страница {page}, {len(reviews)} обзоров")
        except Exception as e:
            self.logger.error(f"Ошибка сохранения прогресса: {e}")
    
    def load(self) -> Tuple[List[Review], int]:
        """Загружает прогресс"""
        path = Path(self.config.output_dir) / self.config.progress_file
        if not path.exists():
            return [], 0
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            reviews = [Review.from_dict(r) for r in data.get('reviews', [])]
            page = data.get('page', 0)
            self.logger.info(f"Загружен прогресс: страница {page}, {len(reviews)} обзоров")
            return reviews, page
        except Exception as e:
            self.logger.error(f"Ошибка загрузки прогресса: {e}")
            return [], 0
    
    def clear(self):
        """Очищает прогресс"""
        path = Path(self.config.output_dir) / self.config.progress_file
        if path.exists():
            path.unlink()
            self.logger.info("Прогресс очищен")