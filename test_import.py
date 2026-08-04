# -*- coding: utf-8 -*-
"""Локальний тест обміну з 1С/BAF БЕЗ самого BAF.

Завантажує приклад CommerceML (tests/sample_commerceml/import.xml)
через ту саму логіку, що й справжній обмін.

Запуск:
    python test_import.py
Потім запусти сайт (python app.py) і відкрий каталог — мають з'явитись тестові товари.
"""
import os

from app import app
from extensions import db
from models import Product, Category
from routes.exchange import process_commerceml

HERE = os.path.dirname(os.path.abspath(__file__))
XML = os.path.join(HERE, "tests", "sample_commerceml", "import.xml")

with app.app_context():
    db.create_all()
    process_commerceml(XML, os.path.dirname(XML))
    print(">>> Категорій у БД:", Category.query.count())
    print(">>> Товарів у БД:", Product.query.count())
    for p in Product.query.order_by(Product.external_id).all():
        print("   - %s | %s | %.2f грн | в наявності: %s | категорія: %s" % (
            p.external_id, p.name, p.price or 0.0, p.in_stock, p.category))
    print(">>> Готово. Якщо товарів > 0 — логіка обміну працює.")
