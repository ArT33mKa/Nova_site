# test_receiver_render.py (Спеціальна версія для тестування на Render)

import os
import shutil
from flask import Flask, request, send_from_directory, redirect, url_for
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# --- НАЛАШТУВАННЯ ---
SAVE_DIR = "received_files_from_bas"
BAS_SECRET_KEY = os.getenv('BAS_SECRET_KEY')


# --------------------

@app.route('/', methods=['GET'])
def list_received_files():
    """Головна сторінка, яка показує список отриманих файлів."""
    if not os.path.exists(SAVE_DIR):
        return """
        <h1>Приймач файлів з BAS готовий</h1>
        <p>Папка для отриманих файлів ще не створена. Запустіть обмін з BAS.</p>
        <p>Після обміну оновіть цю сторінку, щоб побачити список файлів.</p>
        """

    file_list = []
    for root, _, files in os.walk(SAVE_DIR):
        for name in files:
            # Створюємо відносний шлях файлу для посилання
            relative_path = os.path.relpath(os.path.join(root, name), SAVE_DIR)
            file_list.append(relative_path.replace('\\', '/'))  # для сумісності з Windows

    html = "<h1>Отримані файли з BAS</h1>"
    if not file_list:
        html += "<p>Файли ще не отримано. Запустіть обмін з BAS і оновіть сторінку.</p>"
    else:
        html += "<ul>"
        for f in sorted(file_list):
            # Посилання на завантаження
            html += f'<li><a href="/download/{f}">{f}</a></li>'
        html += "</ul>"

    html += '<hr><form action="/clear_files" method="post"><button type="submit">Очистити всі отримані файли для нового тесту</button></form>'
    return html


@app.route('/download/<path:filepath>', methods=['GET'])
def download_file(filepath):
    """Маршрут для завантаження одного файлу."""
    # Запобігаємо атакам, переконуючись, що шлях знаходиться всередині SAVE_DIR
    safe_path = os.path.abspath(os.path.join(SAVE_DIR, filepath))
    if not safe_path.startswith(os.path.abspath(SAVE_DIR)):
        return "Access Denied", 403

    # Використовуємо безпечну функцію Flask для відправки файлів
    return send_from_directory(SAVE_DIR, filepath, as_attachment=True)


@app.route('/clear_files', methods=['POST'])
def clear_files():
    """Видаляє папку з отриманими файлами."""
    if os.path.exists(SAVE_DIR):
        shutil.rmtree(SAVE_DIR)
        print(f"!!! Папку {SAVE_DIR} було очищено.")
    return redirect(url_for('list_received_files'))


@app.route('/api/1c_exchange', methods=['GET', 'POST'])
def cml_exchange_test():
    """Обробник запитів від BAS."""
    mode = request.args.get('mode')
    auth = request.authorization
    print("-" * 50)
    print(f"Отримано запит: mode={mode}, type={request.args.get('type')}, filename={request.args.get('filename')}")

    # Перевірка безпеки
    if not BAS_SECRET_KEY or not auth or auth.username != BAS_SECRET_KEY:
        print(f"!!! ПОМИЛКА АВТОРИЗАЦІЇ. Очікувався ключ, але отримано '{auth.username if auth else 'None'}'.")
        return 'failure\nНевірний ключ авторизації.', 401

    # Обробка команд
    if mode == 'checkauth':
        return 'success\nPHPSESSID\n12345'
    if mode == 'init':
        os.makedirs(SAVE_DIR, exist_ok=True)
        return f"zip=no\nfile_limit=104857600"
    if mode == 'file':
        filename = request.args.get('filename')
        file_path = os.path.join(SAVE_DIR, filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'wb') as f:
            f.write(request.data)
        print(f">>> Файл '{filename}' збережено. Розмір: {len(request.data)} байт.")
        return 'success'
    if mode == 'import':
        return 'success'

    return 'failure\nНевідомий режим.'


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))