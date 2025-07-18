# import_products.py (ФІНАЛЬНА ВЕРСІЯ)
import xml.etree.ElementTree as ET
import os
import shutil

# --- НАЛАШТУВАННЯ ШЛЯХІВ ---
CML_FILE_PATH = os.path.join('import_data', 'tovar.cml')
# Припускаємо, що картинки BAS вивантажує в ту саму папку 'import_data/img'
SOURCE_IMAGES_DIR = os.path.join('import_data', 'img')
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
    return "Сантехніка"  # Категорія за замовчуванням


def copy_local_image(image_filename):
    """Копіює зображення з вихідної папки в папку static/img/products."""
    if not image_filename:
        return "default.jpg"

    source_path = os.path.join(SOURCE_IMAGES_DIR, image_filename)
    dest_path = os.path.join(DEST_IMAGES_DIR, image_filename)

    if os.path.exists(dest_path):
        return image_filename

    if os.path.exists(source_path):
        try:
            shutil.copy(source_path, dest_path)
            print(f"     * Зображення '{image_filename}' успішно скопійовано.")
            return image_filename
        except Exception as e:
            print(f"     ! Помилка копіювання зображення {source_path}: {e}")
    else:
        # Іноді BAS не вивантажує картинки, якщо вони не змінювались.
        # Це не критична помилка.
        print(f"     ! Увага: файл зображення '{image_filename}' не знайдено у '{SOURCE_IMAGES_DIR}'.")

    return "default.jpg"


def import_from_bas():
    """Головна функція для імпорту товарів з локального CML-файлу."""
    from app import app, db, Product, Review
    try:
        if not os.path.exists(CML_FILE_PATH):
            print(f"❌ ПОМИЛКА: Файл для імпорту не знайдено: {CML_FILE_PATH}")
            print("Спочатку виконайте вивантаження з BAS.")
            return

        os.makedirs(DEST_IMAGES_DIR, exist_ok=True)

        print(f"1. Читання та розбір файлу: {CML_FILE_PATH}")
        tree = ET.parse(CML_FILE_PATH)
        root = tree.getroot()

        # Збираємо ціни та залишки. У вашому випадку все в одному файлі.
        print("\n2. Обробка цін та залишків...")
        offers_data = {}
        for offer in root.findall('.//Предложение'):
            offer_id = offer.find('Ид').text
            price_node = offer.find('.//ЦенаЗаЕдиницу')
            price = float(price_node.text) if price_node is not None and price_node.text else 0.0
            offers_data[offer_id] = {'price': price}
        print(f"   -> Знайдено інформацію про ціни для {len(offers_data)} товарів.")

        print("\n3. Обробка каталогу товарів...")
        products_to_create = []
        for item in root.findall('.//Товар'):
            item_id = item.find('Ид').text
            if item_id not in offers_data:
                continue

            name = item.find('Наименование').text.strip()
            description_node = item.find('Описание')
            description = description_node.text.strip() if description_node is not None and description_node.text else 'Опис відсутній.'

            brand = 'Без бренду'
            brand_node = item.find(".//*[Наименование='Виробник']/../Значение")
            if brand_node is not None and brand_node.text:
                brand = brand_node.text.strip()

            in_stock = False
            stock_node = item.find(".//*[Ид='ИД-Наличие']/Значение")  # Пошук по ID властивості
            if stock_node is not None and stock_node.text:
                in_stock = stock_node.text.lower() == 'true'

            image_filename = "default.jpg"
            image_node = item.find('Картинка')
            if image_node is not None and image_node.text:
                image_filename = copy_local_image(image_node.text.strip())

            product_info = {
                "name": name,
                "price": offers_data[item_id]['price'],
                "in_stock": in_stock,
                "description": description,
                "brand": brand,
                "image": image_filename,
                "category": get_category_by_name(name)
            }
            products_to_create.append(Product(**product_info))
            print(f"   + Підготовлено: {name} | Ціна: {product_info['price']} | Наявність: {product_info['in_stock']}")

        if not products_to_create:
            print("\n! Не знайдено товарів для імпорту. Перевірте CML-файл.")
            return

        with app.app_context():
            print(f"\n4. Оновлення бази даних...")
            print("   -> Видалення старих відгуків...")
            db.session.query(Review).delete()
            print("   -> Видалення старих товарів...")
            db.session.query(Product).delete()
            db.session.commit()
            print("   -> Додавання нових товарів...")
            db.session.bulk_save_objects(products_to_create)
            db.session.commit()

        print(f"\n✅ Успішно імпортовано/оновлено {len(products_to_create)} товарів!")

    except Exception as e:
        import traceback
        print(f"❌ КРИТИЧНА ПОМИЛКА під час імпорту: {e}")
        traceback.print_exc()