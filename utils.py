import os
import re
import math
import smtplib
import requests
import cloudinary.utils
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from models import User

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
        'ш': 'sh', 'щ': 'shch', 'ь': '', 'ю': 'yu', 'я': 'ya',
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'H', 'Ґ': 'G', 'Д': 'D', 'Е': 'E',
        'Є': 'Ye', 'Ж': 'Zh', 'З': 'Z', 'И': 'Y', 'І': 'I', 'Ї': 'Yi', 'Й': 'Y',
        'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R',
        'С': 'S', 'Т': 'T', 'У': 'U', 'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch',
        'Ш': 'Sh', 'Щ': 'Shch', 'Ь': '', 'Ю': 'Yu', 'Я': 'Ya',
        'ы': 'y', 'э': 'e', 'ё': 'yo', 'ъ': ''
    }
    result = []
    for char in text:
        if char in translit_map: result.append(translit_map[char])
        elif char.isalnum(): result.append(char)
        elif char.isspace() or char == '-': result.append('-')
    text = "".join(result).lower()
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
        self.pages = int(math.ceil(total / per_page))
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

def send_email(to_address, subject, html_body):
    smtp_user = os.getenv("SMTP_USER", "artemcool200911@gmail.com")
    app_pass = os.getenv("EMAIL_PASS")
    if not app_pass or not smtp_user:
        print("Помилка: SMTP_USER або EMAIL_PASS не налаштовано в .env")
        return False
    msg = MIMEMultipart()
    msg["From"] = f"Магазин НОВА ХВИЛЯ <{smtp_user}>"
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(smtp_user, app_pass)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Помилка при відправці email: {e}")
        return False

def send_telegram_notification(order, items):
    webhook_url = os.getenv("MAKE_WEBHOOK_URL")
    if not webhook_url: return
    products_list = ""
    for item in items:
        products_list += f"▫️ {item.product.name} ({item.quantity} шт) - {int(item.price * item.quantity)} грн\n"
    message = (
        f"📦 <b>НОВЕ ЗАМОВЛЕННЯ #{order.id}</b>\n\n"
        f"👤 <b>Клієнт:</b> {order.customer_name}\n"
        f"📞 <b>Телефон:</b> {order.customer_phone}\n\n"
        f"🛒 <b>Товари:</b>\n{products_list}\n"
        f"💰 <b>Сума:</b> {int(order.total_cost)} грн\n"
        f"🚚 <b>Доставка:</b> {order.delivery_method}\n"
        f"💳 <b>Оплата:</b> {order.payment_method}\n"
        f"💬 <b>Комент:</b> {order.comment or 'Немає'}"
    )
    try:
        requests.post(webhook_url, json={"text": message, "parse_mode": "HTML"}, timeout=5)
    except Exception as e:
        print(f"Telegram Error: {e}")

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

def _get_cloudinary_url(image_filename):
    if not image_filename or not image_filename.strip(): return "/static/img/no_image.png"
    try:
        return cloudinary.utils.cloudinary_url(f"products/products/{os.path.splitext(image_filename)[0]}", secure=True, fetch_format="auto", quality="auto", transformation=[{'dpr': "auto"}])[0]
    except Exception as e:
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