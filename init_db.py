# init_db.py (НОВА, ЧИСТА ВЕРСІЯ)

# Імпортуємо додаток, базу даних та модель User з app.py
from app import app, db, User


def initialize_database():
    """
    Створює всі таблиці та початкового адміністратора.
    НЕ завантажує товари.
    """
    with app.app_context():
        print(">>> 1. Створення таблиць бази даних...")
        # Ця команда створює всі таблиці (users, products, orders і т.д.)
        # на основі моделей у вашому файлі app.py
        db.create_all()
        print(">>>    Таблиці успішно створено.")

        # Створення адміністратора, якщо його ще немає
        if not User.query.filter_by(username='admin').first():
            print(">>> 2. Створення адміністратора...")
            admin = User(
                username='admin',
                first_name='Admin',  # <-- ДОДАЙТЕ ЦЕЙ РЯДОК
                email='artemcool200911@gmail.com',
                is_admin=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print(">>>    Адміністратора створено (логін: admin, пароль: admin123).")
        else:
            print(">>> 2. Адміністратор вже існує, створення пропущено.")

        print("\n>>> Ініціалізацію бази даних завершено. Сайт готовий до роботи.")
        print(">>> Тепер ви можете завантажувати товари з вашої системи BAS.")


if __name__ == '__main__':
    initialize_database()