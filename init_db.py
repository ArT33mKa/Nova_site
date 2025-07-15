# init_db.py (ПРАВИЛЬНА ВЕРСІЯ)

# Імпортуємо додаток, базу даних та модель User з app.py
from app import app, db, User
# Імпортуємо функцію для завантаження товарів з її власного файлу
from import_products import import_from_prom_xml


def initialize_database():
    """Створює всі таблиці та початкові дані."""
    with app.app_context():
        print(">>> Створення таблиць бази даних...")
        db.create_all()
        print(">>> Таблиці успішно створено.")

        # Створення адміністратора, якщо його ще немає
        if not User.query.filter_by(username='admin').first():
            print(">>> Створення адміністратора...")
            admin = User(username='admin', email='artemcool200911@gmail.com', is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print(">>> Адміністратора створено.")
        else:
            print(">>> Адміністратор вже існує.")

        # Запускаємо імпорт товарів
        # Ви можете закоментувати наступні 3 рядки, якщо не хочете,
        # щоб товари імпортувалися при кожному новому деплої.
        print(">>> Імпортую товари з Prom.ua...")
        import_from_prom_xml()
        print(">>> Імпорт товарів завершено.")


if __name__ == '__main__':
    initialize_database()