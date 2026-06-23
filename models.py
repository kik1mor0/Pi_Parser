from dataclasses import dataclass, field
from typing import List, Dict
from enum import Enum


class ReviewStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class Review:
    title: str = ""
    author: str = ""
    date: str = ""
    link: str = ""
    image: str = ""
    status: ReviewStatus = ReviewStatus.PENDING
    
    def to_dict(self) -> Dict:
        return {
            'title': self.title,
            'author': self.author,
            'date': self.date,
            'link': self.link,
            'image': self.image
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Review':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})