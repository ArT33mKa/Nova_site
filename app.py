import os
import re
import math
import locale
import logging
import smtplib
import requests  # для Telegram та Нової Пошти
import traceback
import firebase_admin
from firebase_admin import credentials, auth
import json
import random
from datetime import timezone
import secrets
from itsdangerous import URLSafeTimedSerializer
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from twilio.rest import Client
import cloudinary
import cloudinary.utils
import cloudinary.uploader # <--- ОБОВ'ЯЗКОВО ДОДАТИ ЦЕ
from functools import wraps
from datetime import datetime, timedelta
from dotenv import load_dotenv
from collections import Counter
from sqlalchemy import func, and_, or_ as db_or, select
from email.mime.text import MIMEText
from lxml import etree as lxml_etree
from flask_sqlalchemy import SQLAlchemy
from email.mime.multipart import MIMEMultipart
from flask_dance.consumer import oauth_authorized
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_dance.consumer.storage.sqla import SQLAlchemyStorage
from flask_dance.contrib.google import make_google_blueprint, google
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, make_response, render_template, request, redirect, url_for, session, jsonify, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import xml.etree.ElementTree as ET
from werkzeug.exceptions import Unauthorized

try:
    locale.setlocale(locale.LC_TIME, 'uk_UA.UTF-8')
except locale.Error:
    pass
try:
    # Для Fly.io (змінна середовища)
    firebase_creds_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
    if firebase_creds_json:
        cred_dict = json.loads(firebase_creds_json)
        cred = credentials.Certificate(cred_dict)
    else:
        # Для локальної розробки (файл)
        cred = credentials.Certificate("firebase-service-account.json")

    firebase_admin.initialize_app(cred)
    print(">>> Firebase Admin SDK успішно ініціалізовано.")
except Exception as e:
    print(f">>> ПОМИЛКА ініціалізації Firebase Admin SDK: {e}")

load_dotenv()
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# --- [ДОДАНО] Налаштування логера для подій безпеки ---
security_logger = logging.getLogger('security')
security_handler = logging.FileHandler('security.log')
security_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
security_logger.addHandler(security_handler)
security_logger.setLevel(logging.INFO)

# --- [ДОДАНО] Налаштування лімітера запитів (Rate Limiter) ---
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
    strategy="fixed-window"
)

if __name__ != '__main__':
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
    app.logger.info('>>> Логування Flask інтегровано з Gunicorn.')
else:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    app.logger.info('>>> Запущено в режимі розробки, використано basicConfig.')

try:
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        secure=True
    )
    print(">>> Cloudinary успішно налаштовано.")
except Exception as e:
    print(f">>> ПОМИЛКА конфігурації Cloudinary: {e}")

app.jinja_env.add_extension('jinja2.ext.do')
app.secret_key = os.getenv("FLASK_SECRET", "nova-secret")

database_url = os.getenv('DATABASE_URL', 'sqlite:///site.db')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["GOOGLE_OAUTH_CLIENT_ID"] = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
app.config["GOOGLE_OAUTH_CLIENT_SECRET"] = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")

db = SQLAlchemy(app)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(64), unique=True, nullable=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    children = db.relationship('Category',
                               backref=db.backref('parent', remote_side=[id]),
                               lazy='dynamic')
    products = db.relationship('Product', backref='category_rel', lazy='dynamic')

    def __repr__(self):
        return f'<Category {self.name}>'


def slugify(text):
    if not text:
        return ""
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
        if char in translit_map:
            result.append(translit_map[char])
        elif char.isalnum():
            result.append(char)
        elif char.isspace() or char == '-':
            result.append('-')
    text = "".join(result)
    text = text.lower()
    text = re.sub(r'[^a-z0-9-]', '', text)
    text = re.sub(r'-+', '-', text).strip('-')
    return text

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Будь ласка, увійдіть, щоб виконати цю дію."
login_manager.login_message_category = "info"

def send_email(to_address, subject, html_body):
    smtp_user = os.getenv("SMTP_USER", "artemcool200911@gmail.com")
    app_pass = os.getenv("EMAIL_PASS")
    if not app_pass or not smtp_user:
        print("Помилка: SMTP_USER або EMAIL_PASS не налаштовано в .env")
        return False
    msg = MIMEMultipart()
    msg["From"] = f"Магазин {shop_info['name']} <{smtp_user}>"
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
    if not webhook_url:
        print(">>> ПОМИЛКА Make.com: URL вебхука не вказано в .env")
        return
    product_names = ", ".join([f"{item['product'].name} ({item['quantity']} шт)" for item in items])
    delivery_details = order.delivery_method
    if order.delivery_method == 'Нова Пошта':
        delivery_details += f" ({order.delivery_city}, {order.delivery_warehouse})"
    payload = {
        "order_id": order.id, "order_status": order.status, "customer_name": order.customer_name,
        "customer_phone": order.customer_phone, "product_name": product_names,
        "delivery_method": delivery_details, "payment_method": order.payment_method,
        "total_cost": f"{order.total_cost:.2f} ₴"
    }
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code == 200 and "Accepted" in response.text:
            print(f">>> Make.com: Дані про замовлення #{order.id} успішно надіслано!")
        else:
            print(f">>> Make.com: Помилка відповіді від сервера - {response.status_code} {response.text}")
    except requests.exceptions.RequestException as e:
        print(f">>> Make.com: КРИТИЧНА ПОМИЛКА при відправці сповіщення: {e}")


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    is_email_verified = db.Column(db.Boolean, default=False)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    avatar_url = db.Column(db.String(255), nullable=True)
    reviews = db.relationship('Review', backref='author', lazy='dynamic')
    orders = db.relationship('Order', backref='customer', lazy='dynamic')
    cart_items = db.relationship('CartItem', back_populates='user', lazy='dynamic', cascade="all, delete-orphan")

    def get_email_verify_token(self):
        s = URLSafeTimedSerializer(app.secret_key)
        return s.dumps({'user_id': self.id, 'email': self.email})

    @staticmethod
    def verify_email_token(token, max_age=86400):
        s = URLSafeTimedSerializer(app.secret_key)
        try:
            data = s.loads(token, max_age=max_age)
            user_id = data.get('user_id')
            email = data.get('email')
        except Exception:
            return None, None
        return User.query.get(user_id), email

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_reset_token(self):
        s = URLSafeTimedSerializer(app.secret_key)
        return s.dumps({'user_id': self.id})

    @staticmethod
    def verify_reset_token(token, max_age=1800):
        s = URLSafeTimedSerializer(app.secret_key)
        try:
            data = s.loads(token, max_age=max_age)
            user_id = data.get('user_id')
        except Exception:
            return None
        return User.query.get(user_id)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    image = db.Column(db.String(255), nullable=True)
    category = db.Column(db.String(100))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    in_stock = db.Column(db.Boolean, default=True)
    rating = db.Column(db.Float, default=0.0)
    reviews_count = db.Column(db.Integer, default=0)
    reviews = db.relationship('Review', backref='product', lazy='dynamic', cascade="all, delete-orphan")


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False, default=0)
    text = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    author_name = db.Column(db.String(100), nullable=True)
    author_email = db.Column(db.String(120), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    review_type = db.Column(db.String(50), nullable=False, default='review')
    parent_id = db.Column(db.Integer, db.ForeignKey('review.id'), nullable=True)
    replies = db.relationship('Review', backref=db.backref('parent', remote_side=[id]), lazy='dynamic',
                              cascade="all, delete-orphan", order_by='Review.timestamp.asc()')


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(50), nullable=False, default='Нове')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    delivery_method = db.Column(db.String(50))
    delivery_city = db.Column(db.String(100), nullable=True)
    delivery_warehouse = db.Column(db.String(255), nullable=True)
    payment_method = db.Column(db.String(50))
    total_cost = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    items = db.relationship('OrderItem', backref='order', lazy='dynamic', cascade="all, delete-orphan")
    comment = db.Column(db.Text, nullable=True)


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    product = db.relationship('Product')


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    user = db.relationship('User', back_populates='cart_items')
    product = db.relationship('Product')
    __table_args__ = (db.UniqueConstraint('user_id', 'product_id', name='_user_product_uc'),)

class CategoryView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    views = db.Column(db.Integer, default=0)

class OAuth(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    token = db.Column(db.JSON, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship(User)


google_blueprint = make_google_blueprint(scope=["openid", "https://www.googleapis.com/auth/userinfo.email",
                                                "https://www.googleapis.com/auth/userinfo.profile"],
                                         storage=SQLAlchemyStorage(OAuth, db.session, user=current_user))
app.register_blueprint(google_blueprint, url_prefix="/login")

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


@login_manager.user_loader
def load_user(user_id): return db.session.get(User, int(user_id))

def email_verified_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_email_verified:
            flash('Будь ласка, підтвердіть вашу електронну пошту, щоб продовжити.', 'warning')
            return redirect(url_for('profile_settings'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Доступ до цієї сторінки мають тільки адміністратори.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


def merge_session_cart_to_db(user):
    session_cart = session.get('cart')
    if not session_cart:
        return

    db_cart_items = {item.product_id: item for item in user.cart_items}

    for product_id_str, quantity in session_cart.items():
        product_id = int(product_id_str)
        if product_id in db_cart_items:
            db_cart_items[product_id].quantity += quantity
        else:
            new_item = CartItem(user_id=user.id, product_id=product_id, quantity=quantity)
            db.session.add(new_item)

    db.session.commit()
    session.pop('cart', None)


@app.context_processor
def inject_now(): return {'now': datetime.now(timezone.utc), 'shop': shop_info}


@app.route("/")
@app.route("/")
def index():
    hero_slides = [
        {'image': 'hero-bg.jpg', 'title': 'Професійна сантехніка та обладнання',
         'subtitle': 'Якісні товари для вашого дому з гарантією та доставкою'},
        {'image': 'hero-bg2.jpg', 'title': 'Надійні насоси для будь-яких потреб',
         'subtitle': 'Від найкращих виробників'},
        {'image': 'kotly.jpg', 'title': 'Все для систем опалення', 'subtitle': 'Котли, бойлери та комплектуючі'}
    ]

    popular_products_query = db.session.query(
        Product,
        func.sum(OrderItem.quantity).label('total_sold')
    ).join(OrderItem, OrderItem.product_id == Product.id) \
        .group_by(Product.id) \
        .order_by(func.sum(OrderItem.quantity).desc()) \
        .limit(5).all()

    products = [p[0] for p in popular_products_query]

    main_categories_hierarchy = get_category_hierarchy()

    def get_icon_for_category(name):
        n = name.lower()
        if 'насос' in n or 'станці' in n: return 'fas fa-water'
        if 'бойлер' in n or 'нагрівач' in n: return 'fas fa-temperature-high'
        if 'змішувач' in n or 'кран' in n or 'сифон' in n or 'мик' in n: return 'fas fa-sink'
        if 'вентиляц' in n or 'витяжк' in n or 'домовент' in n: return 'fas fa-fan'
        if 'газ' in n or 'колонк' in n or 'пальник' in n: return 'fas fa-fire'
        if 'опалення' in n or 'радіатор' in n or 'тепла підлога' in n: return 'fas fa-fire-alt'
        if 'труб' in n or 'фітинг' in n: return 'fas fa-project-diagram'
        if 'ванна' in n or 'душ' in n: return 'fas fa-bath'
        if 'кухня' in n: return 'fas fa-utensils'
        if 'автоматика' in n or 'електрика' in n: return 'fas fa-microchip'
        if 'інструмент' in n: return 'fas fa-tools'
        if 'полив' in n: return 'fas fa-cloud-rain'
        return 'fas fa-box-open'

    dynamic_categories = []
    for cat_name in sorted(main_categories_hierarchy.keys()):
        dynamic_categories.append({
            'name': cat_name,
            'icon': get_icon_for_category(cat_name)
        })

    return render_template("index.html", products=products, hero_slides=hero_slides, main_categories=dynamic_categories)


def get_category_hierarchy():
    root_categories = Category.query.filter_by(parent_id=None).order_by(Category.name).all()
    hierarchy = {}
    DEFAULT_ICONS = {
        'Поливочна система': 'irrigation.jpg',
        'Насоси та гідрофори': 'pumps.jpg',
        'Водонагрівачі': 'boilers.jpg',
        'Змішувачі та сифони': 'faucets.jpg',
        'Вентиляція та витяжки': 'hoods.jpg',
        'Газове обладнання': 'gas_columns.jpg',
        'Опалення та водопостачання': 'towel_dryers.jpg',
        'Запчастини та комплектуючі': 'gas_parts.jpg'
    }
    for parent in root_categories:
        subcats = {}
        children_total_items = 0
        children = parent.children.order_by(Category.name).all()
        for child in children:
            child_count = child.products.filter_by(in_stock=True).count()
            if child_count > 0:
                subcats[child.name] = {
                    'slug': child.slug,
                    'count': child_count
                }
                children_total_items += child_count
        parent_direct_count = parent.products.filter_by(in_stock=True).count()
        total_category_count = parent_direct_count + children_total_items
        if total_category_count > 0:
            hierarchy[parent.name] = {
                'slug': parent.slug,
                'icon': DEFAULT_ICONS.get(parent.name, 'gas_parts.jpg'),
                'subcategories': subcats,
                'count': total_category_count,
                'direct_count': parent_direct_count
            }
    return hierarchy


@app.route('/catalog/', defaults={'category_slug': None})
@app.route('/catalog/<path:category_slug>/')
def catalog(category_slug):
    page = request.args.get('page', 1, type=int)
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    search_query = request.args.get('search', '').strip()

    query = Product.query.filter(
        Product.in_stock == True,
        Product.image.notlike('default_tovar%')
    )

    current_category_name = None
    main_category_of_current = None
    parent_category_slug = None

    if category_slug:
        clean_slug = category_slug.strip('/')
        target_slug = clean_slug.split('/')[-1]
        category = Category.query.filter_by(slug=target_slug).first()

        if category:
            current_category_name = category.name
            categories_ids = [category.id]
            for child in category.children:
                categories_ids.append(child.id)
            query = query.filter(Product.category_id.in_(categories_ids))
            if category.parent:
                main_category_of_current = category.parent.name
                parent_category_slug = category.parent.slug
            else:
                main_category_of_current = category.name
                parent_category_slug = category.slug
            try:
                cat_view = CategoryView.query.filter_by(name=category.name).first()
                if not cat_view:
                    cat_view = CategoryView(name=category.name)
                    db.session.add(cat_view)
                cat_view.views += 1
                db.session.commit()
            except:
                db.session.rollback()
        else:
            cat_name_approx = clean_slug.replace('-', ' ').replace('/', ' ')
            query = query.filter(Product.category.ilike(f"%{cat_name_approx}%"))
            current_category_name = cat_name_approx.capitalize()

    if search_query:
        query = query.filter(Product.name.ilike(f'%{search_query}%'))

    price_stats_query = db.session.query(func.min(Product.price), func.max(Product.price))
    if query.whereclause is not None:
        price_stats_query = price_stats_query.filter(query.whereclause)

    price_stats = price_stats_query.first()
    min_available = math.floor(price_stats[0] or 0)
    max_available = math.ceil(price_stats[1] or 0)

    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    products = query.order_by(Product.id.desc()).paginate(page=page, per_page=20, error_out=False)

    hierarchy = get_category_hierarchy()

    return render_template(
        'catalog.html',
        products=products,
        hierarchy=hierarchy,
        current_category=current_category_name,
        main_category_of_current=main_category_of_current,
        parent_category_slug=parent_category_slug,
        category_slug=category_slug,
        min_price_available=min_available,
        max_price_available=max_available,
        search_query=search_query
    )


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    similar_products = Product.query.filter(Product.category == product.category, Product.id != product.id,
                                            Product.in_stock == True,
                                            and_(Product.description != None, Product.description != ''),
                                            Product.image.notlike('default_tovar%')).limit(8).all()
    return render_template("product_detail.html", product=product, similar_products=similar_products)


@app.route('/get_products_by_ids', methods=['POST'])
def get_products_by_ids():
    product_ids = request.json.get('ids', [])
    if not product_ids: return jsonify([])
    try:
        safe_product_ids = [int(pid) for pid in product_ids]
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid IDs provided'}), 400
    products = Product.query.filter(Product.id.in_(safe_product_ids)).all()

    products_data = [
        {'id': p.id, 'name': p.name, 'price': p.price, 'image': p.image, 'in_stock': p.in_stock,
         'url': url_for('product_detail', product_id=p.id)} for p in products]

    return jsonify(products_data)


def get_reviews_data(product_id):
    product = Product.query.get_or_404(product_id)
    all_reviews_and_questions = product.reviews.order_by(Review.timestamp.desc())
    reviews_only = [r for r in all_reviews_and_questions if r.review_type == 'review' and r.parent_id is None]
    questions_only = [q for q in all_reviews_and_questions if q.review_type == 'question' and q.parent_id is None]
    reviews_with_rating = [r for r in reviews_only if r.rating > 0]
    total_with_rating_count = len(reviews_with_rating)
    rating_counts = Counter([r.rating for r in reviews_with_rating])
    rating_breakdown = {star: rating_counts.get(star, 0) for star in range(5, 0, -1)}
    return {'product': product, 'reviews': reviews_only, 'questions': questions_only,
            'review_only_count': len(reviews_only), 'rating_breakdown': rating_breakdown,
            'total_reviews_with_rating': total_with_rating_count}


@app.route("/product/<int:product_id>/reviews")
def product_reviews(product_id):
    data = get_reviews_data(product_id)
    return render_template("reviews.html", **data, active_tab='reviews')


@app.route("/product/<int:product_id>/questions")
def product_questions(product_id):
    data = get_reviews_data(product_id)
    return render_template("questions.html", **data, active_tab='questions')


@app.route('/product/<int:product_id>/add_review', methods=['POST'])
def add_review(product_id):
    product = Product.query.get_or_404(product_id)
    form = request.form
    new_review_data = {'product_id': product_id, 'text': form.get('text'),
                       'author_name': form.get('author_name', 'Анонім'), 'author_email': form.get('author_email'),
                       'review_type': form.get('review_type', 'review'),
                       'parent_id': form.get('parent_id') if form.get('parent_id') else None}
    if new_review_data['review_type'] == 'review': new_review_data['rating'] = int(form.get('rating', 0))
    if current_user.is_authenticated:
        new_review_data['user_id'] = current_user.id
        new_review_data['author_name'] = current_user.first_name or current_user.username
    db.session.add(Review(**new_review_data))
    if new_review_data['review_type'] == 'review' and not new_review_data['parent_id']:
        result = db.session.query(func.avg(Review.rating), func.count(Review.id)).filter(
            Review.product_id == product_id, Review.rating > 0).one()
        product.rating = float(result[0] or 0)
        product.reviews_count = int(result[1] or 0)
    db.session.commit()
    flash('Дякуємо! Ваш запис було успішно додано.', 'success')
    return redirect(url_for('product_questions' if request.form.get('review_type') == 'question' else 'product_reviews',
                            product_id=product_id))


# ────────────────────────────────
#  АВТЕНТИФІКАЦІЯ
# ────────────────────────────────
@app.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    data = request.get_json()
    email = data.get('email')
    user = User.query.filter_by(email=email).first()
    ip_address = get_remote_address()

    if user and user.password_hash and user.check_password(data.get('password')):
        login_user(user, remember=True)
        merge_session_cart_to_db(user)
        security_logger.info(f"Successful login for user '{email}' from IP: {ip_address}")
        return jsonify({"status": "success"})

    security_logger.warning(f"Failed login attempt for email '{email}' from IP: {ip_address}")
    return jsonify({"status": "error", "message": "Невірний email або пароль"}), 401


@app.route("/register", methods=["POST"])
@limiter.limit("10 per hour")
def register():
    data = request.get_json()
    email, first_name, last_name, phone = data.get('email'), data.get('first_name'), data.get('last_name'), data.get('phone')

    if not all([email, first_name, last_name, data.get('password')]):
        return jsonify({"status": "error", "message": "Ім'я, Прізвище, Email та Пароль є обов'язковими"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"status": "error", "message": "Цей email вже зареєстровано"}), 400

    username_base = first_name.strip()
    username, counter = username_base, 1
    while User.query.filter_by(username=username).first():
        username = f"{username_base}_{counter}"
        counter += 1

    new_user = User(first_name=first_name, last_name=last_name, phone=phone, email=email, username=username)
    new_user.set_password(data.get('password'))
    db.session.add(new_user)
    db.session.commit()
    login_user(new_user, remember=True)
    merge_session_cart_to_db(new_user)
    send_email(new_user.email, f"Вітаємо у {shop_info['name']}!",
               render_template("email/welcome.html", user=new_user, shop=shop_info))

    security_logger.info(f"New user registered: '{email}' from IP: {get_remote_address()}")
    return jsonify({"status": "success"})


@app.route("/logout")
@login_required
def logout():
    security_logger.info(f"User '{current_user.email}' logged out.")
    logout_user()
    flash("Ви успішно вийшли з акаунту.", "success")
    return redirect(url_for('index'))


@oauth_authorized.connect_via(google_blueprint)
def google_logged_in(blueprint, token):
    if not token:
        flash("Не вдалося увійти через Google.", category="error")
        return redirect(url_for("index"))

    resp = blueprint.session.get("/oauth2/v2/userinfo")
    if not resp.ok:
        flash("Не вдалося отримати дані від Google.", category="error")
        return redirect(url_for("index"))

    google_info = resp.json()
    email = google_info["email"]

    user = User.query.filter_by(email=email).first()

    if user and user.phone:
        login_user(user, remember=True)
        merge_session_cart_to_db(user)
        return redirect(url_for("index"))

    session['oauth_register_data'] = {
        'email': email,
        'first_name': google_info.get("given_name", ""),
        'last_name': google_info.get("family_name", ""),
        'avatar_url': google_info.get('picture'),
        'provider': 'google'
    }
    return redirect(url_for('complete_registration'))


@app.route('/complete-registration')
def complete_registration():
    if 'oauth_register_data' not in session:
        return redirect(url_for('index'))
    return render_template('index.html', show_complete_reg_modal=True)


@app.route('/api/auth/finalize_google', methods=['POST'])
def finalize_google_registration():
    if 'oauth_register_data' not in session:
        return jsonify({'status': 'error', 'message': 'Сесія Google закінчилася. Спробуйте увійти знову.'}), 400

    data = request.get_json()
    firebase_token = data.get('firebase_token')
    password = data.get('password')

    if not firebase_token or not password:
        return jsonify({'status': 'error', 'message': 'Телефон та пароль є обов\'язковими'}), 400

    if len(password) < 6:
        return jsonify({'status': 'error', 'message': 'Пароль має бути не менше 6 символів'}), 400

    try:
        decoded_token = auth.verify_id_token(firebase_token)
        phone = decoded_token.get('phone_number')

        if not phone:
            return jsonify({'status': 'error', 'message': 'Не вдалося підтвердити номер телефону'}), 400

        if User.query.filter_by(phone=phone).first():
            return jsonify(
                {'status': 'error', 'message': 'Цей номер телефону вже використовується іншим акаунтом'}), 409

        oauth_data = session['oauth_register_data']
        email = oauth_data['email']

        user = User.query.filter_by(email=email).first()

        if user:
            user.phone = phone
            user.set_password(password)
            if not user.first_name: user.first_name = oauth_data['first_name']
            if not user.last_name: user.last_name = oauth_data['last_name']
            if not user.avatar_url: user.avatar_url = oauth_data['avatar_url']
            user.is_email_verified = True
        else:
            username_base = oauth_data['first_name'].lower().strip() or "user"
            username, counter = username_base, 1
            while User.query.filter_by(username=username).first():
                username = f"{username_base}{counter}"
                counter += 1

            user = User(
                email=email,
                username=username,
                first_name=oauth_data['first_name'],
                last_name=oauth_data['last_name'],
                phone=phone,
                avatar_url=oauth_data['avatar_url'],
                is_email_verified=True
            )
            user.set_password(password)
            db.session.add(user)

        db.session.commit()

        login_user(user, remember=True)
        merge_session_cart_to_db(user)
        session.pop('oauth_register_data', None)

        return jsonify({'status': 'success'})

    except Exception as e:
        app.logger.error(f"Google Finalize Error: {e}")
        return jsonify({'status': 'error', 'message': 'Помилка сервера при реєстрації'}), 500

@app.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        ip_address = get_remote_address()

        if user:
            token = user.get_reset_token()
            html_body = render_template('email/password_reset.html', user=user, token=token, shop=shop_info)
            send_email(user.email, f"Відновлення пароля для {shop_info['name']}", html_body)
            security_logger.info(f"Password reset requested for '{email}' from IP: {ip_address}")
            flash('Інструкції для відновлення пароля надіслано на вашу пошту.', 'info')
            return redirect(url_for('index'))
        else:
            security_logger.warning(f"Password reset attempt for non-existent email '{email}' from IP: {ip_address}")
            flash('Якщо такий email існує, на нього буде надіслано лист.', 'info')

    return render_template('auth/forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def reset_password(token):
    user = User.verify_reset_token(token)
    if not user:
        flash('Токен для відновлення пароля недійсний або застарілий.', 'danger')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        if password and password == confirm_password and len(password) >= 6:
            user.set_password(password)
            db.session.commit()
            security_logger.info(f"Password successfully reset for user '{user.email}'")
            flash('Ваш пароль успішно оновлено. Тепер ви можете увійти.', 'success')
            return redirect(url_for('index'))
        else:
            flash('Паролі не співпадають або занадто короткі (мінімум 6 символів).', 'danger')

    return render_template('auth/reset_password.html', token=token)

# ────────────────────────────────
#  КОШИК ТА ОФОРМЛЕННЯ ЗАМОВЛЕННЯ
# ────────────────────────────────
@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    product_id = int(request.get_json().get("product_id"))

    if current_user.is_authenticated:
        cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
        if cart_item:
            cart_item.quantity += 1
        else:
            cart_item = CartItem(user_id=current_user.id, product_id=product_id, quantity=1)
            db.session.add(cart_item)
        db.session.commit()
        cart_count = sum(item.quantity for item in current_user.cart_items)
    else:
        cart = session.get("cart", {})
        product_id_str = str(product_id)
        cart[product_id_str] = cart.get(product_id_str, 0) + 1
        session["cart"] = cart
        cart_count = sum(cart.values())

    return jsonify(status="success", message="Товар додано до кошика", cart_count=cart_count)


@app.route('/update_cart_quantity/<int:product_id>', methods=['POST'])
def update_cart_quantity(product_id):
    new_quantity = request.json.get('quantity')

    if current_user.is_authenticated:
        cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
        if cart_item:
            if new_quantity and new_quantity > 0:
                cart_item.quantity = new_quantity
            else:
                db.session.delete(cart_item)
            db.session.commit()
            return jsonify(status="success")
    else:
        cart = session.get("cart", {})
        product_id_str = str(product_id)
        if product_id_str in cart:
            if new_quantity and new_quantity > 0:
                cart[product_id_str] = new_quantity
            else:
                del cart[product_id_str]
            session["cart"] = cart
            return jsonify(status="success")

    return jsonify(status="error", message="Товар не знайдено"), 404


@app.route('/get_cart')
@limiter.exempt
def get_cart():
    cart_items, total = [], 0

    if current_user.is_authenticated:
        db_cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        for item in db_cart_items:
            product = item.product
            if product:
                cart_items.append({
                    "id": product.id, "name": product.name, "price": product.price,
                    "image": product.image, "quantity": item.quantity,
                    "in_stock": product.in_stock, "url": url_for('product_detail', product_id=product.id)
                })
                total += product.price * item.quantity
    else:
        cart = session.get("cart", {})
        if cart:
            product_ids = [int(pid) for pid in cart.keys() if pid.isdigit()]
            products = Product.query.filter(Product.id.in_(product_ids)).all()
            product_map = {str(p.id): p for p in products}
            for product_id, quantity in cart.items():
                if product := product_map.get(product_id):
                    cart_items.append({
                        "id": product.id, "name": product.name, "price": product.price,
                        "image": product.image, "quantity": quantity,
                        "in_stock": product.in_stock, "url": url_for('product_detail', product_id=product.id)
                    })
                    total += product.price * quantity

    return jsonify({"items": cart_items, "total": total})


@app.route("/remove_from_cart/<int:product_id>", methods=["POST"])
def remove_from_cart(product_id):
    if current_user.is_authenticated:
        CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).delete()
        db.session.commit()
    else:
        cart = session.get("cart", {})
        if str(product_id) in cart:
            del cart[str(product_id)]
        session["cart"] = cart
    return jsonify(status="success")


@app.route('/buy_now', methods=['POST'])
def buy_now():
    product_id = int(request.get_json().get("product_id"))

    if current_user.is_authenticated:
        CartItem.query.filter_by(user_id=current_user.id).delete()
        new_item = CartItem(user_id=current_user.id, product_id=product_id, quantity=1)
        db.session.add(new_item)
        db.session.commit()
    else:
        session["cart"] = {str(product_id): 1}

    return jsonify(status="success")


@app.route('/api/auth/start_email_login', methods=['POST'])
def start_email_login():
    data = request.get_json()
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'status': 'error', 'message': 'Email є обов\'язковим'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'status': 'error',
                        'message': 'Акаунт з такою email-адресою не знайдено. Будь ласка, зареєструйтесь.'}), 404

    code = str(random.randint(100000, 999999))
    session['verification_email'] = email
    session['verification_code'] = code
    session.permanent = True

    html_body = render_template("email/verification_code.html", code=code, shop=shop_info)
    if send_email(email, f"Код входу для {shop_info['name']}", html_body):
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': 'Не вдалося надіслати лист.'}), 500


@app.route('/api/auth/verify_email_code', methods=['POST'])
def verify_email_code():
    data = request.get_json()
    code_from_user = data.get('code')
    expected_code = session.get('verification_code')
    email = session.get('verification_email')

    if not all([expected_code, email, code_from_user]):
        return jsonify({'status': 'error', 'message': 'Сесія застаріла, спробуйте ще раз'}), 400

    if code_from_user != expected_code:
        return jsonify({'status': 'error', 'message': 'Невірний код підтвердження'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        username_base = email.split('@')[0]
        username, counter = username_base, 1
        while User.query.filter_by(username=username).first():
            username = f"{username_base}_{counter}"
            counter += 1

        user = User(
            email=email,
            username=username,
            first_name="",
            last_name=""
        )
        db.session.add(user)
        db.session.commit()

    login_user(user, remember=True)
    merge_session_cart_to_db(user)
    session.pop('verification_code', None)
    session.pop('verification_email', None)

    return jsonify({'status': 'success'})


@app.route('/api/auth/check_user_exists', methods=['POST'])
def check_user_exists():
    phone = request.json.get('phone')
    if not phone:
        return jsonify({'exists': False, 'error': 'Phone number is required'}), 400
    user = User.query.filter_by(phone=phone).first()
    return jsonify({'exists': user is not None})


@app.route('/api/auth/firebase_verify', methods=['POST'])
def firebase_verify():
    token = request.json.get('token')
    intent = request.json.get('intent')
    if not token or not intent:
        return jsonify({'status': 'error', 'message': 'Не вистачає даних (токен або намір)'}), 400

    try:
        decoded_token = auth.verify_id_token(token)
        phone = decoded_token.get('phone_number')
        if not phone:
            return jsonify({'status': 'error', 'message': 'Firebase токен не містить номер телефону'}), 400

        user = User.query.filter_by(phone=phone).first()

        if intent == 'login':
            if not user:
                return jsonify(
                    {'status': 'error', 'message': 'Помилка: Користувача не знайдено, хоча він мав існувати'}), 404


        elif intent == 'register':

            if user:
                return jsonify({'status': 'error', 'message': 'Цей номер вже зареєстровано'}), 409

            first_name = request.json.get('first_name')
            last_name = request.json.get('last_name')
            password = request.json.get('password')

            if not all([first_name, last_name, password]):
                return jsonify({'status': 'error', 'message': 'Ім\'я, прізвище та пароль є обов\'язковими'}), 400

            base_email = f"{phone.replace('+', '')}@temp.user"
            email, counter = base_email, 1
            while User.query.filter_by(email=email).first():
                email = f"{phone.replace('+', '')}_{counter}@temp.user"
                counter += 1

            username_base = first_name.strip().lower() or "user"
            username, counter = username_base, 1
            while User.query.filter_by(username=username).first():
                username = f"{username_base}_{counter}"
                counter += 1

            new_user = User(
                phone=phone,
                first_name=first_name,
                last_name=last_name,
                email=email,
                username=username
            )
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            user = new_user

        else:
            return jsonify({'status': 'error', 'message': 'Невідома дія'}), 400

        login_user(user, remember=True)
        merge_session_cart_to_db(user)
        return jsonify({'status': 'success'})

    except auth.InvalidIdTokenError:
        app.logger.error("Firebase token verification failed: Invalid ID token")
        return jsonify({'status': 'error', 'message': 'Недійсний токен авторизації'}), 401
    except Exception as e:
        app.logger.error(f"Firebase token verification failed: {e}")
        return jsonify({'status': 'error', 'message': 'Невірний токен або помилка сервера'}), 500

@app.route('/api/settings/update_phone', methods=['POST'])
@login_required
def update_phone_number():
    token = request.json.get('token')
    if not token:
        return jsonify({'status': 'error', 'message': 'Відсутній токен верифікації'}), 400

    try:
        decoded_token = auth.verify_id_token(token)
        phone_from_token = decoded_token.get('phone_number')

        if not phone_from_token:
            return jsonify({'status': 'error', 'message': 'Не вдалося отримати номер з токену'}), 400

        existing_user = User.query.filter(User.phone == phone_from_token, User.id != current_user.id).first()
        if existing_user:
            return jsonify({'status': 'error', 'message': 'Цей номер телефону вже прив\'язаний до іншого акаунту'}), 409

        current_user.phone = phone_from_token
        db.session.commit()
        session.pop('hide_phone_prompt', None)

        return jsonify({'status': 'success', 'message': 'Номер телефону успішно підтверджено та оновлено!'})

    except auth.InvalidIdTokenError:
        return jsonify({'status': 'error', 'message': 'Недійсний токен авторизації'}), 401
    except Exception as e:
        app.logger.error(f"Phone update error for user {current_user.id}: {e}")
        return jsonify({'status': 'error', 'message': 'Сталася помилка на сервері'}), 500

@app.route('/profile/resend-verification', methods=['POST'])
@login_required
def resend_verification_email():
    if current_user.is_email_verified:
        flash('Ваш email вже підтверджено.', 'info')
        return redirect(url_for('profile_settings'))
    if current_user.email.endswith('@temp.user'):
        flash('Будь ласка, спочатку вкажіть дійсну адресу електронної пошти.', 'danger')
        return redirect(url_for('profile_settings'))
    try:
        token = current_user.get_email_verify_token()
        html_body = render_template('email/verify_email.html', user=current_user, token=token, shop=shop_info)
        send_email(current_user.email, f"Підтвердження email для {shop_info['name']}", html_body)
        flash('Новий лист для підтвердження надіслано на вашу пошту.', 'success')
    except Exception as e:
        app.logger.error(f"Error resending verification email for {current_user.email}: {e}")
        flash('Не вдалося надіслати лист. Спробуйте пізніше.', 'danger')
    return redirect(url_for('profile_settings'))

@app.route('/verify-email/<token>')
def verify_email(token):
    user, email_from_token = User.verify_email_token(token)
    if not user or user.email != email_from_token:
        flash('Посилання для верифікації недійсне або застаріле.', 'danger')
        return redirect(url_for('index'))
    if user.is_email_verified:
        flash('Цей email вже було підтверджено.', 'info')
    else:
        user.is_email_verified = True
        db.session.commit()
        flash('Дякуємо! Ваш email успішно підтверджено.', 'success')
    if current_user.is_authenticated and current_user.id == user.id:
        return redirect(url_for('profile_settings'))
    else:
        login_user(user)
        return redirect(url_for('index'))


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart_items_display = []
    total_cost = 0

    if current_user.is_authenticated:
        is_cart_empty = not db.session.query(CartItem.query.filter_by(user_id=current_user.id).exists()).scalar()
    else:
        is_cart_empty = not session.get('cart')

    if is_cart_empty:
        flash('Ваш кошик порожній.', 'info')
        return redirect(url_for('catalog'))

    if current_user.is_authenticated:
        items = current_user.cart_items.all()
        for item in items:
            item_total = item.product.price * item.quantity
            total_cost += item_total
            cart_items_display.append({
                'product': item.product,
                'quantity': item.quantity,
                'item_total': item_total
            })
    else:
        cart_session = session.get('cart', {})
        if cart_session:
            product_ids = [int(pid) for pid in cart_session.keys()]
            products = Product.query.filter(Product.id.in_(product_ids)).all()
            product_map = {p.id: p for p in products}

            for pid_str, qty in cart_session.items():
                product = product_map.get(int(pid_str))
                if product:
                    item_total = product.price * qty
                    total_cost += item_total
                    cart_items_display.append({
                        'product': product,
                        'quantity': qty,
                        'item_total': item_total
                    })

    if request.method == 'POST':
        errors = []
        first_name = request.form.get('customer_first_name', '').strip()
        last_name = request.form.get('customer_last_name', '').strip()
        customer_phone = request.form.get('customer_phone', '').strip()
        delivery_method = request.form.get('delivery_method')
        payment_method = request.form.get('payment_method')
        delivery_city = request.form.get('delivery_city', '').strip()
        delivery_warehouse = request.form.get('delivery_warehouse', '').strip()

        if not all([first_name, last_name, customer_phone]):
            errors.append("Ім'я, прізвище та номер телефону є обов'язковими.")

        phone_digits = re.sub(r'\D', '', customer_phone)
        if len(phone_digits) != 12:
            errors.append("Будь ласка, введіть повний номер телефону.")

        if not delivery_method:
            errors.append("Будь ласка, оберіть спосіб доставки.")
        elif delivery_method == 'Нова Пошта' and not all([delivery_city, delivery_warehouse]):
            errors.append("Для доставки Новою Поштою необхідно вказати місто та відділення.")

        if not payment_method:
            errors.append("Будь ласка, оберіть спосіб оплати.")

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('checkout.html', cart_items=cart_items_display, total_cost=total_cost)

        user_id_to_assign = current_user.id if current_user.is_authenticated else None
        if not user_id_to_assign:
            user_by_phone = User.query.filter_by(phone=customer_phone).first()
            if user_by_phone:
                user_id_to_assign = user_by_phone.id

        order = Order(
            customer_name=f"{first_name} {last_name}".strip(),
            customer_phone=customer_phone,
            delivery_method=delivery_method,
            delivery_city=delivery_city,
            delivery_warehouse=delivery_warehouse,
            payment_method=payment_method,
            total_cost=total_cost,
            comment=request.form.get('order_comment'),
            user_id=user_id_to_assign
        )
        db.session.add(order)
        db.session.flush()

        order_items_for_email_and_tg = []

        for item_data in cart_items_display:
            product = item_data['product']
            quantity = item_data['quantity']
            db.session.add(OrderItem(order_id=order.id, product_id=product.id, quantity=quantity, price=product.price))
            order_items_for_email_and_tg.append({'product': product, 'quantity': quantity, 'price': product.price})

        if current_user.is_authenticated:
            CartItem.query.filter_by(user_id=current_user.id).delete()
        else:
            session.pop('cart', None)

        db.session.commit()

        try:
            admin_email = os.getenv("SMTP_USER")
            email_pass = os.getenv("EMAIL_PASS")
            if admin_email and email_pass:
                email_sent = send_email(
                    admin_email, f"Нове замовлення #{order.id}",
                    render_template("email/order_notification.html", order=order, items=order_items_for_email_and_tg,
                                    shop=shop_info)
                )
                if not email_sent:
                    app.logger.error(f"Не вдалося надіслати email-сповіщення про замовлення #{order.id}.")
        except Exception as e:
            app.logger.error(f"Email Error Order #{order.id}: {e}")

        try:
            send_telegram_notification(order, order_items_for_email_and_tg)
        except Exception as e:
            app.logger.error(f"Telegram Error Order #{order.id}: {e}")

        flash('Дякуємо! Ваше замовлення прийнято.', 'success')
        return redirect(url_for('index'))

    return render_template('checkout.html', cart_items=cart_items_display, total_cost=total_cost)


# ────────────────────────────────
#  ПРОФІЛЬ КОРИСТУВАЧА
# ────────────────────────────────
@app.route('/profile/orders')
@login_required
def my_orders():
    page = request.args.get('page', 1, type=int)
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.timestamp.desc()).paginate(page=page,
                                                                                                      per_page=10,
                                                                                                      error_out=False)
    return render_template('my_orders.html', orders=orders)


@app.route('/profile/reviews')
@login_required
def my_reviews():
    page = request.args.get('page', 1, type=int)
    reviews = Review.query.filter_by(user_id=current_user.id).order_by(Review.timestamp.desc()).paginate(page=page,
                                                                                                         per_page=10,
                                                                                                         error_out=False)
    return render_template('my_reviews.html', reviews=reviews)


@app.route('/profile/settings', methods=['GET', 'POST'])
@login_required
def profile_settings():
    if request.method == 'POST':
        if 'update_info' in request.form:
            current_user.first_name = request.form.get('first_name')
            current_user.last_name = request.form.get('last_name')
            new_email = request.form.get('email', '').strip().lower()
            email_changed = new_email and new_email != current_user.email

            if email_changed:
                if User.query.filter(User.email == new_email, User.id != current_user.id).first():
                    flash('Цей email вже використовується іншим користувачем.', 'danger')
                    return redirect(url_for('profile_settings'))

                current_user.email = new_email
                current_user.is_email_verified = False
                try:
                    token = current_user.get_email_verify_token()
                    html_body = render_template('email/verify_email.html', user=current_user, token=token,
                                                shop=shop_info)
                    send_email(current_user.email, f"Підтвердження email для {shop_info['name']}", html_body)
                    flash('Дані оновлено. На вашу нову пошту надіслано лист для підтвердження.', 'info')
                except Exception as e:
                    app.logger.error(f"Error sending verification email for {new_email}: {e}")
                    flash('Дані оновлено, але не вдалося надіслати лист. Спробуйте пізніше.', 'warning')
            else:
                flash('Ваші дані успішно оновлено.', 'success')

            db.session.commit()

        elif 'change_password' in request.form:
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            if not current_user.password_hash:
                flash('Неможливо змінити пароль, оскільки ви увійшли через соціальну мережу або телефон.', 'warning')
            elif not current_user.check_password(current_password):
                flash('Невірний поточний пароль.', 'danger')
            elif not new_password or len(new_password) < 6:
                flash('Новий пароль має бути не менше 6 символів.', 'danger')
            elif new_password != confirm_password:
                flash('Паролі не співпадають.', 'danger')
            else:
                current_user.set_password(new_password)
                db.session.commit()
                flash('Пароль успішно змінено.', 'success')

        return redirect(url_for('profile_settings'))

    return render_template('profile_settings.html')


@app.route('/api/hide_phone_prompt', methods=['POST'])
@login_required
def hide_phone_prompt():
    session['hide_phone_prompt'] = True
    return jsonify({'status': 'success'})


# ────────────────────────────────
#  АДМІН-ПАНЕЛЬ
# ────────────────────────────────
@app.route('/admin/orders', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_orders():
    if request.method == 'POST':
        order_id, new_status = request.form.get('order_id'), request.form.get('status')
        if order := Order.query.get(order_id):
            order.status = new_status
            db.session.commit()
            flash(f"Статус замовлення #{order.id} оновлено.", "success")
        return redirect(url_for('admin_orders', status=request.args.get('status', 'Нове')))
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'Нове')
    query = Order.query if status_filter == 'all' else Order.query.filter_by(status=status_filter)
    orders = query.order_by(Order.timestamp.desc()).paginate(page=page, per_page=15, error_out=False)
    all_statuses = ['Нове', 'Відправлено', 'Виконано', 'Скасовано']
    return render_template('admin_orders.html', orders=orders, all_statuses=all_statuses, current_status=status_filter)


@app.route('/admin/reviews')
@login_required
@admin_required
def admin_reviews():
    page = request.args.get('page', 1, type=int)
    reviews = Review.query.order_by(Review.timestamp.desc()).paginate(page=page, per_page=15, error_out=False)
    return render_template('admin_reviews.html', reviews=reviews)

@app.route("/admin/edit_product/<int:product_id>", methods=['GET', 'POST'])
@login_required
@admin_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        product.name = request.form['name']
        product.price = float(request.form['price'])
        product.description = request.form['description']
        product.category = request.form['category']
        product.in_stock = 'in_stock' in request.form

        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                try:
                    upload_result = cloudinary.uploader.upload(
                        file,
                        folder="products/products"
                    )
                    product.image = upload_result['secure_url']
                except Exception as e:
                    print(f"Помилка завантаження Cloudinary: {e}")

        db.session.commit()
        flash(f"Товар '{product.name}' оновлено!", "success")
        return redirect(url_for('catalog'))

    image_filename = ''
    if product.image:
        try:
            image_filename = product.image.split('/')[-1]
        except Exception:
            pass

    return render_template("edit_product.html", product=product, image_to_display=image_filename)


@app.route("/admin/delete_review/<int:review_id>", methods=["POST"])
@login_required
@admin_required
def delete_review(review_id):
    review = Review.query.get_or_404(review_id)
    product = review.product

    db.session.delete(review)
    db.session.flush()

    result = db.session.query(func.avg(Review.rating), func.count(Review.id)).filter(
        Review.product_id == product.id,
        Review.rating > 0,
        Review.review_type == 'review'
    ).one()

    product.rating = float(result[0] or 0)
    product.reviews_count = int(result[1] or 0)

    db.session.commit()

    flash("Запис видалено, рейтинг товару оновлено.", "success")
    return redirect(request.referrer or url_for('admin_reviews'))


@app.route("/admin/delete_product/<int:product_id>", methods=["POST"])
@login_required
@admin_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product);
    db.session.commit()
    flash(f"Товар '{product.name}' видалено.", "success")
    return redirect(url_for('catalog'))


@app.route("/send_message", methods=["POST"])
def send_message():
    form = request.form
    form_data = {'name': form.get('name'), 'email': form.get('email'), 'message': form.get('message')}
    subject = f"Нове повідомлення з сайту від {form_data['name']}"
    html_body = render_template('email/contact_form_notification.html', data=form_data, shop=shop_info)
    if send_email(os.getenv("SMTP_USER"), subject, html_body):
        return jsonify(status="success", message="✅ Повідомлення успішно надіслано!")
    else:
        return jsonify(status="error", message="❌ Помилка сервера при відправці повідомлення."), 500


def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = os.getenv('BAS_API_KEY')
        provided_key = request.headers.get('X-API-KEY') or request.args.get('key')
        if not api_key or provided_key != api_key:
            return "failure\nInvalid API key.", 401
        return f(*args, **kwargs)

    return decorated_function


@app.route('/cabinet/product_import/get_1c_system_info', methods=['GET'])
def handle_bas_handshake():
    print("BAS: пройдено етап handshake.")
    return "success\nphpsessid\n1234567\nzip=no\nfile_limit=20971520"


def _get_cloudinary_url(image_filename):
    DEFAULT_IMAGE_PUBLIC_ID = "products/products/default_tovar"
    public_id = ""
    try:
        if image_filename and image_filename.strip():
            filename_without_extension = os.path.splitext(image_filename)[0]
            public_id = f"products/products/{filename_without_extension}"
        else:
            public_id = DEFAULT_IMAGE_PUBLIC_ID

        url, _ = cloudinary.utils.cloudinary_url(
            public_id,
            secure=True,
            fetch_format="auto",
            quality="auto",
            transformation=[{'dpr': "auto"}]
        )
        return url
    except Exception as e:
        print(f"!!! ПОМИЛКА генерації Cloudinary URL для ID '{public_id}': {e}")
        url, _ = cloudinary.utils.cloudinary_url(DEFAULT_IMAGE_PUBLIC_ID, secure=True)
        return url


@app.route('/api/bas_import', methods=['POST'], strict_slashes=False)
@require_api_key
def bas_import():
    app.logger.info("BAS Import: Start dynamic categorization import.")

    if 'file' not in request.files:
        return "failure\nFile part is missing.", 400

    cml_file = request.files['file']
    if cml_file.filename == '':
        return "failure\nNo selected file.", 400

    try:
        raw_data = cml_file.read()
        try:
            parser = lxml_etree.XMLParser(recover=True, encoding='utf-8')
            root = lxml_etree.fromstring(raw_data, parser=parser)
        except Exception:
            parser = lxml_etree.XMLParser(recover=True, encoding='windows-1251')
            root = lxml_etree.fromstring(raw_data, parser=parser)

        for elem in root.getiterator():
            if '}' in elem.tag:
                elem.tag = elem.tag.split('}', 1)[1]

        classifier_groups = root.findall('.//Классификатор/Группы/Группа')
        if not classifier_groups:
            classifier_groups = root.findall('.//Группы/Группа')

        category_map = {}

        def process_groups(group_nodes, parent_db_id=None):
            for group in group_nodes:
                ext_id = group.findtext('Ид')
                name = group.findtext('Наименование')

                if not ext_id or not name:
                    continue

                cat = Category.query.filter_by(external_id=ext_id).first()
                if not cat:
                    cat = Category.query.filter_by(name=name).first()
                    if cat:
                        cat.external_id = ext_id
                    else:
                        cat = Category(
                            external_id=ext_id,
                            name=name,
                            slug=slugify(name),
                            parent_id=parent_db_id
                        )
                        db.session.add(cat)
                else:
                    cat.name = name
                    cat.parent_id = parent_db_id
                    if not cat.slug:
                        cat.slug = slugify(name)

                db.session.flush()
                category_map[ext_id] = cat.id

                subgroups = group.find('Группы')
                if subgroups is not None:
                    process_groups(subgroups.findall('Группа'), cat.id)

        process_groups(classifier_groups)
        db.session.commit()
        app.logger.info(f"BAS Import: Categories processed. Total categories mapped: {len(category_map)}")

        catalog_node = root.find('.//Каталог')
        products_from_xml = catalog_node.findall('.//Товар') if catalog_node is not None else []

        existing_products_map = {p.name: p for p in db.session.query(Product).all()}

        updated_count = 0
        added_count = 0

        for product_node in products_from_xml:
            product_id_xml = product_node.findtext('Ид')
            name = (product_node.findtext('Наименование') or 'Без назви').strip()

            group_id_node = product_node.find('.//Группы/Ид')
            cat_ext_id = group_id_node.text if group_id_node is not None else None

            db_category_id = category_map.get(cat_ext_id)
            category_obj = Category.query.get(db_category_id) if db_category_id else None
            category_name_str = category_obj.name if category_obj else "Різне"

            description = (product_node.findtext('Описание') or '').strip()

            image_filename_xml = ''
            main_image_node = product_node.find(".//Картинка[@main_image='1']")
            if main_image_node is not None:
                image_filename_xml = main_image_node.text
            else:
                image_filename_xml = product_node.findtext('Картинка') or ''

            price = 0.0
            in_stock = False
            offer_node = root.find(f".//Предложение[Ид='{product_id_xml}']")
            if offer_node is not None:
                price_node = offer_node.find('.//ЦенаЗаЕдиницу')
                if price_node is not None and price_node.text:
                    try:
                        price = float(re.sub(r'[^\d.]', '', price_node.text.replace(',', '.')))
                    except:
                        pass

                qty_node = offer_node.find('Количество')
                if qty_node is not None and qty_node.text:
                    try:
                        if float(qty_node.text.replace(',', '.')) > 0: in_stock = True
                    except:
                        pass

            if not in_stock:
                stock_prop = product_node.find(".//ЗначенияСвойства[Ид='ИД-Наличие']/Значение")
                if stock_prop is not None and stock_prop.text and stock_prop.text.lower() == 'true':
                    in_stock = True

            product = existing_products_map.get(name)
            if product:
                product.price = price
                product.description = description
                product.category_id = db_category_id
                product.category = category_name_str
                product.image = _get_cloudinary_url(image_filename_xml)
                product.in_stock = in_stock
                updated_count += 1
            else:
                new_product = Product(
                    name=name,
                    price=price,
                    description=description,
                    category_id=db_category_id,
                    category=category_name_str,
                    image=_get_cloudinary_url(image_filename_xml),
                    in_stock=in_stock
                )
                db.session.add(new_product)
                added_count += 1

        db.session.commit()
        return f"success\nCategories synced. Updated: {updated_count}, Added: {added_count}"

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"BAS Import Error: {traceback.format_exc()}")
        return f"failure\nServer error: {e}", 500


def require_bot_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = os.getenv('BOT_API_KEY')
        provided_key = request.headers.get('X-Bot-API-Key')
        if not api_key or provided_key != api_key: return jsonify(
            {"status": "error", "message": "Invalid API key"}), 401
        return f(*args, **kwargs)

    return decorated_function


@app.route('/api/order/<int:order_id>/update_status', methods=['POST'])
@require_bot_api_key
def api_update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.json.get('status')
    if new_status in ['Виконано', 'Скасовано', 'Нове', 'Відправлено']:
        order.status = new_status
        db.session.commit()
        return jsonify({"status": "success", "message": f"Order #{order.id} status updated to {new_status}"})
    return jsonify({"status": "error", "message": "Invalid status"}), 400


@app.route('/api/orders')
@require_bot_api_key
def api_get_orders():
    status = request.args.get('status')
    if not status: return jsonify({"status": "error", "message": "Status parameter is required"}), 400
    orders = Order.query.filter_by(status=status).order_by(Order.timestamp.desc()).limit(10).all()
    orders_data = [
        {"id": o.id, "date": o.timestamp.strftime('%Y-%m-%d'), "name": o.customer_name, "total": o.total_cost} for o in
        orders]
    return jsonify({"status": "success", "orders": orders_data})


@app.route('/api/np/cities')
def find_np_cities():
    api_key = os.getenv('NOVA_POSHTA_API_KEY')
    query = request.args.get('q', '')

    if not api_key:
        return jsonify({"error": "API-ключ Нової Пошти не налаштовано на сервері."}), 500
    if len(query) < 2:
        return jsonify([])

    payload = {
        "apiKey": api_key,
        "modelName": "Address",
        "calledMethod": "searchSettlements",
        "methodProperties": {"CityName": query, "Limit": "20"}
    }
    try:
        response = requests.post("https://api.novaposhta.ua/v2.0/json/", json=payload, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data['success'] and data['data'][0]['TotalCount'] > 0:
            cities = data['data'][0]['Addresses']
            return jsonify([{'ref': c['Ref'], 'name': c['Present']} for c in cities])
        return jsonify([])
    except requests.exceptions.RequestException as e:
        print(f"Помилка API Нової Пошти (міста): {e}")
        return jsonify({"error": "Помилка зв'язку з сервером Нової Пошти."}), 503


@app.route('/api/np/warehouses')
def get_np_warehouses():
    api_key = os.getenv('NOVA_POSHTA_API_KEY')
    city_ref = request.args.get('city_ref', '')

    if not api_key:
        return jsonify({"error": "API-ключ Нової Пошти не налаштовано на сервері."}), 500
    if not city_ref:
        return jsonify([])

    payload = {
        "apiKey": api_key,
        "modelName": "AddressGeneral",
        "calledMethod": "getWarehouses",
        "methodProperties": {
            "SettlementRef": city_ref,
            "TypeOfWarehouseRef": "841339c7-591a-42e2-8234-7a0a00f0ed6f,9a6886f2-89b7-41b0-9b0c-e675a080cb28"
        }
    }
    try:
        response = requests.post("https://api.novaposhta.ua/v2.0/json/", json=payload, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data['success']:
            all_warehouses = data.get('data', [])
            return jsonify([w['Description'] for w in all_warehouses])
        return jsonify([])
    except requests.exceptions.RequestException as e:
        print(f"Помилка API Нової Пошти (відділення): {e}")
        return jsonify({"error": "Помилка зв'язку з сервером Нової Пошти."}), 503


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', shop=shop_info), 404


@app.route('/api/popular_searches')
def popular_searches():
    popular_cats = CategoryView.query.order_by(CategoryView.views.desc()).limit(6).all()
    categories_data = [{
        'name': cat.name,
        'slug': cat.name.lower().replace(' ', '-').replace('/', '-')
    } for cat in popular_cats]
    return jsonify(categories_data)


def normalize_text(text):
    """Видаляє пунктуацію та переводить у нижній регістр."""
    if not text:
        return ""
    # Залишаємо тільки літери та цифри
    return re.sub(r'[^\w\s]', '', text).lower()


def get_trigrams(text):
    """Розбиває текст на трійки символів."""
    text = normalize_text(text)
    # Додаємо пробіли, щоб врахувати початок і кінець слова (опціонально, але покращує точність)
    text = f" {text} "
    return set([text[i:i + 3] for i in range(len(text) - 2)])


def calculate_similarity(query, target):
    """
    Обчислює коефіцієнт схожості (Dice coefficient) між двома рядками.
    0.0 - зовсім не схожі, 1.0 - ідентичні.
    """
    query_trigrams = get_trigrams(query)
    target_trigrams = get_trigrams(target)

    if not query_trigrams or not target_trigrams:
        return 0.0

    # Знаходимо спільні тріграми
    intersection = len(query_trigrams.intersection(target_trigrams))

    # Формула Dice: 2 * (спільні) / (кількість у першому + кількість у другому)
    return (2.0 * intersection) / (len(query_trigrams) + len(target_trigrams))


@app.route('/api/search_suggestions')
def search_suggestions():
    query = request.args.get('q', '').strip()

    if len(query) < 2:
        return jsonify({'products': [], 'categories': []})

    # 1. Отримуємо всі товари (але тільки потрібні поля для швидкості)
    # Ми беремо товари, які є в наявності
    all_products = db.session.query(Product.id, Product.name, Product.category, Product.image).filter(
        Product.in_stock == True
    ).all()

    # 2. Шукаємо та оцінюємо схожість
    scored_products = []

    for p in all_products:
        # Рахуємо схожість назви товару із запитом
        score = calculate_similarity(query, p.name)

        # Також можна перевірити категорію, якщо назва не схожа
        if score < 0.3:
            cat_score = calculate_similarity(query, p.category or "")
            if cat_score > score:
                score = cat_score * 0.8  # Трохи зменшуємо вагу, якщо знайшли по категорії

        # Якщо схожість більше 20% (0.2), додаємо у результати
        if score > 0.2:
            scored_products.append({
                'product': p,
                'score': score
            })

    # 3. Сортуємо: найсхожіші зверху
    scored_products.sort(key=lambda x: x['score'], reverse=True)

    # Беремо ТОП-5 результатів
    top_results = scored_products[:5]

    # 4. Формуємо відповідь JSON
    products_data = []
    for item in top_results:
        p = item['product']
        products_data.append({
            'name': p.name,
            'url': url_for('product_detail', product_id=p.id),
            'category': p.category,
            # Можна додати image, якщо ви хочете показувати фото в пошуку (це круто!)
            'image': p.image
        })

    # 5. Пошук категорій (за тим самим принципом)
    all_categories = db.session.query(Category.name).all()
    scored_categories = []

    for cat in all_categories:
        score = calculate_similarity(query, cat.name)
        if score > 0.3:  # Для категорій поріг вищий
            scored_categories.append({'name': cat.name, 'score': score})

    scored_categories.sort(key=lambda x: x['score'], reverse=True)

    categories_data = []
    for cat in scored_categories[:3]:
        slug = slugify(cat['name'])  # Використовуємо вашу функцію slugify
        categories_data.append({
            'name': cat['name'],
            'url': url_for('catalog', category_slug=slug)
        })

    return jsonify({'products': products_data, 'categories': categories_data})

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)