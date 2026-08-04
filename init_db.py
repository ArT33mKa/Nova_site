import sys
from app import app
from extensions import db


def initialize_database():
    """Створює всі таблиці локальної бази даних (SQLite)."""
    with app.app_context():
        try:
            print(">>> Початок ініціалізації бази даних...")
            db.create_all()
            print(">>> Таблиці успішно створено (або вже існували).")
            print(">>> Готово. Запустіть сайт командою: python app.py")
        except Exception as e:
            print(f">>> КРИТИЧНА ПОМИЛКА під час ініціалізації БД: {e}")
            sys.exit(1)


if __name__ == '__main__':
    initialize_database()
