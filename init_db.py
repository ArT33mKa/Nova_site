# init_db.py (НОВИЙ ФАЙЛ)

# Імпортуємо 'app' та 'db' з вашого основного файлу
from app import app, db, User

print(">>> Запуск скрипта ініціалізації бази даних...")

# Створюємо контекст додатку, щоб працювати з базою
with app.app_context():
    print(">>> Створення всіх таблиць...")
    db.create_all()
    print(">>> Таблиці успішно створено.")

    # Перевіряємо, чи існує адмін, і створюємо, якщо ні
    if not User.query.filter_by(is_admin=True).first():
        print(">>> Створення адміністратора за замовчуванням...")
        admin = User(username='admin', email='artemcool200911@gmail.com', is_admin=True)
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print(">>> Адміністратора створено. Логін: admin, Пароль: admin123")
    else:
        print(">>> Адміністратор вже існує.")

print(">>> Ініціалізація бази даних завершена.")