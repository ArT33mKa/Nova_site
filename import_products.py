# import_products.py (НОВА ВЕРСІЯ ДЛЯ ІНТЕГРАЦІЇ З BAS)

import xml.etree.ElementTree as ET
import requests
import os
from app import app, db, Product

# --- НАЛАШТУВАННЯ ---
# Вставте сюди URL-адреси, які вам надасть адміністратор BAS
CONFIG = {
    "CATALOG_URL": "http://my-bas-export.com.ua/exchange/import.xml",
    "OFFERS_URL": "http://my-bas-export.com.ua/exchange/offers.xml",
    "IMAGE_BASE_URL": "http://my-bas-export.com.ua/exchange/"  # Базовий шлях до папки з файлами
}
IMAGE_SAVE_PATH = os.path.join('static', 'img', 'products')


# Допоміжна функція для визначення категорії (залишається без змін)
def get_category_by_name(product_name):
    product_name_lower = product_name.lower()
    keyword_map = {
        'полив': 'ПОЛИВОЧНА СИСТЕМА', 'насос': 'НАСОСИ', 'бойлер': 'БОЙЛЕРА',
        'змішувач': 'ЗМІШУВАЧІ', 'витяжка': 'ВИТЯЖКИ', 'колонка': 'КОЛОНКИ',
        'сушка для рушників': 'СУШКА ДЛЯ РУШНИКІВ', 'запчастини до газ': 'ЗАПЧАСТИНИ ДО ГАЗ ОБЛАДНАННЯ'
    }
    for keyword, category_name in keyword_map.items():
        if keyword in product_name_lower:
            return category_name
    return "Сантехніка"


def download_file(url):
    """Завантажує файл за URL і повертає його вміст."""
    print(f"  -> Завантаження файлу з {url}...")
    response = requests.get(url, timeout=30)
    response.raise_for_status()  # Викине помилку, якщо URL недоступний
    response.encoding = 'utf-8'  # Гарантуємо правильне кодування
    return response.text


def download_image(image_path):
    """Завантажує зображення та зберігає його локально."""
    image_url = CONFIG['IMAGE_BASE_URL'] + image_path
    image_filename = os.path.basename(image_path)
    local_path = os.path.join(IMAGE_SAVE_PATH, image_filename)

    if os.path.exists(local_path):
        return image_filename  # Не завантажуємо, якщо файл вже є

    try:
        img_response = requests.get(image_url, stream=True, timeout=15)
        if img_response.status_code == 200:
            with open(local_path, 'wb') as f:
                f.write(img_response.content)
            print(f"     * Зображення '{image_filename}' успішно завантажено.")
            return image_filename
    except Exception as e:
        print(f"     ! Не вдалося завантажити зображення {image_url}: {e}")
    return "default.jpg"


def import_from_bas():
    """Головна функція для імпорту товарів з BAS."""
    try:
        os.makedirs(IMAGE_SAVE_PATH, exist_ok=True)

        print("1. Завантаження даних про ціни та залишки...")
        offers_xml_content = download_file(CONFIG['OFFERS_URL'])
        offers_root = ET.fromstring(offers_xml_content)

        offers_data = {}
        for offer in offers_root.findall('.//Предложение'):
            offer_id = offer.find('Ид').text
            price = float(offer.find('.//ЦенаЗаЕдиницу').text or 0)
            quantity = int(float(offer.find('Количество').text or 0))
            offers_data[offer_id] = {'price': price, 'quantity': quantity}
        print(f"   Знайдено інформацію про {len(offers_data)} товарних пропозицій.")

        print("\n2. Завантаження основного каталогу товарів...")
        catalog_xml_content = download_file(CONFIG['CATALOG_URL'])
        catalog_root = ET.fromstring(catalog_xml_content)

        products_to_process = []
        print("\n3. Обробка товарів та зображень...")
        for item in catalog_root.findall('.//Товар'):
            item_id = item.find('Ид').text
            if item_id not in offers_data:
                continue

            name = item.find('Наименование').text or 'Без назви'
            description_node = item.find('Описание')
            description = description_node.text.strip() if description_node is not None and description_node.text else 'Опис відсутній.'

            brand = 'Без бренду'
            brand_node = item.find(".//*[Наименование='Виробник']/../Значение")
            if brand_node is not None:
                brand = brand_node.text

            image_filename = "default.jpg"
            image_node = item.find('Картинка')
            if image_node is not None and image_node.text:
                image_filename = download_image(image_node.text)

            product_info = {
                "name": name,
                "price": offers_data[item_id]['price'],
                "in_stock": offers_data[item_id]['quantity'] > 0,
                "description": description,
                "brand": brand,
                "image": image_filename,
                "category": get_category_by_name(name)
            }
            products_to_process.append(Product(**product_info))

        if not products_to_process:
            print("\n! Не знайдено товарів для імпорту. Перевірте XML-файли.")
            return

        with app.app_context():
            print(f"\n4. Оновлення бази даних. Знайдено {len(products_to_process)} товарів.")
            print("   -> Видалення старих товарів...")
            Product.query.delete()
            print("   -> Додавання нових товарів...")
            db.session.bulk_save_objects(products_to_process)
            db.session.commit()

        print(f"\n✅ Успішно імпортовано {len(products_to_process)} товарів з BAS!")

    except requests.exceptions.RequestException as e:
        print(
            f"❌ КРИТИЧНА ПОМИЛКА: Не вдалося завантажити файл. Перевірте URL в конфігурації та доступність сервера BAS. Помилка: {e}")
    except ET.ParseError as e:
        print(
            f"❌ КРИТИЧНА ПОМИЛКА: Не вдалося розпарсити XML-файл. Він може бути пошкодженим або мати неправильний формат. Помилка: {e}")
    except Exception as e:
        print(f"❌ КРИТИЧНА ПОМИЛКА під час імпорту: {e}")