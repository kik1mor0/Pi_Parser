import sys
import io

if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except (AttributeError, ValueError, OSError):
        pass

try:
    from gui import ParserGUI
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False


def main():
    if not GUI_AVAILABLE:
        print("Ошибка: GUI не доступен (файл gui.py не найден)")
        input("Нажмите Enter для выхода...")
        return
    
    try:
        print("Запуск парсера StopGame.ru...")
        app = ParserGUI()
        app.root.mainloop()
    except Exception as e:
        print(f"Ошибка запуска: {e}")
        input("Нажмите Enter для выхода...")


if __name__ == "__main__":
    main()