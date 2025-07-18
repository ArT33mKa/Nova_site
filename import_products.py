# import_products.py (НОВА ВЕРСІЯ ДЛЯ ІНТЕГРАЦІЇ З LОКАЛЬНИМИ ФАЙЛАМИ BAS)
import xml.etree.ElementTree as ET
import os
import shutil

# --- НАЛАШТУВАННЯ ШЛЯХІВ ---
# Всі шляхи відносно кореня проекту
CML_FILE_PATH = os.path.join('import_data', 'import.xml')  # BAS зазвичай називає файл так
OFFERS_FILE_PATH = os.path.join('import_data', 'offers.xml')  # і вивантажує ціни окремо
SOURCE_IMAGES_DIR = os.path.join('import_data', 'import_files')  # папка з картинками
# Папка, куди будуть зберігатися картинки на сайті
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
    """
    Копіює зображення з вихідної папки в папку static/img/products.
    Повертає ім'я файлу для запису в БД.
    """
    if not image_filename:
        return "default.jpg"

    # BAS може передавати шлях типу "import_files/abc.jpg"
    base_image_name = os.path.basename(image_filename)
    source_path = os.path.join(SOURCE_IMAGES_DIR, base_image_name)
    dest_path = os.path.join(DEST_IMAGES_DIR, base_image_name)

    if os.path.exists(dest_path):
        return base_image_name

    if os.path.exists(source_path):
        try:
            shutil.copy(source_path, dest_path)
            print(f"     * Зображення '{base_image_name}' успішно скопійовано.")
            return base_image_name
        except Exception as e:
            print(f"     ! Помилка копіювання зображення {source_path}: {e}")
    else:
        print(f"     ! Увага: файл зображення '{base_image_name}' не знайдено у '{SOURCE_IMAGES_DIR}'.")

    return "default.jpg"


def import_from_bas():
    """Головна функція для імпорту товарів з локального CML-файлу."""
    from app import app, db, Product
    try:
        # Перевіряємо, чи існує файл з товарами
        if not os.path.exists(CML_FILE_PATH):
            print(f"❌ ПОМИЛКА: Файл з товарами не знайдено: {CML_FILE_PATH}")
            return
        # Перевіряємо, чи існує файл з цінами
        if not os.path.exists(OFFERS_FILE_PATH):
            print(f"❌ ПОМИЛКА: Файл з цінами/залишками не знайдено: {OFFERS_FILE_PATH}")
            return

        os.makedirs(DEST_IMAGES_DIR, exist_ok=True)

        print("\n2. Обробка цін та залишків з offers.xml...")
        offers_data = {}
        offers_tree = ET.parse(OFFERS_FILE_PATH)
        offers_root = offers_tree.getroot()

        for offer in offers_root.findall('.//Предложение'):
            offer_id = offer.find('Ид').text
            price_node = offer.find('.//ЦенаЗаЕдиницу')
            price = float(price_node.text) if price_node is not None and price_node.text else 0.0

            # Наявність зазвичай вказується як кількість, а не true/false
            quantity_node = offer.find('Количество')
            quantity = float(quantity_node.text) if quantity_node is not None and quantity_node.text else 0

            offers_data[offer_id] = {'price': price, 'in_stock': quantity > 0}

        print(f"   -> Знайдено інформацію про ціни та наявність для {len(offers_data)} товарів.")

        print("\n3. Обробка каталогу товарів з import.xml...")
        products_to_create = []
        catalog_tree = ET.parse(CML_FILE_PATH)
        catalog_root = catalog_tree.getroot()

        for item in catalog_root.findall('.//Товар'):
            item_id = item.find('Ид').text

            if item_id not in offers_data:
                # print(f"   ! Пропущено товар '{item.find('Наименование').text}' (ID: {item_id}), немає ціни.")
                continue

            name = item.find('Наименование').text.strip() if item.find('Наименование') is not None else 'Без назви'
            description_node = item.find('Описание')
            description = description_node.text.strip() if description_node is not None and description_node.text else 'Опис відсутній.'

            brand = 'Без бренду'
            # Пошук властивості "Виробник"
            for prop in item.findall(".//ЗначениеРеквизита"):
                if prop.find('Наименование').text == 'Производитель':
                    brand = prop.find('Значение').text.strip()
                    break

            image_node = item.find('Картинка')
            image_filename = "default.jpg"
            if image_node is not None and image_node.text:
                image_filename = copy_local_image(image_node.text.strip())

            product_info = {
                "name": name,
                "price": offers_data[item_id]['price'],
                "in_stock": offers_data[item_id]['in_stock'],
                "description": description,
                "brand": brand,
                "image": image_filename,
                "category": get_category_by_name(name)
            }
            products_to_create.append(Product(**product_info))
            print(
                f"   + Підготовлено товар: {name} (Ціна: {product_info['price']}, Наявність: {product_info['in_stock']})")

        if not products_to_create:
            print("\n! Не знайдено товарів для імпорту. Перевірте ваші CML-файли.")
            return

        with app.app_context():
            print(f"\n4. Оновлення бази даних. Знайдено {len(products_to_create)} товарів.")
            print("   -> Видалення старих товарів...")
            db.session.query(Review).delete()  # Видаляємо старі відгуки разом з товарами
            db.session.query(Product).delete()
            db.session.commit()
            print("   -> Додавання нових товарів...")
            db.session.bulk_save_objects(products_to_create)
            db.session.commit()

        print(f"\n✅ Успішно імпортовано/оновлено {len(products_to_create)} товарів з BAS!")

    except FileNotFoundError as e:
        print(f"❌ КРИТИЧНА ПОМИЛКА: Файл не знайдено. Перевірте шлях. Помилка: {e}")
    except ET.ParseError as e:
        print(f"❌ КРИТИЧНА ПОМИЛКА: Не вдалося розпарсити XML-файл. Він пошкоджений. Помилка: {e}")
    except Exception as e:
        import traceback
        print(f"❌ КРИТИЧНА ПОМИЛКА під час імпорту: {e}")
        traceback.print_exc()