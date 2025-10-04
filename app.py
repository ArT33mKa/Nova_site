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
from twilio.rest import Client
import cloudinary.utils
from functools import wraps
from datetime import datetime
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

if __name__ != '__main__':
    # Якщо додаток запущено через Gunicorn (на Fly.io)
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
    app.logger.info('>>> Логування Flask інтегровано з Gunicorn.')
else:
    # Якщо запущено локально (python app.py)
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
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=True)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    avatar_url = db.Column(db.String(255), nullable=True)
    reviews = db.relationship('Review', backref='author', lazy='dynamic')
    orders = db.relationship('Order', backref='customer', lazy='dynamic')
    cart_items = db.relationship('CartItem', back_populates='user', lazy='dynamic', cascade="all, delete-orphan")

    def set_password(self, password): self.password_hash = generate_password_hash(password)

    def check_password(self, password): return check_password_hash(self.password_hash, password)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    image = db.Column(db.String(255), nullable=True)
    category = db.Column(db.String(100))
    in_stock = db.Column(db.Boolean, default=True)
    rating = db.Column(db.Float, default=0.0)
    reviews_count = db.Column(db.Integer, default=0)
    reviews = db.relationship('Review', backref='product', lazy='dynamic', cascade="all, delete-orphan")


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False, default=0)
    text = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
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
    user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=False)
    user = db.relationship(User)


google_blueprint = make_google_blueprint(scope=["openid", "https://www.googleapis.com/auth/userinfo.email",
                                                "https://www.googleapis.com/auth/userinfo.profile"],
                                         storage=SQLAlchemyStorage(OAuth, db.session, user=current_user))
app.register_blueprint(google_blueprint, url_prefix="/login")

shop_info = {"name": "НОВА ХВИЛЯ",
             "categories": [{'name': 'Поливочна система', 'icon': 'irrigation.jpg'},
                            {'name': 'Насоси та гідрофори', 'icon': 'pumps.jpg'},
                            {'name': 'Водонагрівачі', 'icon': 'boilers.jpg'},
                            {'name': 'Змішувачі та сифони', 'icon': 'faucets.jpg'},
                            {'name': 'Вентиляція та витяжки', 'icon': 'hoods.jpg'},
                            {'name': 'Газове обладнання', 'icon': 'gas_columns.jpg'},
                            {'name': 'Опалення та водопостачання', 'icon': 'towel_dryers.jpg'},
                            {'name': 'Запчастини та комплектуючі', 'icon': 'gas_parts.jpg'}],
             "address": "вул. Гоголя, 47/2", "city": "м. Миргород",
             "phone": ["+38 (050) 670-62-16", "+38 (095) 752-32-58"], "email": "novakhvylia@gmail.com",
             "hours": {"Пн - Пт:": "8:00 - 17:00", "Субота:": "8:00 - 15:00", "Неділя:": "8:00 - 15:00"}}


@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))


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
        return  # Нічого об'єднувати

    # Отримуємо існуючий кошик користувача з БД у вигляді словника {product_id: item}
    db_cart_items = {item.product_id: item for item in user.cart_items}

    for product_id_str, quantity in session_cart.items():
        product_id = int(product_id_str)
        if product_id in db_cart_items:
            # Якщо товар вже є в кошику БД, просто додаємо кількість
            db_cart_items[product_id].quantity += quantity
        else:
            # Якщо товару немає, створюємо новий запис
            new_item = CartItem(user_id=user.id, product_id=product_id, quantity=quantity)
            db.session.add(new_item)

    db.session.commit()
    session.pop('cart', None)  # Очищуємо гостьовий кошик


@app.context_processor
def inject_now(): return {'now': datetime.utcnow(), 'shop': shop_info}


@app.route("/")
def index():
    hero_slides = [{'image': 'hero-bg.jpg', 'title': 'Професійна сантехніка та обладнання',
                    'subtitle': 'Якісні товари для вашого дому з гарантією та доставкою'},
                   {'image': 'hero-bg2.jpg', 'title': 'Надійні насоси для будь-яких потреб',
                    'subtitle': 'Від найкращих виробників'}, {'image': 'kotly.jpg', 'title': 'Все для систем опалення',
                                                              'subtitle': 'Котли, бойлери та комплектуючі'}]
    popular_products_query = db.session.query(
        Product,
        func.sum(OrderItem.quantity).label('total_sold')
    ).join(OrderItem, OrderItem.product_id == Product.id) \
        .group_by(Product.id) \
        .order_by(func.sum(OrderItem.quantity).desc()) \
        .limit(5).all()

    products = [p[0] for p in popular_products_query]  # Витягуємо тільки об'єкти Product

    main_categories_hierarchy = get_category_hierarchy()
    # >>> ДОДАЙТЕ ЦІ РЯДКИ
    main_categories_hierarchy = get_category_hierarchy()
    # Створюємо список з іконками, які у вас були в shop_info
    shop_category_icons = {cat['name'].lower(): cat.get('icon', 'gas_parts.jpg') for cat in shop_info['categories']}

    dynamic_categories = []
    for cat_name in sorted(main_categories_hierarchy.keys()):
        dynamic_categories.append({
            'name': cat_name,
            'icon': shop_category_icons.get(cat_name.lower(), 'gas_parts.jpg')
            # Використовуємо іконку, якщо знайдено, або стандартну
        })

    return render_template("index.html", products=products, hero_slides=hero_slides, main_categories=dynamic_categories)


def get_category_hierarchy():
    MAIN_CATEGORIES = {
        "Поливочна система": ["полив", "зрошення", "шланг", "конектор", "розпилювач", "краплинн", "дощувач", "іригац", "крапельн", "система"],
        "Насоси та гідрофори": ["насос", "помпа", "гідрофор", "дренажн", "фекальн", "циркуляційн", "свердловин"],
        "Водонагрівачі": ["бойлер", "водонагрівач", "тен"],
        "Змішувачі та сифони": ["змішувач", "кран", "сифон", "душов", "лійка"],
        "Вентиляція та витяжки": ["витяжк", "вентилятор", "решітка", "канал"],
        "Газове обладнання": ["колонк", "газов", "конвектор"],
        "Опалення та водопостачання": ["опален", "радіатор", "рушникосуш", "котел", "фітинг", "труба", "крани",
                                       "тепла підлога"],
        "Запчастини та комплектуючі": ["запчастин", "комплектуюч", "термопар", "автоматика", "реле", "мембрана"]
    }
    products = db.session.query(Product.category) \
        .filter(Product.category.isnot(None), Product.category != '', Product.in_stock == True) \
        .all()
    hierarchy = {}
    other_category_name = "Різне"
    for category_tuple in products:
        category_name = category_tuple[0].strip()
        if not category_name:
            continue
        assigned_main_category = None
        for main_cat, keywords in MAIN_CATEGORIES.items():
            if category_name.lower() == main_cat.lower():
                assigned_main_category = main_cat
                break
            if any(keyword in category_name.lower() for keyword in keywords):
                assigned_main_category = main_cat
                break
        if not assigned_main_category:
            assigned_main_category = other_category_name
        if assigned_main_category not in hierarchy:
            hierarchy[assigned_main_category] = {'count': 0, 'subcategories': {}}
        hierarchy[assigned_main_category]['count'] += 1
        if category_name.lower() != assigned_main_category.lower():
            if category_name not in hierarchy[assigned_main_category]['subcategories']:
                hierarchy[assigned_main_category]['subcategories'][category_name] = 0
            hierarchy[assigned_main_category]['subcategories'][category_name] += 1
    return hierarchy


@app.route('/catalog/', defaults={'category_slug': None})
@app.route('/catalog/<path:category_slug>/')
def catalog(category_slug):
    page = request.args.get('page', 1, type=int)
    hierarchy = get_category_hierarchy()
    min_price_str = request.args.get('min_price', '')
    max_price_str = request.args.get('max_price', '')
    search_query = request.args.get('search', '').strip()
    min_price = float(min_price_str) if min_price_str.isdigit() else None
    max_price = float(max_price_str) if max_price_str.isdigit() else None

    # Логіка редіректу тепер коректно обробляє пошук з існуючої категорії
    if search_query:
        found_product = Product.query.filter(
            Product.name.ilike(f'%{search_query}%'),
            Product.in_stock == True,
            Product.description.isnot(None),
            Product.description != ''
        ).first()

        if found_product and found_product.category:
            product_main_category = None
            MAIN_CATEGORIES_FOR_REDIRECT = {
                "Поливочна система": ["полив", "зрошення", "шланг"],
                "Насоси та гідрофори": ["насос", "помпа", "гідрофор"],
                "Водонагрівачі": ["бойлер", "водонагрівач"], "Змішувачі та сифони": ["змішувач", "кран", "сифон"],
                "Вентиляція та витяжки": ["витяжк", "вентилятор"], "Газове обладнання": ["колонк", "газов"],
                "Опалення та водопостачання": ["опален", "радіатор", "котел"],
                "Запчастини та комплектуючі": ["запчастин"]
            }
            for main_cat, keywords in MAIN_CATEGORIES_FOR_REDIRECT.items():
                if any(keyword in found_product.category.lower() for keyword in keywords):
                    product_main_category = main_cat
                    break
            if not product_main_category:
                product_main_category = "Різне"

            new_slug = product_main_category.replace(' ', '-').replace('/', '-')

            if not category_slug or category_slug.replace('-', ' ').replace('/', ' ') != new_slug.replace('-', ' '):
                redirect_args = request.args.copy()
                redirect_args.pop('search', None)
                redirect_args.pop('category_slug', None)
                return redirect(url_for('catalog', category_slug=new_slug, search=search_query, **redirect_args))

    query = Product.query.filter(
        Product.in_stock == True,
        Product.description.isnot(None),
        Product.description != '',
        Product.image.notlike('default_tovar%')
    )
    if search_query:
        query = query.filter(Product.name.ilike(f'%{search_query}%'))

    current_category = None
    main_category_of_current = None
    if category_slug:
        category_name_from_slug = category_slug.replace('-', ' ').replace('/', ' ')
        for main_cat, data in hierarchy.items():
            if main_cat.lower().replace('/', ' ') == category_name_from_slug.lower():
                current_category = main_cat
                main_category_of_current = main_cat
                subcategories = list(data.get('subcategories', {}).keys())
                all_cats_for_filter = [current_category] + subcategories
                # [ВИПРАВЛЕНО] Зроблено фільтрацію нечутливою до регістру
                query = query.filter(Product.category.ilike(current_category))
                break
            for sub_cat in data.get('subcategories', {}):
                if sub_cat.lower().replace('/', ' ') == category_name_from_slug.lower():
                    current_category = sub_cat
                    main_category_of_current = main_cat
                    # [ВИПРАВЛЕНО] Змінено точне порівняння на нечутливе до регістру
                    query = query.filter(Product.category.ilike(current_category))
                    break
            if current_category: break
    if current_category:
        try:
            # Намагаємося знайти запис про категорію
            cat_view = CategoryView.query.filter(func.lower(CategoryView.name) == func.lower(current_category)).first()
            if cat_view:
                cat_view.views += 1
            else:
                # Якщо не знайдено, створюємо новий запис
                cat_view = CategoryView(name=current_category, views=1)
                db.session.add(cat_view)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Помилка підрахунку переглядів категорії '{current_category}': {e}")

    price_range_statement = select(func.min(Product.price), func.max(Product.price)).select_from(query.subquery())
    price_range_result = db.session.execute(price_range_statement).first()

    if price_range_result and price_range_result[0] is not None:
        min_val, max_val = price_range_result
        min_price_available = math.floor(min_val)
        max_price_available = math.ceil(max_val)
    else:
        min_price_available = 0
        max_price_available = 10000
    if min_price:
        query = query.filter(Product.price >= min_price)
    if max_price:
        query = query.filter(Product.price <= max_price)

    # Кількість товарів на сторінці
    products = query.order_by(Product.id.desc()).paginate(page=page, per_page=20, error_out=False)

    current_filters = request.args.copy()
    current_filters.pop('page', None)
    return render_template(
        'catalog.html', products=products, hierarchy=hierarchy, current_category=current_category,
        main_category_of_current=main_category_of_current, current_filters=current_filters,
        category_slug=category_slug, min_price_available=min_price_available,
        max_price_available=max_price_available, search_query=search_query
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
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data.get('email')).first()
    if user and user.password_hash and user.check_password(data.get('password')):
        login_user(user, remember=True)
        merge_session_cart_to_db(user)
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Невірний email або пароль"}), 401


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    email, first_name, last_name, phone = data.get('email'), data.get('first_name'), data.get('last_name'), data.get(
        'phone')
    if not email or not first_name or not data.get('password'): return jsonify(
        {"status": "error", "message": "Ім'я, Email та Пароль є обов'язковими"}), 400
    if User.query.filter_by(email=email).first(): return jsonify(
        {"status": "error", "message": "Цей email вже зареєстровано"}), 400
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
    return jsonify({"status": "success"})


@app.route("/logout")
@login_required
def logout():
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
        msg = resp.json().get("error", {}).get("message", "Невідома помилка.")
        flash(f"Не вдалося отримати інформацію про користувача з Google: {msg}", category="error")
        return redirect(url_for("index"))
    google_info = resp.json()
    email = google_info["email"]
    user = User.query.filter_by(email=email).first()
    if not user:
        first_name = google_info.get("given_name", "User")
        last_name = google_info.get("family_name")
        username_base = first_name.lower().strip()
        username, counter = username_base, 1
        while User.query.filter_by(username=username).first():
            username = f"{username_base}{counter}"
            counter += 1
        user = User(email=email, username=username, first_name=first_name, last_name=last_name,
                    avatar_url=google_info.get('picture'))
        db.session.add(user)
        db.session.commit()
        subject = f"Вітаємо у {shop_info['name']}!"
        html_body = render_template("email/welcome.html", user=user, shop=shop_info)
        send_email(user.email, subject, html_body)
        flash("Ви успішно зареєструвалися та увійшли через Google!", category="success")
    else:
        if not user.avatar_url and google_info.get('picture'):
            user.avatar_url = google_info.get('picture')
            db.session.commit()
        flash("Ви успішно увійшли через Google!", category="success")
    login_user(user, remember=True)
    merge_session_cart_to_db(user)
    return redirect(url_for("index"))


# ────────────────────────────────
#  КОШИК ТА ОФОРМЛЕННЯ ЗАМОВЛЕННЯ
# ────────────────────────────────
@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    product_id = int(request.get_json().get("product_id"))

    if current_user.is_authenticated:
        # Логіка для залогінених користувачів (база даних)
        cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
        if cart_item:
            cart_item.quantity += 1
        else:
            cart_item = CartItem(user_id=current_user.id, product_id=product_id, quantity=1)
            db.session.add(cart_item)
        db.session.commit()
        cart_count = sum(item.quantity for item in current_user.cart_items)
    else:
        # Логіка для гостей (сесія)
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
def get_cart():
    cart_items, total = [], 0

    if current_user.is_authenticated:
        # Для залогінених: беремо з бази даних
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
        # Для гостей: беремо з сесії
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
        # Повністю очищуємо кошик користувача і додаємо один товар
        CartItem.query.filter_by(user_id=current_user.id).delete()
        new_item = CartItem(user_id=current_user.id, product_id=product_id, quantity=1)
        db.session.add(new_item)
        db.session.commit()
    else:
        # Для гостя просто замінюємо кошик в сесії
        session["cart"] = {str(product_id): 1}

    return jsonify(status="success")


@app.route('/api/auth/start_email_login', methods=['POST'])
def start_email_login():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    if not email:
        return jsonify({'status': 'error', 'message': 'Email є обов\'язковим'}), 400

    code = str(random.randint(100000, 999999))
    session['verification_email'] = email
    session['verification_code'] = code
    session.permanent = True  # Код буде жити 10 хвилин
    app.permanent_session_lifetime = 600  # 10 хвилин

    html_body = render_template("email/verification_code.html", code=code, shop=shop_info)
    if send_email(email, f"Код підтвердження для {shop_info['name']}", html_body):
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': 'Не вдалося надіслати лист. Спробуйте пізніше.'}), 500


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
        # [ЗМІНЕНО] Створюємо користувача без імені
        username_base = email.split('@')[0]
        username, counter = username_base, 1
        while User.query.filter_by(username=username).first():
            username = f"{username_base}_{counter}"
            counter += 1

        user = User(
            email=email,
            username=username,
            first_name=""  # Залишаємо ім'я порожнім
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
    """Перевіряє, чи існує користувач за номером телефону."""
    phone = request.json.get('phone')
    if not phone:
        return jsonify({'exists': False, 'error': 'Phone number is required'}), 400
    user = User.query.filter_by(phone=phone).first()
    return jsonify({'exists': user is not None})


@app.route('/api/auth/firebase_verify', methods=['POST'])
def firebase_verify():
    """
    Перевіряє токен від Firebase, знаходить або створює користувача
    і авторизує його в системі Flask-Login.
    """
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
                # Ця ситуація не повинна виникати, оскільки фронтенд вже перевірив існування
                return jsonify(
                    {'status': 'error', 'message': 'Помилка: Користувача не знайдено, хоча він мав існувати'}), 404

        elif intent == 'register':
            if user:
                # Ця ситуація також не повинна виникати
                return jsonify({'status': 'error', 'message': 'Цей номер вже зареєстровано'}), 409

            first_name = request.json.get('first_name')
            last_name = request.json.get('last_name')
            if not all([first_name, last_name]):
                return jsonify({'status': 'error', 'message': 'Ім\'я та прізвище є обов\'язковими'}), 400

            # Генеруємо унікальний email та username
            base_email = f"{phone.replace('+', '')}@temp.user"
            email, counter = base_email, 1
            while User.query.filter_by(email=email).first():
                email = f"{phone.replace('+', '')}_{counter}@temp.user"
                counter += 1

            username_base = first_name.strip()
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
            db.session.add(new_user)
            db.session.commit()
            user = new_user  # Перепризначаємо user на щойно створеного

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

        # Перевірка, чи цей номер не зайнятий іншим користувачем
        existing_user = User.query.filter(User.phone == phone_from_token, User.id != current_user.id).first()
        if existing_user:
            return jsonify({'status': 'error', 'message': 'Цей номер телефону вже прив\'язаний до іншого акаунту'}), 409

        # Все добре, оновлюємо номер
        current_user.phone = phone_from_token
        db.session.commit()
        session.pop('hide_phone_prompt', None) # Скидаємо банер, бо телефон додано

        return jsonify({'status': 'success', 'message': 'Номер телефону успішно підтверджено та оновлено!'})

    except auth.InvalidIdTokenError:
        return jsonify({'status': 'error', 'message': 'Недійсний токен авторизації'}), 401
    except Exception as e:
        app.logger.error(f"Phone update error for user {current_user.id}: {e}")
        return jsonify({'status': 'error', 'message': 'Сталася помилка на сервері'}), 500

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    # [ОНОВЛЕНО] Перевірка кошика тепер працює для обох типів користувачів
    if current_user.is_authenticated:
        # Для залогіненого користувача перевіряємо кошик в БД
        is_cart_empty = not db.session.query(CartItem.query.filter_by(user_id=current_user.id).exists()).scalar()
    else:
        # Для гостя перевіряємо сесію
        is_cart_empty = not session.get('cart')

    if is_cart_empty:
        flash('Ваш кошик порожній.', 'info')
        return redirect(url_for('catalog'))

    if request.method == 'POST':
        # --- БЛОК ВАЛІДАЦІЇ (без змін) ---
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
            return render_template('checkout.html')

        # --- [ПОВНІСТЮ ПЕРЕРОБЛЕНО] Логіка отримання даних з кошика ---
        cart_items_to_process = []
        total_cost = 0

        if current_user.is_authenticated:
            # Для залогінених: беремо дані з бази даних
            user_cart_items = current_user.cart_items.all()
            for item in user_cart_items:
                cart_items_to_process.append({'product': item.product, 'quantity': item.quantity})
                total_cost += item.product.price * item.quantity
        else:
            # Для гостей: беремо дані з сесії
            cart_session = session.get('cart', {})
            product_ids = [int(pid) for pid in cart_session.keys()]
            products = Product.query.filter(Product.id.in_(product_ids)).all()
            product_map = {p.id: p for p in products}

            for pid, qty in cart_session.items():
                product = product_map.get(int(pid))
                if product:
                    cart_items_to_process.append({'product': product, 'quantity': qty})
                    total_cost += product.price * qty

        # --- Логіка створення замовлення (з невеликими змінами) ---
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
        for item_data in cart_items_to_process:
            product = item_data['product']
            quantity = item_data['quantity']
            db.session.add(OrderItem(order_id=order.id, product_id=product.id, quantity=quantity, price=product.price))
            order_items_for_email_and_tg.append({'product': product, 'quantity': quantity, 'price': product.price})

        # [ОНОВЛЕНО] Очищення кошика для обох типів користувачів
        if current_user.is_authenticated:
            CartItem.query.filter_by(user_id=current_user.id).delete()
        else:
            session.pop('cart', None)

        db.session.commit()

        # --- Блок відправки сповіщень (без змін, використовуємо версію з минулого виправлення) ---
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
                else:
                    app.logger.info(f"Email-сповіщення про замовлення #{order.id} успішно надіслано.")
            else:
                app.logger.warning("Email-сповіщення не надіслано: SMTP_USER або EMAIL_PASS не налаштовано.")
        except Exception as e:
            app.logger.error(
                f"Критична помилка при спробі відправки email про замовлення #{order.id}: {e}\n{traceback.format_exc()}")

        try:
            send_telegram_notification(order, order_items_for_email_and_tg)
        except Exception as e:
            app.logger.error(
                f"Критична помилка при спробі відправки Telegram-сповіщення про замовлення #{order.id}: {e}\n{traceback.format_exc()}")

        flash('Дякуємо! Ваше замовлення прийнято.', 'success')
        return redirect(url_for('index'))

    # GET-запит: просто показуємо сторінку
    return render_template('checkout.html')


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


# app.py

@app.route('/profile/settings', methods=['GET', 'POST'])
@login_required
def profile_settings():
    if request.method == 'POST':
        # --- БЛОК ОНОВЛЕННЯ ІНФОРМАЦІЇ ---
        if 'update_info' in request.form:
            current_user.first_name = request.form.get('first_name')
            current_user.last_name = request.form.get('last_name')

            # [ОНОВЛЕНО] Додано перевірку унікальності номера телефону
            new_phone = request.form.get('phone')
            if new_phone and new_phone != current_user.phone:
                # Перевіряємо, чи інший користувач вже використовує цей номер
                existing_user = User.query.filter(User.phone == new_phone, User.id != current_user.id).first()
                if existing_user:
                    flash('Цей номер телефону вже використовується іншим користувачем.', 'danger')
                    return redirect(url_for('profile_settings'))
            current_user.phone = new_phone

            new_email = request.form.get('email')
            if new_email != current_user.email:
                if User.query.filter_by(email=new_email).first():
                    flash('Цей email вже використовується іншим користувачем.', 'danger')
                    return redirect(url_for('profile_settings'))
                current_user.email = new_email

            db.session.commit()
            flash('Ваші дані успішно оновлено.', 'success')

        # --- БЛОК ЗМІНИ ПАРОЛЮ (без змін) ---
        elif 'change_password' in request.form:
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            if not current_user.password_hash:
                flash('Неможливо змінити пароль, оскільки ви увійшли через соціальну мережу.', 'warning')
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

        # [НОВЕ] Очищуємо сесійну змінну, якщо користувач оновив телефон
        session.pop('hide_phone_prompt', None)
        return redirect(url_for('profile_settings'))

    return render_template('profile_settings.html')


# [НОВЕ] Додайте цей маршрут в кінець файлу, перед запуском додатку
@app.route('/api/hide_phone_prompt', methods=['POST'])
@login_required
def hide_phone_prompt():
    """Зберігає в сесії, що користувач закрив банер."""
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


@app.route("/admin/add_product", methods=['GET', 'POST'])
@login_required
@admin_required
def add_product():
    if request.method == 'POST':
        new_product = Product(
            name=request.form['name'],
            price=float(request.form['price']),
            description=request.form['description'],
            image=_get_cloudinary_url(request.form['image'].strip()),
            category=request.form['category'],
            in_stock='in_stock' in request.form
        )
        db.session.add(new_product)
        db.session.commit()
        flash(f"Товар '{new_product.name}' додано!", "success")
        return redirect(url_for('catalog'))
    return render_template("add_product.html")


@app.route("/admin/edit_product/<int:product_id>", methods=['GET', 'POST'])
@login_required
@admin_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        product.name = request.form['name']
        product.price = float(request.form['price'])
        product.description = request.form['description']
        product.image = _get_cloudinary_url(request.form['image'].strip())
        product.category = request.form['category']
        product.in_stock = 'in_stock' in request.form

        db.session.commit()
        flash(f"Товар '{product.name}' оновлено!", "success")
        return redirect(url_for('catalog'))

    image_filename = ''
    if product.image:
        try:
            match = re.search(r'/products/products/([^/.]+)', product.image)
            if match:
                image_filename = match.group(1) + '.jpg'
        except Exception:
            pass

    return render_template("edit_product.html", product=product, image_to_display=image_filename)


@app.route("/admin/delete_review/<int:review_id>", methods=["POST"])
@login_required
@admin_required
def delete_review(review_id):
    review = Review.query.get_or_404(review_id)
    product = review.product  # Отримуємо зв'язаний товар

    # Видаляємо відгук
    db.session.delete(review)

    # Важливо! Перераховуємо рейтинг та кількість ТІЛЬКИ для відгуків (не питань)
    # Робимо це перед фінальним комітом, щоб запит врахував видалення
    db.session.flush()  # Застосовуємо видалення в сесії, але ще не зберігаємо в базу

    # Запит для перерахунку середнього рейтингу та кількості
    result = db.session.query(func.avg(Review.rating), func.count(Review.id)).filter(
        Review.product_id == product.id,
        Review.rating > 0,
        Review.review_type == 'review'  # Враховуємо тільки записи типу "review"
    ).one()

    product.rating = float(result[0] or 0)
    product.reviews_count = int(result[1] or 0)

    db.session.commit()  # Зберігаємо і видалення, і оновлення товару

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


@app.route('/admin/unfinished')
@login_required
@admin_required
def admin_unfinished():
    page = request.args.get('page', 1, type=int)
    query = Product.query
    active_filters = [k for k in request.args if k in ['no_stock', 'no_description', 'no_image']]
    if not active_filters:
        query = query.filter(
            db_or(Product.in_stock == False,
                  (Product.description == None) | (Product.description == ''),
                  Product.image.like('default_tovar%') | (Product.image == None)))
    else:
        if 'no_stock' in active_filters: query = query.filter(Product.in_stock == False)
        if 'no_description' in active_filters: query = query.filter(
            (Product.description == None) | (Product.description == ''))
        if 'no_image' in active_filters: query = query.filter(
            Product.image.like('default_tovar%') | (Product.image == None))

    counts = {'no_stock': Product.query.filter(Product.in_stock == False).count(),
              'no_description': Product.query.filter(
                  (Product.description == None) | (Product.description == '')).count(),
              'no_image': Product.query.filter(Product.image.like('default_tovar%') | (Product.image == None)).count()}

    products = query.order_by(Product.id.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin_unfinished.html', products=products, counts=counts)


# ────────────────────────────────
#  ІНШІ МАРШРУТИ ТА API
# ────────────────────────────────
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


# ────────────────────────────────
#  API ДЛЯ ІНТЕГРАЦІЇ З BAS (1C) - НАДІЙНА ВЕРСІЯ
# ────────────────────────────────



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
    """
    [ОНОВЛЕНО] Внутрішня функція для генерації повного URL зображення з Cloudinary.
    """
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
        # Повертаємо URL для заглушки за замовчуванням у разі помилки
        url, _ = cloudinary.utils.cloudinary_url(DEFAULT_IMAGE_PUBLIC_ID, secure=True)
        return url


@app.route('/api/bas_import', methods=['POST'], strict_slashes=False)
@require_api_key
def bas_import():
    """ [ОНОВЛЕНА ВЕРСІЯ З ДЕТАЛЬНИМ ЛОГУВАННЯМ] """
    app.logger.info("BAS Import: Отримано запит на імпорт.")

    if 'file' not in request.files:
        app.logger.warning("BAS Import: Запит без файлу. Відхилено.")
        return "failure\nFile part is missing in the request.", 400

    cml_file = request.files['file']
    if cml_file.filename == '':
        app.logger.warning("BAS Import: Надіслано порожній файл. Відхилено.")
        return "failure\nNo selected file.", 400

    app.logger.info(f"BAS Import: Отримано файл '{cml_file.filename}'. Починаю обробку...")

    try:
        raw_data = cml_file.read()
        try:
            # Спершу пробуємо стандартне кодування UTF-8
            parser = lxml_etree.XMLParser(recover=True, encoding='utf-8')
            root = lxml_etree.fromstring(raw_data, parser=parser)
            app.logger.info("BAS Import: Файл успішно розпарсено в кодуванні UTF-8.")
        except Exception:
            # Якщо не вийшло, пробуємо Windows-1251, що часто використовується в 1С/BAS
            app.logger.warning("BAS Import: Не вдалося розпарсити як UTF-8. Пробую Windows-1251...")
            parser = lxml_etree.XMLParser(recover=True, encoding='windows-1251')
            root = lxml_etree.fromstring(raw_data, parser=parser)
            app.logger.info("BAS Import: Файл успішно розпарсено в кодуванні Windows-1251.")

        # Видалення неймспейсів для спрощення пошуку
        for elem in root.getiterator():
            if '}' in elem.tag:
                elem.tag = elem.tag.split('}', 1)[1]

        catalog_node = root.find('.//Каталог')
        if catalog_node is None:
            app.logger.error("BAS Import: Не знайдено тег <Каталог> у файлі.")
            return "failure\nНе знайдено тег <Каталог>.", 400

        groups = {g.findtext('Ид'): g.findtext('Наименование') for g in root.findall('.//Группа')}
        products_from_xml = catalog_node.findall('.//Товар')
        app.logger.info(f"BAS Import: В XML знайдено {len(products_from_xml)} товарів. Починаю оптимізовану обробку...")

        app.logger.info("BAS Import: Завантажую існуючі товари з бази даних...")
        existing_products_map = {p.name: p.id for p in db.session.query(Product.id, Product.name).all()}
        app.logger.info(f"BAS Import: Успішно завантажено {len(existing_products_map)} існуючих товарів з бази даних.")

        products_to_update = []
        products_to_add = []

        for product_node in products_from_xml:
            product_id_from_xml = product_node.findtext('Ид')
            if not product_id_from_xml: continue

            name = (product_node.findtext('Наименование') or 'Без назви').strip()
            description = (product_node.findtext('Описание') or '').strip()

            group_id_node = product_node.find('.//Группы/Ид')
            group_id = group_id_node.text if group_id_node is not None else None
            category = groups.get(group_id, "Різне")

            main_image_node = product_node.find(".//Картинка[@main_image='1']")
            if main_image_node is not None:
                image_filename_from_xml = main_image_node.text
            else:
                image_filename_from_xml = product_node.findtext('Картинка') or ''
            image_filename_from_xml = image_filename_from_xml.strip()

            price = 0.0
            in_stock = False

            offer_node = root.find(f".//Предложение[Ид='{product_id_from_xml}']")
            if offer_node is not None:
                price_node = offer_node.find('.//ЦенаЗаЕдиницу')
                if price_node is not None and price_node.text:
                    try:
                        price = float(re.sub(r'[^\d.]', '', price_node.text.replace(',', '.')))
                    except (ValueError, AttributeError): pass

                quantity_node = offer_node.find('Количество')
                if quantity_node is not None and quantity_node.text:
                    try:
                        if int(float(quantity_node.text.strip())) > 0: in_stock = True
                    except (ValueError, TypeError): pass

            # Додаткова перевірка наявності через властивості товару
            if not in_stock:
                stock_prop_node = product_node.find(".//ЗначенияСвойства[Ид='ИД-Наличие']/Значение")
                if stock_prop_node is not None and stock_prop_node.text and stock_prop_node.text.lower() == 'true':
                    in_stock = True
                else:
                    stock_prop_node_alt = product_node.find(".//ЗначенняРеквизита[Наименование='Наличие']/Значение")
                    if stock_prop_node_alt is not None and stock_prop_node_alt.text and stock_prop_node_alt.text.strip().lower() in ['true', 'да', 'є', 'yes']:
                         in_stock = True

            product_data = {
                'name': name,
                'price': price,
                'description': description,
                'category': category,
                'image': _get_cloudinary_url(image_filename_from_xml),
                'in_stock': in_stock
            }

            if name in existing_products_map:
                product_data['id'] = existing_products_map[name]
                products_to_update.append(product_data)
            else:
                products_to_add.append(product_data)

        updated_count = len(products_to_update)
        added_count = len(products_to_add)
        app.logger.info(f"BAS Import: Підготовлено до оновлення: {updated_count}. Підготовлено до додавання: {added_count}.")

        if products_to_add:
            app.logger.info(f"BAS Import: Виконую пакетне додавання {len(products_to_add)} нових товарів...")
            db.session.bulk_insert_mappings(Product, products_to_add)
            app.logger.info("BAS Import: Пакетне додавання завершено.")

        if products_to_update:
            app.logger.info(f"BAS Import: Виконую пакетне оновлення {len(products_to_update)} існуючих товарів...")
            db.session.bulk_update_mappings(Product, products_to_update)
            app.logger.info("BAS Import: Пакетне оновлення завершено.")

        if products_to_add or products_to_update:
            app.logger.info("BAS Import: Зберігаю зміни в базі даних (commit)...")
            db.session.commit()
            app.logger.info("BAS Import: Зміни успішно збережено.")
        else:
            app.logger.info("BAS Import: Немає товарів для додавання або оновлення.")

        message = f"Імпорт CommerceML успішно завершено. Оновлено: {updated_count}, Додано нових: {added_count}."
        app.logger.info(f"BAS Import: {message}")
        return "success"

    except Exception as e:
        db.session.rollback()
        # Ось тут логуємо критичну помилку з повним шляхом, що дуже допоможе в зневадженні
        error_details = traceback.format_exc()
        app.logger.error(f"BAS Import: КРИТИЧНА ПОМИЛКА під час обробки файлу: {e}\n{error_details}")
        return f"failure\nВнутрішня помилка сервера: {e}", 500


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


# API ДЛЯ ІНТЕГРАЦІЇ З "НОВОЮ ПОШТОЮ"
@app.route('/api/np/cities')
def find_np_cities():
    """Пошук населених пунктів."""
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
    """Отримання ВІДДІЛЕНЬ ТА ПОШТОМАТІВ для населеного пункту."""
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


@app.route('/api/catalog/load_more')
def api_load_more():
    page = request.args.get('page', 1, type=int)
    category_slug = request.args.get('category_slug')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    search_query = request.args.get('search', '').strip()

    hierarchy = get_category_hierarchy()
    query = Product.query.filter(
        Product.in_stock == True,
        Product.description.isnot(None),
        Product.description != '',
        Product.image.notlike('default_tovar%')
    )

    if search_query:
        query = query.filter(Product.name.ilike(f'%{search_query}%'))

    if category_slug:
        category_name_from_slug = category_slug.replace('-', ' ').replace('/', ' ')
        current_category = None
        for main_cat, data in hierarchy.items():
            if main_cat.lower().replace('/', ' ') == category_name_from_slug.lower():
                current_category = main_cat
                subcategories = list(data.get('subcategories', {}).keys())
                all_cats_for_filter = [current_category] + subcategories
                query = query.filter(Product.category.in_(all_cats_for_filter))
                break

            for sub_cat in data.get('subcategories', {}):
                if sub_cat.lower().replace('/', ' ') == category_name_from_slug.lower():
                    current_category = sub_cat
                    query = query.filter(Product.category == current_category)
                    break
            if current_category:
                break

    if min_price:
        query = query.filter(Product.price >= min_price)
    if max_price:
        query = query.filter(Product.price <= max_price)

    products_pagination = query.order_by(Product.id.desc()).paginate(
        page=page, per_page=12, error_out=False
    )

    html = render_template('_products_grid_items.html', products=products_pagination.items)
    response = make_response(html)
    response.headers['X-More-Available'] = 'true' if products_pagination.has_next else 'false'
    return response

@app.route('/api/popular_searches')
def popular_searches():
    # Отримуємо 6 найпопулярніших категорій за кількістю переглядів
    popular_cats = CategoryView.query.order_by(CategoryView.views.desc()).limit(6).all()
    # Формуємо slug (URL-частину) для кожної
    categories_data = [{
        'name': cat.name,
        'slug': cat.name.lower().replace(' ', '-').replace('/', '-')
    } for cat in popular_cats]
    return jsonify(categories_data)

# ────────────────────────────────
#  API ДЛЯ ПОШУКОВИХ ПІДКАЗОК
# ────────────────────────────────
@app.route('/api/search_suggestions')
def search_suggestions():
    query = request.args.get('q', '').strip()

    if len(query) < 2:
        return jsonify({'products': [], 'categories': []})

    # Пошук товарів (до 5 штук)
    products_result = Product.query.filter(
        Product.name.ilike(f'%{query}%'),
        Product.in_stock == True,
        Product.description.isnot(None),
        Product.description != ''
    ).limit(5).all()

    # Пошук унікальних категорій (до 3 штук)
    categories_result = db.session.query(Product.category).filter(
        Product.category.ilike(f'%{query}%')
    ).distinct().limit(3).all()

    # Форматуємо результати для JSON
    products = [
        {'name': p.name, 'url': url_for('product_detail', product_id=p.id), 'category': p.category}
        for p in products_result
    ]
    categories = []
    for cat_tuple in categories_result:
        cat_name = cat_tuple[0]
        # Створюємо URL-безпечну версію назви категорії (slug)
        cat_slug = cat_name.lower().replace(' ', '-').replace('/', '-')
        categories.append({
            'name': cat_name,
            'url': url_for('catalog', category_slug=cat_slug)
        })

    return jsonify({'products': products, 'categories': categories})

# ────────────────────────────────
#  ЗАПУСК ДОДАТКУ
# ────────────────────────────────
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(is_admin=True).first():
            print(">>> Створення адміністратора...")
            admin = User(username='admin', first_name='Admin', last_name='User', email='artemcool200911@gmail.com',
                         is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin);
            db.session.commit()
            print(">>> Адміністратора створено. Логін: admin, Пароль: admin123")
    app.run(debug=True, port=5000)