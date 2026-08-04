import io
import os
import re
import math
from models import User

try:
    import cloudinary
    import cloudinary.uploader
except Exception:  # бібліотека може бути відсутня локально
    cloudinary = None


def normalize_phone_clean(phone_str):
    if not phone_str: return None
    digits = re.sub(r'\D', '', str(phone_str))
    if len(digits) == 12 and digits.startswith('380'): return f"+{digits}"
    elif len(digits) == 10 and digits.startswith('0'): return f"+38{digits}"
    elif len(digits) == 9: return f"+380{digits}"
    return f"+{digits}"


def normalize_phone(phone):
    if not phone: return None
    digits = re.sub(r'\D', '', phone)
    if digits.startswith('380') and len(digits) == 12: return f"+{digits}"
    if digits.startswith('0') and len(digits) == 10: return f"+38{digits}"
    return f"+{digits}" if not phone.startswith('+') else phone


def slugify(text):
    if not text: return ""
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'h', 'ґ': 'g', 'д': 'd', 'е': 'e',
        'є': 'ye', 'ж': 'zh', 'з': 'z', 'и': 'y', 'і': 'i', 'ї': 'yi', 'й': 'y',
        'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
        'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch',
        'ш': 'sh', 'щ': 'shch', 'ь': '', 'ю': 'yu', 'я': 'ya'
    }
    result = []
    for char in text.lower():
        if char in translit_map: result.append(translit_map[char])
        elif char.isalnum(): result.append(char)
        elif char.isspace() or char == '-': result.append('-')
    text = "".join(result)
    text = re.sub(r'[^a-z0-9-]', '', text)
    return re.sub(r'-+', '-', text).strip('-')


def generate_unique_username(base_name):
    base = slugify(base_name).replace('-', '_')
    if not base: base = "user"
    username = base
    counter = 1
    while User.query.filter_by(username=username).first():
        username = f"{base}_{counter}"
        counter += 1
    return username


class FakePagination:
    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.pages = int(math.ceil(total / per_page)) if per_page else 0
        self.prev_num = page - 1
        self.next_num = page + 1
        self.has_prev = page > 1
        self.has_next = page < self.pages

    def iter_pages(self, left_edge=2, left_current=2, right_current=5, right_edge=2):
        last = 0
        for num in range(1, self.pages + 1):
            if num <= left_edge or \
                    (num > self.page - left_current - 1 and num < self.page + right_current) or \
                    num > self.pages - right_edge:
                if last + 1 != num: yield None
                yield num
                last = num


def normalize_text(text):
    if not text: return ""
    text = re.sub(r"[^\w\s\d']", '', text).lower()
    return " ".join(text.split())


def get_ngrams(text, n=3):
    text = normalize_text(text)
    text = f" {text} "
    if len(text) < n: return set()
    return set([text[i:i + n] for i in range(len(text) - n + 1)])


def calculate_similarity(query, target):
    query = normalize_text(query)
    target = normalize_text(target)
    if not query or not target: return 0.0
    if query in target: return 1.0

    q_bigrams, t_bigrams = get_ngrams(query, 2), get_ngrams(target, 2)
    q_trigrams, t_trigrams = get_ngrams(query, 3), get_ngrams(target, 3)

    def dice_score(s1, s2):
        if not s1 or not s2: return 0.0
        return (2.0 * len(s1.intersection(s2))) / (len(s1) + len(s2))

    score_2 = dice_score(q_bigrams, t_bigrams)
    score_3 = dice_score(q_trigrams, t_trigrams)

    if len(query) < 4: return (score_2 * 0.8) + (score_3 * 0.2)
    else: return (score_2 * 0.3) + (score_3 * 0.7)


def _ensure_cloudinary():
    """Лінива конфігурація Cloudinary з env (load_dotenv() виконується після імпортів).
    Повертає True, якщо Cloudinary доступний і налаштований."""
    if cloudinary is None:
        return False
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
    if not (cloud_name and api_key and api_secret):
        return False
    cloudinary.config(cloud_name=cloud_name, api_key=api_key,
                      api_secret=api_secret, secure=True)
    return True


def upload_product_image(local_path, public_id):
    """Завантажує локальний файл у Cloudinary (папка nova_khvylia/products).
    Повертає secure_url або None, якщо Cloudinary недоступний чи сталася помилка."""
    if not local_path or not os.path.isfile(local_path):
        return None
    if not _ensure_cloudinary():
        return None
    try:
        res = cloudinary.uploader.upload(
            local_path,
            folder="products_image",
            public_id=str(public_id) if public_id else None,
            overwrite=True,
            resource_type="image",
        )
        return res.get("secure_url")
    except Exception:
        return None


def cloudinary_upload_bytes(raw, public_id):
    """Вантажить зображення у Cloudinary НАПРЯМУ з байтів (без тимчасових файлів).
    Повертає secure_url або None.

    ОПТИМІЗОВАНО 2026-08-04: збільшено timeout до 120 секунд для великих файлів."""
    if not raw:
        return None
    if not _ensure_cloudinary():
        return None
    safe = ''.join(ch for ch in str(public_id) if ch.isalnum() or ch in '-_') or 'img'
    try:
        res = cloudinary.uploader.upload(
            io.BytesIO(raw),
            folder="products_image",
            public_id=safe,
            overwrite=True,
            resource_type="image",
            timeout=120  # збільшено з 60 до 120 секунд для великих файлів
        )
        url = res.get("secure_url")
        if url:
            return url
        return None
    except Exception as e:
        import logging
        logging.error('Cloudinary upload failed for %s: %s', public_id, e, exc_info=True)
        return None


def cloudinary_url_by_name(name, folder="products_image"):
    """Будує URL зображення в Cloudinary ЗА ІМЕНЕМ (public_id) у папці products_image.
    Нічого не завантажує — лише формує посилання. BAF вантажить фото в Cloudinary
    (public_id = ід товару), а сайт бере його за цим іменем."""
    if not name:
        return None
    cloud = os.getenv("CLOUDINARY_CLOUD_NAME")
    if not cloud:
        return None
    safe = ''.join(ch for ch in str(name) if ch.isalnum() or ch in '-_') or 'img'
    return "https://res.cloudinary.com/%s/image/upload/f_auto,q_auto/%s/%s" % (cloud, folder, safe)


def get_image(image_filename):
    """Повертає URL зображення товару.
    - повне http(s)-посилання (напр. Cloudinary) -> віддаємо як є;
    - інакше шукаємо локальний файл у static/img/products/;
    - якщо нічого немає -> заглушка no_image.png."""
    if not image_filename or not str(image_filename).strip():
        return "/static/img/no_image.png"
    val = str(image_filename).strip()
    if val.startswith("http://") or val.startswith("https://"):
        return val
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(base_dir, "static", "img", "products", val)
    if os.path.exists(candidate):
        return f"/static/img/products/{val}"
    return "/static/img/no_image.png"


shop_info = {
    "name": "НОВА ХВИЛЯ",
    "categories": [
        {'name': 'Поливочна система', 'icon': 'fas fa-water'},
        {'name': 'Насоси та гідрофори', 'icon': 'fas fa-cogs'},
        {'name': 'Водонагрівачі', 'icon': 'fas fa-temperature-high'},
        {'name': 'Змішувачі та сифони', 'icon': 'fas fa-sink'},
        {'name': 'Вентиляція та витяжки', 'icon': 'fas fa-wind'},
        {'name': 'Газове обладнання', 'icon': 'fas fa-burn'},
        {'name': 'Опалення та водопостачання', 'icon': 'fas fa-fire-alt'},
        {'name': 'Запчастини та комплектуючі', 'icon': 'fas fa-tools'}
    ],
    "address": "вул. Гоголя, 47/2", "city": "м. Миргород",
    "phone": ["+38 (050) 670-62-16", "+38 (095) 752-32-58"], "email": "novakhvylia@gmail.com",
    "hours": {"Пн - Пт:": "8:00 - 17:00", "Субота:": "8:00 - 15:00", "Неділя:": "8:00 - 15:00"}
}
