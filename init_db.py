from app import app, db, User

def initialize_database():
    """
    Створює всі таблиці та початкового адміністратора.
    НЕ завантажує товари.
    """
    with app.app_context():
        # Шукаємо твого користувача (заміни на свій телефон АБО email)
        me = User.query.filter_by(phone='+380667268392').first()
        # АБО, якщо ти входив через Google:
        # me = User.query.filter_by(email='tviy_email@gmail.com').first()

        if me:
            me.is_admin = True  # Робимо адміном
            db.session.commit()  # Зберігаємо зміни
            print(f"Користувача {me.first_name} зроблено адміном!")
        else:
            print("Користувача не знайдено. Спочатку зареєструйся на сайті.")

if __name__ == '__main__':
    initialize_database()