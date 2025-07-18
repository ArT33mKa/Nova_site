# init_db.py
from app import app, db, User
from import_products import import_from_bas

def initialize_database():
    with app.app_context():
        print(">>> 1. Створення таблиць бази даних...")
        db.create_all()

        if not User.query.filter_by(username='admin').first():
            print(">>> 2. Створення адміністратора...")
            admin = User(username='admin', email='artemcool200911@gmail.com', is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print(">>> Адміністратора створено.")
        else:
            print(">>> 2. Адміністратор вже існує.")

        print("\n" + "="*50)
        print(">>> 3. ЗАПУСК ІМПОРТУ ТОВАРІВ З ЛОКАЛЬНОГО ФАЙЛУ BAS...")
        import_from_bas()
        print("\n>>> Процес ініціалізації бази даних завершено! <<<")

if __name__ == '__main__':
    initialize_database()