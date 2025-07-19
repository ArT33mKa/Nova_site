# import_products.py

import xml.etree.ElementTree as ET
import os
import shutil
from datetime import datetime

# --- Шляхи до файлів ---
# Папка, куди app.py складає дані від BAS
IMPORT_DATA_DIR = 'import_data'
# Основний файл з товарами
CML_FILE_PATH = os.path.join(IMPORT_DATA_DIR, 'tovar.cml')
# Папка, куди app.py складає отримані картинки
SOURCE_IMAGES_DIR = os.path.join(IMPORT_DATA_DIR, 'img')
# Папка на сайті, куди будуть копіюватися картинки для відображення
DEST_IMAGES_DIR = os.path.join('static', 'img', 'products')


def get_category_by_name(product_name):
    """Визначає категорію товару за ключовими словами в назві."""
    product_name_lower = product_name.lower()
    # Розширена мапа для кращого розпізнавання
    keyword_map = {
        'полив': 'ПОЛИВОЧНА СИСТЕМА', 'зрошення': 'ПОЛИВОЧНА СИСТЕМА', 'кран': 'ПОЛИВОЧНА СИСТЕМА',
        'насос': 'НАСОСИ',
        'бойлер': 'БОЙЛЕРА', 'водонагрівач': 'БОЙЛЕРА',
        'змішувач': 'ЗМІШУВАЧІ',
        'витяжка': 'ВИТЯЖКИ',
        'колонка': 'КОЛОНКИ',
        'рушникосушка': 'СУШКА ДЛЯ РУШНИКІВ', 'сушка для рушників': 'СУШКА ДЛЯ РУШНИКІВ',
        'запчастини': 'ЗАПЧАСТИНИ ДО ГАЗ ОБЛАДНАННЯ',
        'котел': 'КОТЛИ ТА ОБІГРІВАЧІ',
        'радіатор': 'КОТЛИ ТА ОБІГРІВАЧІ'
    }
    for keyword, category_name in keyword_map.items():
        if keyword in product_name_lower:
            return category_name
    return "Різне"  # Категорія за замовчуванням


def copy_local_image(image_filename):
    """
    Копіює зображення з тимчасової папки імпорту в постійну папку static.
    Повертає ім'я файлу для запису в БД.
    """
    if not image_filename:
        return "default.jpg"

    source_path = os.path.join(SOURCE_IMAGES_DIR, image_filename)

    # Створюємо папку призначення, якщо її немає
    os.makedirs(DEST_IMAGES_DIR, exist_ok=True)
    dest_path = os.path.join(DEST_IMAGES_DIR, image_filename)

    if not os.path.exists(source_path):
        print(
            f"     ! Увага: файл зображення '{image_filename}' не знайдено у '{SOURCE_IMAGES_DIR}'. Використовується default.jpg")
        return "default.jpg"

    if os.path.exists(dest_path):
        # print(f"     * Зображення '{image_filename}' вже існує. Копіювання пропущено.")
        return image_filename

    try:
        shutil.copy(source_path, dest_path)
        print(f"     * Зображення '{image_filename}' успішно скопійовано.")
        return image_filename
    except Exception as e:
        print(f"     ! ПОМИЛКА копіювання зображення {source_path}: {e}")
        return "default.jpg"


def process_cml_import(app, db, Product):
    """
    Головна функція для обробки CML файлу та оновлення БД.
    Викликається після того, як всі файли завантажено.
    """
    if not os.path.exists(CML_FILE_PATH):
        raise FileNotFoundError("Файл tovar.cml не знайдено в папці import_data")

    tree = ET.parse(CML_FILE_PATH)
    root = tree.getroot()

    # Словник для зберігання існуючих товарів для швидкого доступу
    existing_products = {p.name: p for p in Product.query.all()}

    products_added = 0
    products_updated = 0
    products_skipped = 0

    # Простір імен може бути різним, тому шукаємо гнучко
    products_xml = root.findall('.//Товары/Товар')
    if not products_xml:
        # Спроба знайти з простором імен (часто буває в CML)
        ns_map = {'cml': 'urn:1C.ru:commerceml_2'}
        products_xml = root.findall('.//cml:Товары/cml:Товар', ns_map)

    print(f"Знайдено {len(products_xml)} товарів у CML файлі.")

    for product_node in products_xml:
        # Використовуємо .text для безпечного отримання значення
        name_node = product_node.find('.//Наименование')
        name = name_node.text.strip() if name_node is not None and name_node.text else None

        if not name:
            products_skipped += 1
            continue

        price_node = product_node.find('.//ЦенаЗаЕдиницу')
        price = float(price_node.text) if price_node is not None and price_node.text else 0.0

        description_node = product_node.find('.//Описание')
        description = description_node.text.strip() if description_node is not None and description_node.text else ''

        image_node = product_node.find('.//Картинка')
        image_filename = image_node.text.strip() if image_node is not None and image_node.text else None

        # Обробка характеристик (для бренду)
        brand = "Без бренду"
        properties_node = product_node.find('.//ЗначенияСвойств')
        if properties_node is not None:
            for prop in properties_node.findall('.//ЗначениеСвойства'):
                prop_id_node = prop.find('.//Ид')
                prop_value_node = prop.find('.//Значение')
                # Тут припускаємо, що ID характеристики "Производитель" нам відомий, або шукаємо по назві
                # Для прикладу шукаємо назву "Производитель" в довіднику властивостей
                if prop_id_node is not None and prop_value_node is not None and "производитель" in prop_id_node.text.lower():
                    brand = prop_value_node.text.strip()
                    break

        final_image = copy_local_image(image_filename)

        # Оновлення або створення товару
        product = existing_products.get(name)
        if product:
            # Оновлюємо існуючий товар
            product.price = price
            product.description = description
            product.image = final_image
            product.category = get_category_by_name(name)
            product.brand = brand
            product.in_stock = True  # Вважаємо, що всі товари з вигрузки є в наявності
            products_updated += 1
            print(f"  Оновлено: {name}")
        else:
            # Створюємо новий товар
            new_product = Product(
                name=name,
                price=price,
                description=description,
                image=final_image,
                category=get_category_by_name(name),
                brand=brand,
                in_stock=True
            )
            db.session.add(new_product)
            products_added += 1
            print(f"  Додано: {name}")

    with app.app_context():
        db.session.commit()

    summary = f"Додано: {products_added}, Оновлено: {products_updated}, Пропущено: {products_skipped}."
    print(f">>> Звіт по імпорту: {summary}")
    return summary


def get_cml_file_info():
    """Повертає інформацію про файл імпорту для адмін-панелі."""
    if not os.path.exists(CML_FILE_PATH):
        return None
    try:
        stat = os.stat(CML_FILE_PATH)
        return {
            "mtime": datetime.fromtimestamp(stat.st_mtime),
            "size_kb": round(stat.st_size / 1024, 2)
        }
    except Exception as e:
        print(f"Помилка отримання інформації про файл: {e}")
        return None