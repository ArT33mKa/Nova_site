# test_receiver_render.py (ДІАГНОСТИЧНА ВЕРСІЯ БЕЗ АВТОРИЗАЦІЇ)

import os
import shutil
from flask import Flask, request, send_from_directory, redirect, url_for

app = Flask(__name__)

SAVE_DIR = "received_files_from_bas"
BAS_SECRET_KEY = os.environ.get('BAS_SECRET_KEY')  # Ми його читаємо, але не використовуємо


@app.route('/')
def list_received_files():
    if not os.path.exists(SAVE_DIR):
        return "<h1>Приймач файлів з BAS готовий (БЕЗ АВТОРИЗАЦІЇ)</h1><p>Запустіть обмін з BAS. Файли мають з'явитися тут.</p>"

    files_html = "<h1>Отримані файли з BAS</h1><ul>"
    for filename in sorted(os.listdir(SAVE_DIR)):
        files_html += f'<li><a href="/download/{filename}">{filename}</a></li>'
    files_html += "</ul><hr><form action='/clear' method='post'><button>Очистити файли</button></form>"
    return files_html


@app.route('/download/<path:filename>')
def download_file(filename):
    return send_from_directory(SAVE_DIR, filename, as_attachment=True)


@app.route('/clear', methods=['POST'])
def clear_files():
    if os.path.exists(SAVE_DIR):
        shutil.rmtree(SAVE_DIR)
    return redirect(url_for('list_received_files'))


@app.route('/api/1c_exchange', methods=['GET', 'POST'])
def cml_exchange_test():
    mode = request.args.get('mode')

    print("=" * 60)
    print(f"НОВИЙ ЗАПИТ: {request.method} /api/1c_exchange")
    print(f"  - Аргументи (args): {request.args.to_dict()}")
    print(f"  - Заголовки (headers): {request.headers}")  # Дуже важливо подивитись на це в логах!
    print(f"  - Тіло запиту (data size): {len(request.data)} bytes")

    # #############################################################
    # ## ТИМЧАСОВО ВИМИКАЄМО ПЕРЕВІРКУ АВТОРИЗАЦІЇ ДЛЯ ТЕСТУ ##
    # #############################################################
    # auth = request.authorization
    # if not BAS_SECRET_KEY or not auth or auth.username != BAS_SECRET_KEY:
    #     print("!!! ПОМИЛКА АВТОРИЗАЦІЇ (але ми її ігноруємо для тесту) !!!")
    #     # return 'failure\nIncorrect authorization key.', 401
    # else:
    #     print("+++ Авторизація успішна (але ми її все одно ігноруємо) +++")
    # #############################################################

    try:
        if mode == 'checkauth':
            print(">>> ВІДПОВІДЬ для checkauth: success...")
            return 'success\nPHPSESSID\n12345'
        if mode == 'init':
            os.makedirs(SAVE_DIR, exist_ok=True)
            print(">>> ВІДПОВІДЬ для init: zip=no...")
            return "zip=no\nfile_limit=104857600"
        if mode == 'file':
            filename = request.args.get('filename')
            file_path = os.path.join(SAVE_DIR, filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'wb') as f:
                f.write(request.data)
            print(f">>> Файл '{filename}' збережено.")
            return 'success'
        if mode == 'import':
            return 'success'

        print(f"!!! ПОМИЛКА: Невідомий режим '{mode}'")
        return 'failure\nUnknown mode.', 400

    except Exception as e:
        print(f"\n\nCRITICAL ERROR: {e}\n\n")
        import traceback
        traceback.print_exc()
        return f"failure\nServer Error: {e}", 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)