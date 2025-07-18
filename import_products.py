# import_products.py (НОВА ВЕРСІЯ ДЛЯ ІНТЕГРАЦІЇ З LОКАЛЬНИМИ ФАЙЛАМИ BAS)
import xml.etree.ElementTree as ET
import os
import shutil


# --- НАЛАШТУВАННЯ ШЛЯХІВ ---
# [ЗМІНЕНО] Вказуємо шляхи до локальних файлів, а не URL
# Всі шляхи відносно кореня проекту
CML_FILE_PATH = os.path.join('import_data', 'tovar.cml')
SOURCE_IMAGES_DIR = os.path.join('import_data', 'img')
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

    source_path = os.path.join(SOURCE_IMAGES_DIR, image_filename)
    dest_path = os.path.join(DEST_IMAGES_DIR, image_filename)

    # Не копіюємо, якщо файл вже існує в папці призначення
    if os.path.exists(dest_path):
        # print(f"     * Зображення '{image_filename}' вже існує.")
        return image_filename

    if os.path.exists(source_path):
        try:
            shutil.copy(source_path, dest_path)
            print(f"     * Зображення '{image_filename}' успішно скопійовано.")
            return image_filename
        except Exception as e:
            print(f"     ! Помилка копіювання зображення {source_path}: {e}")
    else:
        print(f"     ! Увага: файл зображення '{image_filename}' не знайдено у '{SOURCE_IMAGES_DIR}'.")

    return "default.jpg"


def import_from_bas():
    """Головна функція для імпорту товарів з локального CML-файлу."""
    from app import app, db, Product
    try:
        # Перевіряємо, чи існує файл для імпорту
        if not os.path.exists(CML_FILE_PATH):
            print(f"❌ КРИТИЧНА ПОМИЛКА: Файл для імпорту не знайдено за шляхом: {CML_FILE_PATH}")
            print("Переконайтесь, що ви поклали файл вивантаження з BAS в правильну папку.")
            return

        # Створюємо папку для зображень на сайті, якщо її немає
        os.makedirs(DEST_IMAGES_DIR, exist_ok=True)

        print(f"1. Читання та розбір файлу: {CML_FILE_PATH}")
        tree = ET.parse(CML_FILE_PATH)
        root = tree.getroot()

        # [ЗМІНЕНО] Розбираємо ціни та залишки з того ж файлу
        print("\n2. Обробка цін та залишків...")
        offers_data = {}
        # Ваш файл містить ціни та залишки всередині тегу <Предложения>
        for offer in root.findall('.//Предложение'):
            offer_id = offer.find('Ид').text

            # Обробка ціни
            price_node = offer.find('.//ЦенаЗаЕдиницу')
            price = float(price_node.text) if price_node is not None and price_node.text else 0.0

            # Обробка наявності (у вашому файлі наявність в <Товар>, а не в <Предложение>)
            # Тому ми будемо брати її пізніше, а тут поки збережемо ціну
            offers_data[offer_id] = {'price': price}

        print(f"   -> Знайдено інформацію про ціни для {len(offers_data)} товарних пропозицій.")

        print("\n3. Обробка основного каталогу товарів та зображень...")
        products_to_create = []
        for item in root.findall('.//Товар'):
            item_id = item.find('Ид').text

            # Пропускаємо товари, для яких немає ціни
            if item_id not in offers_data:
                print(
                    f"   ! Пропущено товар '{item.find('Наименование').text}' (ID: {item_id}), оскільки для нього не знайдено ціни.")
                continue

            name = item.find('Наименование').text.strip() if item.find('Наименование') is not None and item.find(
                'Наименование').text else 'Без назви'

            description_node = item.find('Описание')
            description = description_node.text.strip() if description_node is not None and description_node.text else 'Опис відсутній.'

            # Виробник (бренд)
            brand = 'Без бренду'
            brand_node = item.find(".//*[Наименование='Виробник']/../Значение")
            if brand_node is not None and brand_node.text:
                brand = brand_node.text.strip()

            # Наявність (in_stock)
            # У вашому файлі це булеве значення в <ЗначенияСвойства>
            in_stock = False
            stock_node = item.find(".//*[Ид='ИД-Наличие']/Значение")
            if stock_node is not None and stock_node.text:
                in_stock = stock_node.text.lower() == 'true'

            # Зображення
            image_filename = "default.jpg"
            image_node = item.find('Картинка')
            if image_node is not None and image_node.text:
                image_filename = copy_local_image(image_node.text.strip())

            # Збираємо всю інформацію про товар
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
            print(
                f"   + Підготовлено товар: {name} (Ціна: {product_info['price']}, Наявність: {product_info['in_stock']})")

        if not products_to_create:
            print("\n! Не знайдено товарів для імпорту. Перевірте ваш CML-файл.")
            return

        with app.app_context():
            print(f"\n4. Оновлення бази даних. Знайдено {len(products_to_create)} товарів для імпорту.")
            print("   -> Видалення старих товарів...")
            Product.query.delete()
            print("   -> Додавання нових товарів...")
            db.session.bulk_save_objects(products_to_create)
            db.session.commit()

        print(f"\n✅ Успішно імпортовано/оновлено {len(products_to_create)} товарів з BAS!")

    except FileNotFoundError:
        print(f"❌ КРИТИЧНА ПОМИЛКА: Файл '{CML_FILE_PATH}' не знайдено. Перевірте шлях та ім'я файлу.")
    except ET.ParseError as e:
        print(
            f"❌ КРИТИЧНА ПОМИЛКА: Не вдалося розпарсити XML/CML-файл. Він може бути пошкодженим або мати неправильний формат. Помилка: {e}")
    except Exception as e:
        import traceback
        print(f"❌ КРИТИЧНА ПОМИЛКА під час імпорту: {e}")
        traceback.print_exc()