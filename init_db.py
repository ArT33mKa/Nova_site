from app import app, db, User, import_from_prom_xml


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
            admin.set_password('admin123')  # Ви можете змінити пароль
            db.session.add(admin)
            db.session.commit()
            print(">>> Адміністратора створено.")
        else:
            print(">>> Адміністратор вже існує.")

        # За бажанням, можна розкоментувати, щоб імпортувати товари при кожному деплої
        # print(">>> Імпортую товари з Prom.ua...")
        # import_from_prom_xml()
        # print(">>> Імпорт товарів завершено.")


if __name__ == '__main__':
    initialize_database()