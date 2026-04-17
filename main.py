import logging
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from config import Config, default_config
from models import Review
from http_client import HttpClient
from parser import ReviewParser
from progress import ProgressManager
from export import JsonExporter, CsvExporter, HtmlExporter


def setup_logging(config: Config) -> logging.Logger:
    """Настройка логирования"""
    logger = logging.getLogger("StopGameParser")
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Файловый обработчик
    file_handler = logging.FileHandler(
        f"{config.output_dir}/{config.log_file}",
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


class StopGameParser:
    """Основной класс парсера, объединяющий все компоненты"""
    
    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.logger = setup_logging(self.config)
        
        # Инициализация компонентов
        self.http_client = HttpClient(self.config, self.logger)
        self.review_parser = ReviewParser(self.config, self.logger)
        self.progress_manager = ProgressManager(self.config, self.logger)
        self.json_exporter = JsonExporter(self.config, self.logger)
        self.csv_exporter = CsvExporter(self.config, self.logger)
        self.html_exporter = HtmlExporter(self.config, self.logger)
        
        self.logger.info("Парсер инициализирован")
        self.logger.info(f"Конфигурация: delay={self.config.request_delay}s, "
                        f"timeout={self.config.request_timeout}s, "
                        f"workers={self.config.max_workers}")
    
    def parse_all(self, max_pages: int = None, resume: bool = True) -> List[Review]:
        """Парсит все страницы"""
        start_time = time.time()
        
        # Загрузка прогресса
        all_reviews, last_page = self.progress_manager.load() if resume else ([], 0)
        start_page = last_page + 1 if last_page > 0 else 1
        
        # Первая страница
        first_url = self.http_client.build_url(1)
        
        if start_page == 1:
            self.logger.info("Парсинг страницы 1")
            soup = self.http_client.get_cached(first_url)
            if soup:
                reviews = self.review_parser.parse_page(soup, first_url)
                all_reviews.extend(reviews)
                self.progress_manager.save(all_reviews, 1)
        
        # Определение количества страниц
        soup = self.http_client.get_cached(first_url)
        total_pages = self.review_parser.get_total_pages(soup) if soup else 1
        if max_pages:
            total_pages = min(total_pages, max_pages)
        
        self.logger.info(f"Всего страниц: {total_pages}, начинаем с {max(start_page, 2)}")
        
        # Сбор остальных страниц
        if self.config.max_workers > 1:
            new_reviews = self._parse_parallel(total_pages, start_page)
        else:
            new_reviews = self._parse_sequential(total_pages, start_page)
        
        all_reviews.extend(new_reviews)
        
        if resume and not max_pages:
            self.progress_manager.clear()
        
        elapsed = time.time() - start_time
        self.logger.info(f"Завершено за {elapsed:.2f} сек, собрано {len(all_reviews)} обзоров")
        return all_reviews
    
    def _parse_sequential(self, total_pages: int, start_page: int) -> List[Review]:
        """Последовательный парсинг страниц"""
        all_reviews = []
        
        for page_num in range(max(start_page, 2), total_pages + 1):
            time.sleep(self.config.request_delay)
            page_url = self.http_client.build_url(page_num)
            self.logger.info(f"Страница {page_num}/{total_pages}")
            
            soup = self.http_client.get_cached(page_url)
            if soup:
                reviews = self.review_parser.parse_page(soup, page_url)
                if reviews:
                    all_reviews.extend(reviews)
                    self.progress_manager.save(all_reviews, page_num)
                    self.logger.info(f"Собрано {len(reviews)} обзоров, всего {len(all_reviews)}")
        
        return all_reviews
    
    def _parse_parallel(self, total_pages: int, start_page: int) -> List[Review]:
        """Параллельный парсинг страниц"""
        all_reviews = []
        urls = []
        
        for page_num in range(max(start_page, 2), total_pages + 1):
            urls.append((page_num, self.http_client.build_url(page_num)))
        
        self.logger.info(f"Параллельный парсинг {len(urls)} страниц")
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {
                executor.submit(self.http_client.get_cached, url): page_num
                for page_num, url in urls
            }
            
            for future in as_completed(futures):
                page_num = futures[future]
                try:
                    soup = future.result()
                    if soup:
                        reviews = self.review_parser.parse_page(soup, f"page_{page_num}")
                        all_reviews.extend(reviews)
                        self.progress_manager.save(all_reviews, page_num)
                        self.logger.info(f"Страница {page_num}: {len(reviews)} обзоров")
                except Exception as e:
                    self.logger.error(f"Ошибка страницы {page_num}: {e}")
        
        return all_reviews
    
    def export(self, reviews: List[Review]):
        """Экспорт данных во все форматы"""
        if not reviews:
            return
        
        self.json_exporter.export(reviews)
        self.csv_exporter.export(reviews)
        self.html_exporter.export(reviews)
    
    def print_stats(self, reviews: List[Review]):
        """Выводит статистику"""
        if not reviews:
            print("Нет данных")
            return
        
        total = len(reviews)
        authors = len(set(r.author for r in reviews))
        with_dates = sum(1 for r in reviews if r.date != "Дата не указана")
        with_images = sum(1 for r in reviews if r.image)
        with_rating = sum(1 for r in reviews if r.rating)
        total_comments = sum(r.comments for r in reviews)
        
        # ТОП авторов
        from collections import Counter
        top_authors = Counter(r.author for r in reviews).most_common(5)
        
        print("\n" + "=" * 60)
        print("СТАТИСТИКА СБОРА ДАННЫХ")
        print("=" * 60)
        print(f"  Всего обзоров:          {total}")
        print(f"  Уникальных авторов:     {authors}")
        print(f"  Обзоров с датами:       {with_dates} ({with_dates/total*100:.1f}%)")
        print(f"  Обзоров с изображениями: {with_images} ({with_images/total*100:.1f}%)")
        print(f"  Обзоров с рейтингом:    {with_rating} ({with_rating/total*100:.1f}%)")
        print(f"  Всего комментариев:     {total_comments}")
        print(f"  Среднее комментариев:   {total_comments/total:.1f}")
        
        print("\nТОП-5 АВТОРОВ:")
        for i, (author, count) in enumerate(top_authors, 1):
            print(f"  {i}. {author}: {count} обзоров ({count/total*100:.1f}%)")
        
        print("=" * 60)


def parse_args():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(description='Парсер обзоров StopGame.ru')
    parser.add_argument('-p', '--pages', type=int, help='Количество страниц')
    parser.add_argument('-w', '--workers', type=int, default=1, help='Количество потоков')
    parser.add_argument('--no-cache', action='store_true', help='Отключить кэш')
    parser.add_argument('--no-resume', action='store_true', help='Не возобновлять прогресс')
    return parser.parse_args()


def main():
    print("=" * 60)
    print("ПАРСЕР STOPGAME.RU (модульная версия)")
    print("=" * 60)
    
    args = parse_args()
    
    config = Config()
    if args.workers > 1:
        config.max_workers = args.workers
    if args.no_cache:
        config.cache_enabled = False
    
    parser_app = StopGameParser(config)
    
    print(f"\nРежим: {'параллельный' if config.max_workers > 1 else 'последовательный'}")
    print(f"Потоков: {config.max_workers}")
    
    try:
        reviews = parser_app.parse_all(max_pages=args.pages, resume=not args.no_resume)
    except KeyboardInterrupt:
        print("\nПрервано. Прогресс сохранён.")
        return
    
    if reviews:
        parser_app.export(reviews)
        parser_app.print_stats(reviews)
        print(f"\nГотово! Результаты в папке: {config.output_dir}/")
    else:
        print("Обзоры не найдены.")


if __name__ == "__main__":
    main()