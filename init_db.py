# init_db.py (ОНОВЛЕНА ВЕРСІЯ)

# Імпортуємо додаток, базу даних та модель User з app.py
from app import app, db, User
# Імпортуємо нашу нову функцію для завантаження товарів з BAS
from import_products import import_from_bas

def initialize_database():
    """Створює всі таблиці, адміна та імпортує товари з BAS."""
    with app.app_context():
        print(">>> 1. Створення таблиць бази даних...")
        db.create_all()
        print(">>> Таблиці успішно створено.")

        # Створення адміністратора, якщо його ще немає
        if not User.query.filter_by(username='admin').first():
            print(">>> 2. Створення адміністратора...")
            admin = User(username='admin', email='artemcool200911@gmail.com', is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print(">>> Адміністратора створено.")
        else:
            print(">>> 2. Адміністратор вже існує.")

        # Запускаємо імпорт товарів з BAS
        print("\n>>> 3. ЗАПУСК ІМПОРТУ ТОВАРІВ З BAS...")
        import_from_bas()
        print(">>> Імпорт товарів завершено.")

if __name__ == '__main__':
    initialize_database()