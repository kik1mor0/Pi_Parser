import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
from pathlib import Path
import webbrowser
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from config import Config
from models import Review
from http_client import HttpClient
from parser import ReviewParser
from export import JsonExporter, CsvExporter, HtmlExporter


def setup_logging(config: Config) -> logging.Logger:
    logger = logging.getLogger("StopGameParser")
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    try:
        file_handler = logging.FileHandler(
            f"{config.output_dir}/{config.log_file}",
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        pass
    
    try:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    except Exception:
        pass
    
    return logger


class StopGameParser:
    def __init__(self, config: Config = None, gui_callback=None):
        self.config = config or Config()
        self.logger = setup_logging(self.config)
        self.gui_callback = gui_callback
        
        self.http_client = HttpClient(self.config, self.logger)
        self.review_parser = ReviewParser(self.config, self.logger)
        self.json_exporter = JsonExporter(self.config, self.logger)
        self.csv_exporter = CsvExporter(self.config, self.logger)
        self.html_exporter = HtmlExporter(self.config, self.logger)
        
        self.logger.info("Парсер инициализирован")
    
    def parse_all(self, max_pages: int = None, resume: bool = True) -> List[Review]:
        start_time = time.time()
        
        all_reviews = []
        start_page = 1
        
        first_url = self.http_client.build_url(1)
        
        self.logger.info("Парсинг страницы 1")
        self._update_status("Парсинг страницы 1")
        soup = self.http_client.get(first_url)  
        if soup:
            reviews = self.review_parser.parse_page(soup, first_url)
            all_reviews.extend(reviews)
        
        soup = self.http_client.get(first_url)  
        total_pages = self.review_parser.get_total_pages(soup) if soup else 1
        if max_pages:
            total_pages = min(total_pages, max_pages)
        
        self.logger.info(f"Всего страниц: {total_pages}")
        self._update_status(f"Всего страниц: {total_pages}")
        
        if self.config.max_workers > 1:
            new_reviews = self._parse_parallel(total_pages, start_page)
        else:
            new_reviews = self._parse_sequential(total_pages, start_page)
        
        all_reviews.extend(new_reviews)
        
        elapsed = time.time() - start_time
        self.logger.info(f"Завершено за {elapsed:.2f} сек, собрано {len(all_reviews)} обзоров")
        self._update_status(f"Завершено! Собрано {len(all_reviews)} обзоров")
        return all_reviews
    
    def _parse_sequential(self, total_pages: int, start_page: int) -> List[Review]:
        all_reviews = []
        
        for page_num in range(max(start_page, 2), total_pages + 1):
            if self.gui_callback and self.gui_callback.is_stopped():
                break
                
            time.sleep(self.config.request_delay)
            page_url = self.http_client.build_url(page_num)
            self.logger.info(f"Страница {page_num}/{total_pages}")
            self._update_progress(page_num, total_pages)
            
            soup = self.http_client.get(page_url)  # Без кэша
            if soup:
                reviews = self.review_parser.parse_page(soup, page_url)
                if reviews:
                    all_reviews.extend(reviews)
                    self.logger.info(f"Собрано {len(reviews)} обзоров, всего {len(all_reviews)}")
                    self._update_status(f"Страница {page_num}/{total_pages}: {len(reviews)} обзоров")
        
        return all_reviews
    
    def _parse_parallel(self, total_pages: int, start_page: int) -> List[Review]:
        all_reviews = []
        urls = []
        
        for page_num in range(max(start_page, 2), total_pages + 1):
            urls.append((page_num, self.http_client.build_url(page_num)))
        
        self.logger.info(f"Параллельный парсинг {len(urls)} страниц")
        self._update_status(f"Параллельный парсинг {len(urls)} страниц")
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {
                executor.submit(self.http_client.get, url): page_num  # Без кэша
                for page_num, url in urls
            }
            
            completed = 0
            for future in as_completed(futures):
                if self.gui_callback and self.gui_callback.is_stopped():
                    break
                    
                page_num = futures[future]
                completed += 1
                self._update_progress(completed, len(urls))
                
                try:
                    soup = future.result()
                    if soup:
                        reviews = self.review_parser.parse_page(soup, f"page_{page_num}")
                        all_reviews.extend(reviews)
                        self.logger.info(f"Страница {page_num}: {len(reviews)} обзоров")
                        self._update_status(f"Страница {page_num}: {len(reviews)} обзоров")
                except Exception as e:
                    self.logger.error(f"Ошибка страницы {page_num}: {e}")
        
        return all_reviews
    
    def _update_progress(self, current, total):
        if self.gui_callback:
            percent = (current / total) * 100
            self.gui_callback.update_progress(percent, f"Страница {current}/{total}")
    
    def _update_status(self, message):
        if self.gui_callback:
            self.gui_callback.update_status(message)
    
    def export(self, reviews: List[Review]):
        if not reviews:
            return
        
        self.json_exporter.export(reviews)
        self.csv_exporter.export(reviews)
        self.html_exporter.export(reviews)


class ParserGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Парсер StopGame.ru")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        self.parser = None
        self.is_running = False
        self.stop_flag = False
        self.reviews = []
        
        self.setup_style()
        self.create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def setup_style(self):
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Arial", 14, "bold"))
        style.configure("Header.TLabel", font=("Arial", 11, "bold"))
        style.configure("Status.TLabel", font=("Arial", 10))
        
    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        title = ttk.Label(title_frame, text="Парсер обзоров StopGame.ru", style="Title.TLabel")
        title.pack(side=tk.LEFT)
        
        self.status_label = ttk.Label(title_frame, text="Готов к работе", style="Status.TLabel")
        self.status_label.pack(side=tk.RIGHT)
        
        settings_frame = ttk.LabelFrame(main_frame, text="Настройки", padding="10")
        settings_frame.pack(fill=tk.X, pady=(0, 10))
        
        row1 = ttk.Frame(settings_frame)
        row1.pack(fill=tk.X, pady=2)
        
        ttk.Label(row1, text="Страниц (0 = все):").pack(side=tk.LEFT, padx=(0, 5))
        self.pages_var = tk.StringVar(value="0")
        pages_entry = ttk.Entry(row1, textvariable=self.pages_var, width=10)
        pages_entry.pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Label(row1, text="Потоков:").pack(side=tk.LEFT, padx=(0, 5))
        self.workers_var = tk.StringVar(value="1")
        workers_entry = ttk.Entry(row1, textvariable=self.workers_var, width=10)
        workers_entry.pack(side=tk.LEFT, padx=(0, 20))
        
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.start_btn = ttk.Button(buttons_frame, text="Начать парсинг", command=self.start_parsing, width=20)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_btn = ttk.Button(buttons_frame, text="Остановить", command=self.stop_parsing, width=20, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.export_btn = ttk.Button(buttons_frame, text="Экспорт", command=self.export_data, width=20, state=tk.DISABLED)
        self.export_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.clear_btn = ttk.Button(buttons_frame, text="Очистить", command=self.clear_output, width=20)
        self.clear_btn.pack(side=tk.LEFT)
        
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, mode='determinate')
        self.progress_bar.pack(fill=tk.X)
        
        self.progress_label = ttk.Label(progress_frame, text="Прогресс: 0%", style="Status.TLabel")
        self.progress_label.pack()
        
        stats_frame = ttk.LabelFrame(main_frame, text="Статистика", padding="10")
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X)
        
        stats_labels = [
            ("Всего обзоров:", "0", 0, 0),
            ("Авторов:", "0", 0, 1),
        ]
        
        self.stats_vars = {}
        for label, default, row, col in stats_labels:
            ttk.Label(stats_grid, text=label, style="Header.TLabel").grid(
                row=row, column=col*2, sticky='w', padx=(0, 5), pady=2
            )
            var = tk.StringVar(value=default)
            self.stats_vars[label] = var
            ttk.Label(stats_grid, textvariable=var).grid(
                row=row, column=col*2+1, sticky='w', padx=(0, 20), pady=2
            )
        
        log_frame = ttk.LabelFrame(main_frame, text="Лог выполнения", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, wrap=tk.WORD, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        self.log_text.tag_config("INFO", foreground="black")
        self.log_text.tag_config("WARNING", foreground="orange")
        self.log_text.tag_config("ERROR", foreground="red")
        self.log_text.tag_config("SUCCESS", foreground="green")
        
        status_bar = ttk.Frame(self.root)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_text = ttk.Label(status_bar, text="Готов к работе", relief=tk.SUNKEN, anchor=tk.W, padding=5)
        self.status_text.pack(fill=tk.X)
        
    def log(self, message, level="INFO"):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        tag = level.upper()
        if tag not in ["INFO", "WARNING", "ERROR", "SUCCESS"]:
            tag = "INFO"
        
        self.log_text.insert(tk.END, f"[{timestamp}] [{tag}] {message}\n", tag)
        self.log_text.see(tk.END)
        
        if len(message) > 80:
            status_msg = message[:77] + "..."
        else:
            status_msg = message
        self.status_text.config(text=status_msg)
        
    def update_progress(self, value, text=None):
        self.progress_var.set(value)
        if text:
            self.progress_label.config(text=text)
        else:
            self.progress_label.config(text=f"Прогресс: {int(value)}%")
        self.root.update()
        
    def update_status(self, message):
        self.status_label.config(text=message)
        self.root.update()
        
    def is_stopped(self):
        return self.stop_flag
        
    def update_stats(self, reviews):
        if not reviews:
            return
            
        total = len(reviews)
        authors = len(set(r.author for r in reviews if r.author))
        
        self.stats_vars["Всего обзоров:"].set(str(total))
        self.stats_vars["Авторов:"].set(str(authors))
        
    def start_parsing(self):
        if self.is_running:
            return
            
        try:
            pages = int(self.pages_var.get())
            workers = int(self.workers_var.get())
            if workers < 1:
                workers = 1
            if workers > 10:
                workers = 10
                messagebox.showwarning("Предупреждение", "Количество потоков ограничено 10")
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректные числа")
            return
        
        self.log_text.delete(1.0, tk.END)
        self.stop_flag = False
        
        config = Config()
        if pages > 0:
            config.max_pages = pages
        config.max_workers = workers
        config.cache_enabled = False
        config.save_progress = False
        
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.export_btn.config(state=tk.DISABLED)
        self.is_running = True
        
        thread = threading.Thread(target=self._parse_thread, args=(config,), daemon=True)
        thread.start()
        
        self.log("Парсинг запущен...", "INFO")
        self.log(f"Настройки: страниц={pages if pages>0 else 'все'}, потоков={workers}", "INFO")
        
    def _parse_thread(self, config):
        try:
            class GUILogger:
                def __init__(self, gui):
                    self.gui = gui
                    
                def info(self, msg):
                    self.gui.log(msg, "INFO")
                    
                def warning(self, msg):
                    self.gui.log(msg, "WARNING")
                    
                def error(self, msg):
                    self.gui.log(msg, "ERROR")
                    
                def debug(self, msg):
                    pass
            
            self.parser = StopGameParser(config, self)
            self.parser.logger = GUILogger(self)
            
            self.log("Начинаю сбор обзоров...", "SUCCESS")
            
            reviews = self.parser.parse_all(
                max_pages=config.max_pages if hasattr(config, 'max_pages') else None,
                resume=False  
            )
            
            self.reviews = reviews
            self.root.after(0, lambda: self.update_stats(reviews))
            self.root.after(0, self._finish_parsing)
            
        except Exception as e:
            self.root.after(0, lambda: self.log(f"Ошибка: {e}", "ERROR"))
            self.root.after(0, self._finish_parsing)
            
    def _finish_parsing(self):
        self.is_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        
        if self.reviews and not self.stop_flag:
            self.export_btn.config(state=tk.NORMAL)
            self.log(f"Парсинг завершен! Собрано {len(self.reviews)} обзоров", "SUCCESS")
            self.update_progress(100, "Завершено!")
        elif self.stop_flag:
            self.log("Парсинг остановлен пользователем", "WARNING")
            self.update_progress(0, "Остановлено")
        else:
            self.log("Обзоры не найдены", "WARNING")
            self.update_progress(0, "Не найдено")
            
        if self.parser:
            self.parser.logger = None
            
    def stop_parsing(self):
        if not self.is_running:
            return
            
        self.stop_flag = True
        self.log("Остановка парсинга...", "WARNING")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        
    def export_data(self):
        if not self.reviews:
            messagebox.showwarning("Предупреждение", "Нет данных для экспорта")
            return
        
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        folder = filedialog.askdirectory(
            title="Выберите папку для сохранения",
            initialdir=str(output_dir.absolute())
        )
        
        if not folder:
            return
            
        try:
            output_path = Path(folder)
            output_path.mkdir(exist_ok=True)
            
            class DummyLogger:
                def __init__(self, gui):
                    self.gui = gui
                    
                def info(self, msg):
                    self.gui.log(msg, "INFO")
                    
                def warning(self, msg):
                    self.gui.log(msg, "WARNING")
                    
                def error(self, msg):
                    self.gui.log(msg, "ERROR")
                    
                def debug(self, msg):
                    pass
            
            dummy_logger = DummyLogger(self)
            
            config = Config()
            config.output_dir = str(output_path)
            
            json_exp = JsonExporter(config, dummy_logger)
            csv_exp = CsvExporter(config, dummy_logger)
            html_exp = HtmlExporter(config, dummy_logger)
            
            json_exp.export(self.reviews)
            csv_exp.export(self.reviews)
            html_exp.export(self.reviews)
            
            self.log(f"Данные сохранены в: {output_path}", "SUCCESS")
            messagebox.showinfo(
                "Успех",
                f"Данные сохранены в папке:\n{output_path.absolute()}\n\nФайлы:\nreviews.json\nreviews.csv\nreports.html"
            )
            
            if messagebox.askyesno("Открыть папку", "Открыть папку с результатами?"):
                webbrowser.open(str(output_path.absolute()))
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка экспорта:\n{e}")
            self.log(f"Ошибка экспорта: {e}", "ERROR")
            
    def clear_output(self):
        if self.reviews and not messagebox.askyesno("Подтверждение", "Очистить все данные?"):
            return
            
        self.reviews = []
        self.log_text.delete(1.0, tk.END)
        self.log("Данные очищены", "INFO")
        
        for var in self.stats_vars.values():
            var.set("0")
            
        self.update_progress(0, "Очищено")
        self.export_btn.config(state=tk.DISABLED)
        
    def on_close(self):
        if self.is_running:
            if not messagebox.askyesno("Подтверждение", "Парсинг еще выполняется. Закрыть программу?"):
                return
            self.stop_flag = True
            self.is_running = False
            
        self.root.destroy()