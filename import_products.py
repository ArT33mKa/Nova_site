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
    keyword_map = {
        'полив': 'ПОЛИВОЧНА СИСТЕМА', 'насос': 'НАСОСИ', 'бойлер': 'БОЙЛЕРА',
        'водонагрівач': 'БОЙЛЕРА', 'змішувач': 'ЗМІШУВАЧІ', 'витяжка': 'ВИТЯЖКИ',
        'колонка': 'КОЛОНКИ', 'сушка для рушників': 'СУШКА ДЛЯ РУШНИКІВ',
        'запчастини до газ': 'ЗАПЧАСТИНИ ДО ГАЗ ОБЛАДНАННЯ'
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


def get_cml_file_info():
    """Повертає інформацію про файл імпорту."""
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


def import_from_bas():
    """Головна функція для імпорту товарів з CML-файлу."""
    # Імпортуємо тут, щоб уникнути циклічних залежностей
    from app import app, db, Product

    try:
        print(">>> ЗАПУСК ІМПОРТУ ТОВАРІВ З BAS...")
        if not os.path.exists(CML_FILE_PATH):
            error_msg = f"ПОМИЛКА: Файл для імпорту не знайдено: {CML_FILE_PATH}"
            print(error_msg)
            return {"status": "error", "message": error_msg}

        os.makedirs(DEST_IMAGES_DIR, exist_ok=True)

        print(f"1. Читання та розбір файлу: {CML_FILE_PATH}")
        tree = ET.parse(CML_FILE_PATH)
        root = tree.getroot()
        ns = {'cml': 'urn:1C.ru:commerceml_2'}  # Namespace для CommerceML 2

        # --- Обробка цін та залишків ---
        print("2. Обробка пропозицій (ціни та залишки)...")
        offers_data = {}
        for offer in root.findall('.//cml:Предложение', ns) or root.findall('.//Предложение'):
            offer_id = offer.find('cml:Ид', ns) or offer.find('Ид')
            if offer_id is None: continue

            offer_id_text = offer_id.text
            offers_data[offer_id_text] = {}

            price_node = offer.find('.//cml:ЦенаЗаЕдиницу', ns) or offer.find('.//ЦенаЗаЕдиницу')
            offers_data[offer_id_text]['price'] = float(
                price_node.text) if price_node is not None and price_node.text else 0.0

            stock_node = offer.find('cml:Количество', ns) or offer.find('Количество')
            stock_quantity = float(stock_node.text) if stock_node is not None and stock_node.text else 0
            offers_data[offer_id_text]['in_stock'] = stock_quantity > 0

        print(f"   -> Знайдено інформацію про ціни/залишки для {len(offers_data)} товарних пропозицій.")

        # --- Обробка каталогу товарів ---
        print("3. Обробка каталогу товарів...")
        products_to_process = []
        catalog_node = root.find('cml:Каталог', ns) or root.find('Каталог')
        if catalog_node is None:
            return {"status": "error", "message": "Не знайдено тег <Каталог> у CML файлі."}

        for item in catalog_node.findall('.//cml:Товар', ns) or catalog_node.findall('.//Товар'):
            item_id_node = item.find('cml:Ид', ns) or item.find('Ид')
            if item_id_node is None: continue

            item_id = item_id_node.text
            offer_details = offers_data.get(item_id)

            if not offer_details:
                # print(f"   ! Пропущено товар (ID: {item_id}), оскільки для нього не знайдено ціни/залишку.")
                continue

            name_node = item.find('cml:Наименование', ns) or item.find('Наименование')
            name = name_node.text.strip() if name_node is not None and name_node.text else 'Без назви'

            description_node = item.find('cml:Описание', ns) or item.find('Описание')
            description = description_node.text.strip() if description_node is not None and description_node.text else ''

            brand = 'Без бренду'
            # Пошук реквізиту "Виробник"
            for prop_val in item.findall('.//cml:ЗначениеРеквизита', ns) or item.findall('.//ЗначениеРеквизита'):
                if (prop_val.find('cml:Наименование', ns) or prop_val.find('Наименование')).text == 'Виробник':
                    brand_node = prop_val.find('cml:Значение', ns) or prop_val.find('Значение')
                    if brand_node is not None and brand_node.text:
                        brand = brand_node.text.strip()
                    break

            image_filename = "default.jpg"
            image_node = item.find('cml:Картинка', ns) or item.find('Картинка')
            if image_node is not None and image_node.text:
                image_filename = copy_local_image(image_node.text.strip())

            product_info = {
                "name": name,
                "price": offer_details.get('price', 0.0),
                "in_stock": offer_details.get('in_stock', False),
                "description": description,
                "brand": brand,
                "image": image_filename,
                "category": get_category_by_name(name)
            }
            products_to_process.append(product_info)
            print(
                f"   + Підготовлено товар: {name} (Ціна: {product_info['price']}, Наявність: {product_info['in_stock']})")

        if not products_to_process:
            message = "У CML-файлі не знайдено товарів для імпорту або для них відсутні ціни."
            print(f"! {message}")
            return {"status": "warning", "message": message}

        with app.app_context():
            print("4. Оновлення бази даних...")
            print("   -> Видалення старих товарів та пов'язаних відгуків...")
            # Каскадне видалення повинно видалити і відгуки (залежить від налаштувань моделі)
            Product.query.delete()
            db.session.commit()

            print("   -> Створення нових товарів...")
            new_products_obj = [Product(**p) for p in products_to_process]
            db.session.bulk_save_objects(new_products_obj)
            db.session.commit()

        success_msg = f"Успішно імпортовано/оновлено {len(products_to_process)} товарів."
        print(f"✅ {success_msg}")
        return {"status": "success", "message": success_msg}

    except FileNotFoundError:
        error_msg = f"КРИТИЧНА ПОМИЛКА: Файл '{CML_FILE_PATH}' не знайдено."
        print(f"❌ {error_msg}")
        return {"status": "error", "message": error_msg}
    except ET.ParseError as e:
        error_msg = f"КРИТИЧНА ПОМИЛКА: Не вдалося розпарсити XML. Файл пошкоджено. Помилка: {e}"
        print(f"❌ {error_msg}")
        return {"status": "error", "message": error_msg}
    except Exception as e:
        import traceback
        error_msg = f"КРИТИЧНА ПОМИЛКА під час імпорту: {e}"
        print(f"❌ {error_msg}")
        traceback.print_exc()
        return {"status": "error", "message": error_msg}