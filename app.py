import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import func
from collections import Counter
import locale  # [НОВЕ] Імпорт для локалізації дати
import shutil
from werkzeug.utils import secure_filename
from import_products import process_cml_import, get_cml_file_info


from flask import request, jsonify

from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.consumer import oauth_authorized
from flask_dance.consumer.storage.sqla import SQLAlchemyStorage


# app.py (ВСТАВИТИ ЗАМІСТЬ ІСНУЮЧОГО БЛОКУ ІНТЕГРАЦІЇ)

# ────────────────────────────────
#  ІНТЕГРАЦІЯ З BAS (Спрощена версія для діагностики)
# ────────────────────────────────

@app.route('/webhook/cml-import', methods=['GET', 'POST'])
def webhook_cml_import_test():
    """
    Максимально простий "слухач" для перевірки з'єднання.
    Приймає і GET, і POST запити.
    Нічого не робить, лише логує факт отримання запиту.
    """
    # 1. Логуємо абсолютно все, що можемо, щоб побачити, що прийшло
    print("=" * 40)
    print(f"!!! [ТЕСТОВИЙ РЕЖИМ] ОТРИМАНО ЗАПИТ: {datetime.now()} !!!")
    print(f"МЕТОД ЗАПИТУ: {request.method}")
    print(f"URL: {request.url}")
    print(f"ЗАГОЛОВКИ (Headers): {dict(request.headers)}")

    # 2. Перевіряємо, чи є файли
    if request.files:
        files_list = [f.filename for f in request.files.getlist('file')]
        print(f"ПРИКРІПЛЕНІ ФАЙЛИ: {files_list}")
    else:
        print("ФАЙЛИ НЕ ЗНАЙДЕНО В ЗАПИТІ.")

    # 3. Перевіряємо, чи є дані у формі
    if request.form:
        print(f"ДАНІ ФОРМИ: {dict(request.form)}")
    else:
        print("ДАНІ ФОРМИ НЕ ЗНАЙДЕНО.")

    # 4. Логуємо тіло запиту, якщо воно є
    try:
        raw_data = request.get_data(as_text=True)
        # Обрізаємо, щоб не заспамити лог
        print(f"СИРІ ДАНІ (перші 500 символів): {raw_data[:500]}")
    except Exception as e:
        print(f"Не вдалося прочитати сирі дані: {e}")

    print("=" * 40)

    # 5. Повертаємо просту відповідь, яку BAS точно зрозуміє
    # 'success' - стандартна відповідь для 1C/BAS
    # або можна спробувати 'OK'
    response_text = "success\n"
    return response_text, 200, {'Content-Type': 'text/plain; charset=utf-8'}