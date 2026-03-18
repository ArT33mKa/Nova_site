import sys
from app import app, db

# ВАЖЛИВО: Імпортуємо ВСІ моделі, щоб SQLAlchemy знала, які таблиці створювати.
from app import User, Category, Product, Review, Order, OrderItem, CartItem, CategoryView, OAuth


def initialize_database():
    """
    Створює всі таблиці та початкового адміністратора.
    """
    with app.app_context():
        try:
            print(">>> Початок ініціалізації бази даних...")

            # 1. Створюємо всі таблиці на основі моделей в app.py
            # Ця команда не видалить існуючі таблиці, а тільки створить відсутні.
            db.create_all()

            print(">>> Таблиці успішно створено (або вже існували).")

            # 2. Тепер, коли таблиці гарантовано існують, шукаємо адміністратора.
            #    ЗАМІНІТЬ ЦЕЙ НОМЕР НА СВІЙ РЕАЛЬНИЙ, ЯКИЙ ВИКОРИСТОВУЄТЬСЯ ПРИ РЕЄСТРАЦІЇ.
            admin_phone = '+380667268392'

            admin_user = User.query.filter_by(phone=admin_phone).first()

            if admin_user:
                if not admin_user.is_admin:
                    admin_user.is_admin = True
                    db.session.commit()
                    print(
                        f">>> Успіх! Користувач '{admin_user.first_name}' з номером {admin_phone} тепер є адміністратором.")
                else:
                    print(f">>> Користувач '{admin_user.first_name}' вже є адміністратором.")
            else:
                # ВАЖЛИВО: Цей скрипт не створює користувача, він лише надає права.
                # Вам потрібно спочатку один раз зареєструватися на сайті з цим номером телефону.
                print(f">>> УВАГА: Користувача з номером {admin_phone} не знайдено.")
                print(">>> Будь ласка, спочатку зареєструйтесь на сайті, а потім перезапустіть деплой.")
                # Можна завершити з помилкою, щоб деплой зупинився, якщо адмін не знайдений
                # sys.exit(1) # Розкоментуйте, якщо хочете, щоб деплой падав без адміна

        except Exception as e:
            print(f">>> КРИТИЧНА ПОМИЛКА під час ініціалізації БД: {e}")
            # Виходимо з кодом помилки, щоб деплой на Fly.io зупинився
            sys.exit(1)


if __name__ == '__main__':
    initialize_database()