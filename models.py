from dataclasses import dataclass, field
from typing import List, Dict
from enum import Enum


class ReviewStatus(Enum):
    """Статус обработки обзора"""
    PENDING = "pending"
    SUCCESS = "success"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class Review:
    """Модель данных обзора"""
    title: str = ""
    author: str = ""
    date: str = ""
    comments: int = 0
    link: str = ""
    image: str = ""
    description: str = ""
    rating: str = ""
    tags: List[str] = field(default_factory=list)
    status: ReviewStatus = ReviewStatus.PENDING
    
    def to_dict(self) -> Dict:
        """Преобразование в словарь"""
        return {
            'title': self.title,
            'author': self.author,
            'date': self.date,
            'comments': self.comments,
            'link': self.link,
            'image': self.image,
            'description': self.description,
            'rating': self.rating,
            'tags': self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Review':
        """Создание из словаря"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})