# check_categories.py
import os
from collections import Counter
from sqlalchemy import create_engine, text

# Беремо URL бази даних з тієї ж змінної, що і Flask додаток
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

if not database_url:
    print("Помилка: змінна DATABASE_URL не знайдена.")
else:
    try:
        engine = create_engine(database_url)
        with engine.connect() as connection:
            # Виконуємо прямий SQL запит, щоб отримати всі унікальні категорії та їх кількість
            result = connection.execute(
                text("SELECT category, COUNT(*) FROM product GROUP BY category ORDER BY COUNT(*) DESC;"))

            categories = result.fetchall()

            if not categories:
                print("У базі даних немає жодного товару з категорією.")
            else:
                print("=" * 40)
                print("Знайдені категорії в базі даних:")
                print("=" * 40)
                for category, count in categories:
                    print(f"- '{category}': {count} товарів")
                print("=" * 40)

    except Exception as e:
        print(f"Не вдалося підключитися до бази даних: {e}")