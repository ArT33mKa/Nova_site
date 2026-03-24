import sys
from app import app
from extensions import db
from models import User

def initialize_database():
    """
    Створює всі таблиці та надає права адміністратора.
    """
    with app.app_context():
        try:
            print(">>> Початок ініціалізації бази даних...")

            # 1. Створюємо всі таблиці
            db.create_all()
            print(">>> Таблиці успішно створено (або вже існували).")

            # 2. Шукаємо користувача, якого треба зробити адміном
            # ВАЖЛИВО: Заміни цей номер на свій реальний, з яким ти зареєструвався на сайті!
            admin_phone = '+380667268392'

            admin_user = User.query.filter_by(phone=admin_phone).first()

            if admin_user:
                if not admin_user.is_admin:
                    admin_user.is_admin = True
                    db.session.commit()
                    print(f">>> Успіх! Користувач '{admin_user.first_name}' з номером {admin_phone} тепер є адміністратором.")
                else:
                    print(f">>> Користувач '{admin_user.first_name}' вже є адміністратором.")
            else:
                print(f">>> УВАГА: Користувача з номером {admin_phone} не знайдено.")
                print(">>> Будь ласка, спочатку зареєструйтесь на сайті, а потім запустіть цей скрипт знову.")

        except Exception as e:
            print(f">>> КРИТИЧНА ПОМИЛКА під час ініціалізації БД: {e}")
            sys.exit(1)

if __name__ == '__main__':
    initialize_database()