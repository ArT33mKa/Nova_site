import requests
import xml.etree.ElementTree as ET
from app import db, Product, app
import re
import os

PROM_XML_URL = "https://xn--80adbyphh2d3e.pp.ua/google_merchant_center.xml?hash_tag=69d6477e7c56f7d08d3e47da055c7964&product_ids=&label_ids=&export_lang=uk&group_ids="
IMAGE_SAVE_PATH = os.path.join('static', 'img', 'products')


def import_from_prom_xml():
    try:
        os.makedirs(IMAGE_SAVE_PATH, exist_ok=True)

        print("1. Завантажую XML-файл...")
        response = requests.get(PROM_XML_URL)
        response.raise_for_status()
        response.encoding = 'utf-8'
        xml_content = response.text

        namespaces = {
            'g': 'http://base.google.com/ns/1.0',
            's': 'https://www.google.com/ns/structured_data/2021'  # Додаємо новий неймспейс
        }
        root = ET.fromstring(xml_content)
        channel = root.find('channel')
        if channel is None:
            print("❌ Помилка: Не знайдено тег <channel>.")
            return

        products_to_add = []
        print("2. Починаю обробку товарів...")

        items = channel.findall('item')
        total_items = len(items)

        for i, item in enumerate(items):
            # Використовуємо .text або "" для безпечного отримання даних
            name = getattr(item.find('g:title', namespaces), 'text', 'Без назви')
            price_text = getattr(item.find('g:price', namespaces), 'text', '0')
            description = getattr(item.find('g:description', namespaces), 'text', 'Опис відсутній.').strip()
            image_url = getattr(item.find('g:image_link', namespaces), 'text', None)
            is_available = getattr(item.find('g:availability', namespaces), 'text', '') == 'in stock'
            # ОТРИМУЄМО БРЕНД
            brand = getattr(item.find('g:brand', namespaces), 'text', 'Без бренду')

            price = float(re.match(r"[\d.]+", price_text).group(0))

            image_filename = "default.jpg"
            if image_url:
                image_filename = image_url.split('/')[-1].split('?')[0]
                local_image_path = os.path.join(IMAGE_SAVE_PATH, image_filename)
                if not os.path.exists(local_image_path):
                    try:
                        print(f"  -> [{i + 1}/{total_items}] Завантажую фото для '{name[:40]}...'")
                        img_response = requests.get(image_url, stream=True)
                        if img_response.status_code == 200:
                            with open(local_image_path, 'wb') as f:
                                for chunk in img_response.iter_content(1024): f.write(chunk)
                        else:
                            image_filename = "default.jpg"
                    except:
                        image_filename = "default.jpg"

            category_name = "Сантехніка"
            if "бойлер" in name.lower():
                category_name = "Бойлера"
            elif "насос" in name.lower():
                category_name = "Насоси"
            elif "змішувач" in name.lower():
                category_name = "Змішувачі"
            elif "котел" in name.lower():
                category_name = "Котли"

            new_product = Product(
                name=name, price=price, description=description,
                image=image_filename, category=category_name,
                brand=brand,  # <-- ДОДАЛИ БРЕНД СЮДИ
                in_stock=is_available
            )
            products_to_add.append(new_product)

        if products_to_add:
            with app.app_context():
                print("\n3. Створення нової бази даних і таблиць...")
                # db.drop_all() # Видаляє всі таблиці, якщо вони є
                db.create_all()  # Створює їх заново з правильною структурою

                print(f"4. Додаю {len(products_to_add)} товарів...")
                db.session.bulk_save_objects(products_to_add)
                db.session.commit()
            print(f"\n✅ Успішно імпортовано {len(products_to_add)} товарів!")
        else:
            print("Товарів для імпорту не знайдено.")

    except Exception as e:
        print(f"❌ Сталася критична помилка: {e}")