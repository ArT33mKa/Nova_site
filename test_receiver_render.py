# test_receiver_render.py (СУПЕР-ПРОСТА ВЕРСІЯ для збереження файлів)

import os
import shutil
from flask import Flask, request, send_from_directory, redirect, url_for

app = Flask(__name__)
SAVE_DIR = "received_files_from_bas"


# ... (Код для /, /download, /clear залишається той самий) ...
@app.route('/')
def list_received_files():
    if not os.path.exists(SAVE_DIR):
        return "<h1>Приймач файлів з BAS готовий (СУПЕР-ПРОСТА ВЕРСІЯ)</h1><p>Запустіть обмін.</p>"

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
    print(f"НОВИЙ ЗАПИТ: mode={mode}, filename={request.args.get('filename')}")

    try:
        if mode == 'checkauth' or mode == 'init' or mode == 'import':
            # На перші запити просто відповідаємо успіхом
            return 'success\nPHPSESSID\n12345' if mode == 'checkauth' else 'zip=no\nfile_limit=104857600' if mode == 'init' else 'success'

        elif mode == 'file':
            # --- ЦЕ НАЙВАЖЛИВІША ЧАСТИНА ---
            original_filename = request.args.get('filename')
            if not original_filename:
                print("!!! ПОМИЛКА: mode=file, але параметр 'filename' відсутній!")
                return 'failure\nFilename parameter is missing', 400

            # Спрощуємо ім'я файлу, беремо тільки останню частину шляху
            safe_filename = os.path.basename(original_filename)

            # Створюємо головну папку, якщо її немає
            os.makedirs(SAVE_DIR, exist_ok=True)

            # Зберігаємо файл у цю головну папку
            save_path = os.path.join(SAVE_DIR, safe_filename)

            with open(save_path, 'wb') as f:
                f.write(request.data)

            print(
                f">>> Файл '{original_filename}' успішно збережено як '{safe_filename}'. Розмір: {len(request.data)} байт.")
            return 'success'

        else:
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