import json
import csv
from pathlib import Path
from typing import List
from datetime import datetime

from models import Review
from config import Config


class JsonExporter:
    """Экспорт в JSON"""
    
    def __init__(self, config: Config, logger):
        self.config = config
        self.logger = logger
    
    def export(self, reviews: List[Review], filename: str = "reviews.json"):
        path = Path(self.config.output_dir) / filename
        data = [r.to_dict() for r in reviews]
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"JSON сохранён: {path} ({len(reviews)} обзоров)")


class CsvExporter:
    """Экспорт в CSV"""
    
    def __init__(self, config: Config, logger):
        self.config = config
        self.logger = logger
    
    def export(self, reviews: List[Review], filename: str = "reviews.csv"):
        if not reviews:
            return
        
        path = Path(self.config.output_dir) / filename
        fields = ['title', 'author', 'date', 'comments', 'rating', 'link', 'image', 'description']
        
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for r in reviews:
                writer.writerow({k: getattr(r, k, '') for k in fields})
        
        self.logger.info(f"CSV сохранён: {path} ({len(reviews)} обзоров)")


class HtmlExporter:
    """Экспорт в HTML"""
    
    def __init__(self, config: Config, logger):
        self.config = config
        self.logger = logger
    
    def export(self, reviews: List[Review], filename: str = "reports.html"):
        path = Path(self.config.output_dir) / filename
        
        html = self._generate_html(reviews)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        self.logger.info(f"HTML отчёт сохранён: {path}")
    
    def _generate_html(self, reviews: List[Review]) -> str:
        """Генерирует HTML код отчёта"""
        # Статистика
        total = len(reviews)
        authors = len(set(r.author for r in reviews))
        total_comments = sum(r.comments for r in reviews)
        
        # Генерация строк таблицы
        rows = ""
        for r in reviews[:100]:
            rows += f"""
            <tr>
                <td><a href="{r.link}">{r.title[:60]}</a></td>
                <td>{r.author}</td>
                <td>{r.date}</td>
                <td class="comment">{r.comments}</td>
                <td>{r.rating}</td>
            </tr>"""
        
        return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Отчёт парсера StopGame.ru</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .stats {{ background: #f0f0f0; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .comment {{ color: #666; font-size: 0.9em; }}
    </style>
</head>
<body>
    <h1>Отчёт парсера StopGame.ru</h1>
    <div class="stats">
        <p><strong>Всего обзоров:</strong> {total}</p>
        <p><strong>Уникальных авторов:</strong> {authors}</p>
        <p><strong>Всего комментариев:</strong> {total_comments}</p>
        <p><strong>Дата генерации:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    <table>
        <thead>
            <tr><th>Название</th><th>Автор</th><th>Дата</th><th>Комментарии</th><th>Рейтинг</th></tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>
</body>
</html>"""