# app.py (СПЕЦІАЛЬНА ДІАГНОСТИЧНА ВЕРСІЯ)

import os
import shutil
from flask import Flask, request, send_from_directory, url_for, redirect

app = Flask(__name__)

# Папка для збереження файлів, які ми отримали
SAVE_DIR = "received_from_bas"


@app.route('/')
def index():
    """Головна сторінка для перегляду отриманих файлів."""
    html = "<h1>Приймач файлів з BAS (Діагностична версія)</h1>"
    html += "<p>Тут з'являться файли, отримані від BAS.</p>"

    if os.path.exists(SAVE_DIR) and os.listdir(SAVE_DIR):
        html += "<h2>Отримані файли:</h2><ul>"
        for filename in sorted(os.listdir(SAVE_DIR)):
            html += f'<li><a href="/download/{filename}">{filename}</a></li>'
        html += "</ul>"
    else:
        html += "<p>Поки що файлів немає. Спробуйте запустити вивантаження з BAS.</p>"

    html += '<hr><form action="/clear" method="post"><button type="submit">Очистити всі файли</button></form>'
    return html


@app.route('/download/<path:filename>')
def download(filename):
    """Маршрут для завантаження файлу."""
    return send_from_directory(SAVE_DIR, filename, as_attachment=True)


@app.route('/clear', methods=['POST'])
def clear():
    """Видаляє папку з файлами для нового тесту."""
    if os.path.exists(SAVE_DIR):
        shutil.rmtree(SAVE_DIR)
    return redirect(url_for('index'))


@app.route('/api/1c_exchange', methods=['GET', 'POST'])
def cml_exchange():
    """Обробник запитів від BAS."""
    mode = request.args.get('mode')

    print("=" * 60)
    print(f"НОВИЙ ЗАПИТ: {request.method} /api/1c_exchange?{request.query_string.decode()}")
    print(f"Headers: {request.headers}")

    # --- Перевірка безпеки ---
    secret_key_from_env = os.getenv('BAS_SECRET_KEY')
    key_from_bas = request.args.get('key')
    if not secret_key_from_env or secret_key_from_env != key_from_bas:
        print("!!! ПОМИЛКА АВТОРИЗАЦІЇ !!!")
        return 'failure\nНевірний ключ авторизації.', 401

    print("--- Авторизація успішна ---")

    try:
        # --- Обробка команд ---
        if mode == 'checkauth':
            print(">>> Відповідь на checkauth: success")
            return 'success\nPHPSESSID\n12345'

        if mode == 'init':
            print(">>> Відповідь на init: success")
            os.makedirs(SAVE_DIR, exist_ok=True)
            return 'zip=no\nfile_limit=104857600'

        if mode == 'import':
            original_filename = request.args.get('filename')
            print(f">>> Обробка import для файлу: {original_filename}")

            uploaded_file = request.files.get('file')
            if not uploaded_file:
                print("!!! ПОМИЛКА: Файл не знайдено в request.files['file'] !!!")
                return 'failure\nServer error: file not found in request.', 500

            # Зберігаємо файл з його ОРИГІНАЛЬНИМ іменем
            save_path = os.path.join(SAVE_DIR, original_filename)
            uploaded_file.save(save_path)

            print(f"+++ Файл '{original_filename}' успішно збережено в папку '{SAVE_DIR}' +++")
            return 'success'

        # Якщо прийшов якийсь інший режим
        print(f"--- Отримано невідомий режим '{mode}', ігноруємо і відповідаємо успіхом ---")
        return 'success'

    except Exception as e:
        # Якщо сталася будь-яка помилка, ми записуємо її в лог
        print("\n\n" + "!" * 20 + " CRITICAL ERROR " + "!" * 20)
        import traceback
        traceback.print_exc()
        print("!" * 56 + "\n\n")
        return f"failure\nServer Error: {e}", 500


if __name__ == "__main__":
    # Цей блок потрібен для локального запуску, Render буде використовувати команду з Procfile
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))