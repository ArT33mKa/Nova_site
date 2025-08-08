import os
import re
import locale
import smtplib
import requests  # для Telegram та Нової Пошти
import cloudinary.utils
from functools import wraps
from datetime import datetime
from dotenv import load_dotenv
from collections import Counter
from sqlalchemy import func, and_, or_ as db_or
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

load_dotenv()
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

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
    if 'sslmode' not in database_url:
        if '?' in database_url:
            database_url += '&sslmode=require'
        else:
            database_url += '?sslmode=require'

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# [ВАЖЛИВО] Повертаємо налаштування для стабільності БД на Heroku
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 280,
    'pool_size': 10,
    'max_overflow': 20
}

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
    phone = db.Column(db.String(20), nullable=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    avatar_url = db.Column(db.String(255), nullable=True)
    reviews = db.relationship('Review', backref='author', lazy='dynamic')
    orders = db.relationship('Order', backref='customer', lazy='dynamic')

    def set_password(self, password): self.password_hash = generate_password_hash(password)

    def check_password(self, password): return check_password_hash(self.password_hash, password)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    image = db.Column(db.String(255), nullable=True)
    category = db.Column(db.String(100))
    brand = db.Column(db.String(100), index=True, nullable=True)
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
             "categories": [{'name': 'Поливочна система', 'image': 'irrigation.jpg', 'icon': 'irrigation.jpg'},
                            {'name': 'Насоси', 'image': 'pumps.jpg', 'icon': 'pumps.jpg'},
                            {'name': 'Бойлер', 'image': 'boilers.jpg', 'icon': 'boilers.jpg'},
                            {'name': 'Змішувач', 'image': 'faucets.jpg', 'icon': 'faucets.jpg'},
                            {'name': "Витяжки", 'image': 'hoods.jpg', 'icon': 'hoods.jpg'},
                            {'name': "Колонки", 'image': 'gas_parts.jpg', 'icon': 'gas_columns.jpg'},
                            {'name': "Сука для рушників", 'image': 'towel_dryers.jpg', 'icon': 'towel_dryers.jpg'},
                            {'name': "Запчастини до газ обладнання", 'image': 'gas_parts.jpg',
                             'icon': 'gas_parts.jpg'}], "address": "вул. Гоголя, 47/2", "city": "м. Миргород",
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


@app.context_processor
def inject_now(): return {'now': datetime.utcnow(), 'shop': shop_info}


@app.route("/")
def index():
    hero_slides = [{'image': 'hero-bg.jpg', 'title': 'Професійна сантехніка та обладнання',
                    'subtitle': 'Якісні товари для вашого дому з гарантією та доставкою'},
                   {'image': 'hero-bg2.jpg', 'title': 'Надійні насоси для будь-яких потреб',
                    'subtitle': 'Від найкращих виробників'}, {'image': 'kotly.jpg', 'title': 'Все для систем опалення',
                                                              'subtitle': 'Котли, бойлери та комплектуючі'}]
    products = Product.query.filter(Product.in_stock == True).order_by(Product.id.desc()).limit(5).all()
    return render_template("index.html", products=products, hero_slides=hero_slides)


def get_category_hierarchy():
    MAIN_CATEGORIES = {
        "Поливочна система": ["полив", "шланг", "конектор", "розпилювач"],
        "Насоси": ["насос", "помпа", "гідрофор"],
        "Бойлери": ["бойлер", "водонагрівач"],
        "Змішувачі": ["змішувач", "кран", "сифон"],
        "Витяжки": ["витяжк", "вентилятор"],
        "Газові колонки": ["колонк", "газов"],
        "Сушка для рушників": ["сушк", "рушник"],
        "Запчастини": ["запчастин", "котел", "термопар"]
    }
    products = db.session.query(Product.category) \
        .filter(Product.category.isnot(None), Product.category != '', Product.in_stock == True).all()
    hierarchy = {}
    for category, in products:
        category = category.strip()
        main_category = None
        if category in MAIN_CATEGORIES:
            main_category = category
        else:
            for main_cat, keywords in MAIN_CATEGORIES.items():
                if any(keyword in category.lower() for keyword in keywords):
                    main_category = main_cat
                    break
        if not main_category:
            main_category = "Запчастини"
        if main_category not in hierarchy:
            hierarchy[main_category] = {'count': 0, 'subcategories': {}}
        hierarchy[main_category]['count'] += 1
        if category != main_category:
            if category not in hierarchy[main_category]['subcategories']:
                hierarchy[main_category]['subcategories'][category] = 0
            hierarchy[main_category]['subcategories'][category] += 1
    return hierarchy


@app.route('/catalog/', defaults={'category_slug': None})
@app.route('/catalog/<string:category_slug>/')
def catalog(category_slug):
    page = request.args.get('page', 1, type=int)
    hierarchy = get_category_hierarchy()

    min_price_str = request.args.get('min_price', '')
    max_price_str = request.args.get('max_price', '')
    search_query = request.args.get('search', '').strip()

    min_price = float(min_price_str) if min_price_str.isdigit() else None
    max_price = float(max_price_str) if max_price_str.isdigit() else None

    if search_query:
        found_product = Product.query.filter(
            Product.name.ilike(f'%{search_query}%'),
            Product.in_stock == True
        ).first()
        if found_product:
            product_main_category = None
            MAIN_CATEGORIES = {
                "Поливочна система": ["полив", "шланг", "конектор", "розпилювач"],
                "Насоси": ["насос", "помпа", "гідрофор"],
                "Бойлери": ["бойлер", "водонагрівач"], "Змішувачі": ["змішувач", "кран", "сифон"],
                "Витяжки": ["витяжк", "вентилятор"], "Газові колонки": ["колонк", "газов"],
                "Сушка для рушників": ["сушк", "рушник"], "Запчастини": ["запчастин", "котел", "термопар"]
            }
            if found_product.category and found_product.category in MAIN_CATEGORIES:
                product_main_category = found_product.category
            elif found_product.category:
                for main_cat, keywords in MAIN_CATEGORIES.items():
                    if any(keyword in found_product.category.lower() for keyword in keywords):
                        product_main_category = main_cat
                        break
            if not product_main_category:
                product_main_category = "Запчастини"

            new_slug = product_main_category.lower().replace(' ', '-')
            if category_slug != new_slug:
                redirect_args = request.args.copy()
                if 'category_slug' in redirect_args: redirect_args.pop('category_slug')
                if 'search' in redirect_args: redirect_args.pop('search')
                return redirect(url_for('catalog', category_slug=new_slug, search=search_query, **redirect_args))

    # [ГОЛОВНЕ ВИПРАВЛЕННЯ] Основний фільтр - тільки товари в наявності.
    query = Product.query.filter(Product.in_stock == True)

    if search_query:
        query = query.filter(Product.name.ilike(f'%{search_query}%'))

    current_category = None
    main_category_of_current = None
    if category_slug:
        category_name = category_slug.replace('-', ' ')
        for m_cat, data in hierarchy.items():
            if m_cat.lower() == category_name.lower():
                current_category = m_cat
                main_category_of_current = m_cat
                subcategories = list(data.get('subcategories', {}).keys())
                query = query.filter(Product.category.in_([current_category] + subcategories))
                break
            if current_category: break
            for sub_cat in data.get('subcategories', {}):
                if sub_cat.lower() == category_name.lower():
                    current_category = sub_cat
                    main_category_of_current = m_cat
                    query = query.filter(Product.category == current_category)
                    break
            if current_category: break

    price_range_query = db.session.query(func.floor(func.min(Product.price)), func.ceil(func.max(Product.price)))
    if query.whereclause is not None:
        price_range_query = price_range_query.select_from(query.subquery())

    price_range = price_range_query.one()
    min_price_available = price_range[0] or 0
    max_price_available = price_range[1] or 10000

    if min_price:
        query = query.filter(Product.price >= min_price)
    if max_price:
        query = query.filter(Product.price <= max_price)

    products = query.order_by(Product.id.desc()).paginate(page=page, per_page=12, error_out=False)

    current_filters = request.args.copy()
    if 'page' in current_filters: current_filters.pop('page')
    if 'category_slug' in current_filters: current_filters.pop('category_slug')

    return render_template(
        'catalog.html',
        products=products,
        hierarchy=hierarchy,
        current_category=current_category,
        main_category_of_current=main_category_of_current,
        current_filters=current_filters,
        category_slug=category_slug,
        min_price_available=min_price_available,
        max_price_available=max_price_available,
        search_query=search_query
    )


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    similar_products = Product.query.filter(Product.category == product.category, Product.id != product.id,
                                            Product.in_stock == True).limit(8).all()
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


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data.get('email')).first()
    if user and user.password_hash and user.check_password(data.get('password')):
        login_user(user, remember=True)
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
    return redirect(url_for("index"))


@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    data = request.get_json()
    product_id = str(data.get("product_id"))
    cart = session.get("cart", {})
    cart[product_id] = cart.get(product_id, 0) + 1
    session["cart"] = cart
    return jsonify(status="success", message="Товар додано до кошика", cart_count=sum(cart.values()))


@app.route('/update_cart_quantity/<int:product_id>', methods=['POST'])
def update_cart_quantity(product_id):
    cart = session.get("cart", {})
    product_id_str = str(product_id)
    new_quantity = request.json.get('quantity')
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
    cart = session.get("cart", {})
    cart_items, total = [], 0
    if cart:
        product_ids = [int(pid) for pid in cart.keys() if pid.isdigit()]
        products = Product.query.filter(Product.id.in_(product_ids)).all()
        product_map = {str(p.id): p for p in products}
        for product_id, quantity in cart.items():
            if product := product_map.get(product_id):
                cart_items.append({
                    "id": product.id, "name": product.name, "price": product.price, "image": product.image,
                    "quantity": quantity, "in_stock": product.in_stock,
                    "url": url_for('product_detail', product_id=product.id)
                })
                total += product.price * quantity
    return jsonify({"items": cart_items, "total": total})


@app.route("/remove_from_cart/<int:product_id>", methods=["POST"])
def remove_from_cart(product_id):
    cart = session.get("cart", {})
    if str(product_id) in cart: del cart[str(product_id)]
    session["cart"] = cart
    return jsonify(status="success")


@app.route('/buy_now', methods=['POST'])
def buy_now():
    session["cart"] = {str(request.get_json().get("product_id")): 1}
    return jsonify(status="success")


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = session.get('cart', {})
    if not cart:
        flash('Ваш кошик порожній.', 'info')
        return redirect(url_for('catalog'))
    if request.method == 'POST':
        product_ids = [int(pid) for pid in cart.keys() if pid.isdigit()]
        products = Product.query.filter(Product.id.in_(product_ids)).all()
        product_map = {str(p.id): p for p in products}
        total_cost = sum(product_map[pid].price * qty for pid, qty in cart.items())
        first_name, last_name = request.form.get('customer_first_name', '').strip(), request.form.get(
            'customer_last_name', '').strip()
        order = Order(
            customer_name=f"{first_name} {last_name}".strip(), customer_phone=request.form.get('customer_phone'),
            delivery_method=request.form.get('delivery_method'), delivery_city=request.form.get('delivery_city'),
            delivery_warehouse=request.form.get('delivery_warehouse'),
            payment_method=request.form.get('payment_method'),
            total_cost=total_cost, comment=request.form.get('order_comment'),
            user_id=current_user.id if current_user.is_authenticated else None)
        db.session.add(order)
        db.session.flush()
        order_items_for_email_and_tg = []
        for pid, qty in cart.items():
            if p := product_map.get(pid):
                db.session.add(OrderItem(order_id=order.id, product_id=p.id, quantity=qty, price=p.price))
                order_items_for_email_and_tg.append({'product': p, 'quantity': qty, 'price': p.price})
        db.session.commit()
        try:
            if admin_email := os.getenv("SMTP_USER"):
                send_email(admin_email, f"Нове замовлення #{order.id}",
                           render_template("email/order_notification.html", order=order,
                                           items=order_items_for_email_and_tg, shop=shop_info))
            send_telegram_notification(order, order_items_for_email_and_tg)
        except Exception as e:
            print(f">>> ПОМИЛКА СПОВІЩЕННЯ: {e}")
        session.pop('cart', None)
        flash('Дякуємо! Ваше замовлення прийнято.', 'success')
        return redirect(url_for('index'))
    return render_template('checkout.html')


@app.route('/profile/orders')
@login_required
def my_orders():
    page = request.args.get('page', 1, type=int)
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.timestamp.desc()).paginate(
        page=page, per_page=10, error_out=False)
    return render_template('my_orders.html', orders=orders)


@app.route('/profile/reviews')
@login_required
def my_reviews():
    page = request.args.get('page', 1, type=int)
    reviews = Review.query.filter_by(user_id=current_user.id).order_by(Review.timestamp.desc()).paginate(
        page=page, per_page=10, error_out=False)
    return render_template('my_reviews.html', reviews=reviews)


@app.route('/profile/settings', methods=['GET', 'POST'])
@login_required
def profile_settings():
    if request.method == 'POST':
        if 'update_info' in request.form:
            current_user.first_name = request.form.get('first_name')
            current_user.last_name = request.form.get('last_name')
            current_user.phone = request.form.get('phone')
            new_email = request.form.get('email')
            if new_email != current_user.email:
                if User.query.filter_by(email=new_email).first():
                    flash('Цей email вже використовується іншим користувачем.', 'danger')
                    return redirect(url_for('profile_settings'))
                current_user.email = new_email
            db.session.commit()
            flash('Ваші дані успішно оновлено.', 'success')
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
        return redirect(url_for('profile_settings'))
    return render_template('profile_settings.html')


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
            name=request.form['name'], price=float(request.form['price']), description=request.form['description'],
            image=request.form['image'].strip() or 'default_tovar.png', category=request.form['category'],
            in_stock='in_stock' in request.form)
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
        product.image = request.form['image'].strip() or 'default_tovar.png'
        product.category = request.form['category']
        product.in_stock = 'in_stock' in request.form
        db.session.commit()
        flash(f"Товар '{product.name}' оновлено!", "success")
        return redirect(url_for('catalog'))
    image_to_display = product.image if product.image and 'default_tovar' not in product.image else ''
    return render_template("edit_product.html", product=product, image_to_display=image_to_display)


@app.route("/admin/delete_review/<int:review_id>", methods=["POST"])
@login_required
@admin_required
def delete_review(review_id):
    review = Review.query.get_or_404(review_id)
    db.session.delete(review)
    db.session.commit()
    flash("Запис видалено.", "success")
    return redirect(request.referrer or url_for('admin_reviews'))


@app.route("/admin/delete_product/<int:product_id>", methods=["POST"])
@login_required
@admin_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
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
            db_or(Product.in_stock == False, (Product.description == None) | (Product.description == ''),
                  Product.image.like('default_tovar%') | (Product.image == None)))
    else:
        if 'no_stock' in active_filters: query = query.filter(Product.in_stock == False)
        if 'no_description' in active_filters: query = query.filter(
            (Product.description == None) | (Product.description == ''))
        if 'no_image' in active_filters: query = query.filter(
            Product.image.like('default_tovar%') | (Product.image == None))
    counts = {
        'no_stock': Product.query.filter(Product.in_stock == False).count(),
        'no_description': Product.query.filter((Product.description == None) | (Product.description == '')).count(),
        'no_image': Product.query.filter(Product.image.like('default_tovar%') | (Product.image == None)).count()
    }
    products = query.order_by(Product.id.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin_unfinished.html', products=products, counts=counts)


@app.route("/send_message", methods=["POST"])
def send_message():
    form = request.form
    form_data = {'name': form.get('name'), 'email': form.get('email'), 'message': form.get('message')}
    subject = f"Нове повідомлення з сайту від {form_data['name']}"
    html_body = render_template('email/contact_form_notification.html', data=form_data, shop=shop_info)
    if send_email(os.getenv("SMTP_USER"), subject, html_body):
        return jsonify(status="success", message="✅ Повідомлення успішно надіслано!")
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
    DEFAULT_IMAGE_PUBLIC_ID = "default_tovar_dw8qbz"
    public_id = ""
    try:
        if image_filename and image_filename.strip():
            filename_without_extension = os.path.splitext(image_filename)[0]
            public_id = f"products/products/{filename_without_extension}"
        else:
            public_id = DEFAULT_IMAGE_PUBLIC_ID
        url, _ = cloudinary.utils.cloudinary_url(public_id, secure=True, fetch_format="auto", quality="auto")
        return url
    except Exception as e:
        print(f"!!! ПОМИЛКА генерації Cloudinary URL для ID '{public_id}': {e}")
        return None


@app.route('/api/bas_import', methods=['POST'], strict_slashes=False)
@require_api_key
def bas_import():
    if 'file' not in request.files:
        return "failure\nFile part is missing in the request.", 400
    cml_file = request.files['file']
    if cml_file.filename == '':
        return "failure\nNo selected file.", 400
    print(f"BAS: Отримано файл '{cml_file.filename}'. Починаю обробку з lxml...")
    try:
        raw_data = cml_file.read()
        try:
            parser_utf8 = lxml_etree.XMLParser(recover=True, encoding='utf-8')
            root = lxml_etree.fromstring(raw_data, parser=parser_utf8)
            print("Info: Файл успішно розібрано з кодуванням UTF-8.")
        except Exception:
            parser_win1251 = lxml_etree.XMLParser(recover=True, encoding='windows-1251')
            root = lxml_etree.fromstring(raw_data, parser=parser_win1251)
            print("Info: Файл успішно розібрано з кодуванням windows-1251.")
        for elem in root.getiterator():
            if '}' in elem.tag: elem.tag = elem.tag.split('}', 1)[1]

        catalog_node = root.find('.//Каталог')
        if catalog_node is None: return "failure\nНе знайдено тег <Каталог>.", 400
        groups = {g.findtext('Ид'): g.findtext('Наименование') for g in root.findall('.//Группа')}
        products_from_xml = catalog_node.findall('.//Товар')
        print(f"В XML знайдено {len(products_from_xml)} товарів. Починаю обробку...")

        existing_products_raw = db.session.query(Product.id, Product.name).all()
        existing_products_map = {name: pid for pid, name in existing_products_raw}
        print(f"Завантажено {len(existing_products_map)} існуючих товарів.")
        products_to_update, products_to_add = [], []
        default_image_url = _get_cloudinary_url(None)

        for product_node in products_from_xml:
            product_id_from_xml = product_node.findtext('Ид')
            if not product_id_from_xml: continue
            name = (product_node.findtext('Наименование') or 'Без назви').strip()
            description = (product_node.findtext('Описание') or '').strip()
            group_id_node = product_node.find('.//Групи/Ид')
            group_id = group_id_node.text if group_id_node is not None else None
            category = groups.get(group_id, "Загальна")

            image_tags = product_node.findall('Картинка')
            image_filename_from_xml = ''
            if image_tags:
                main_image_tag = next((tag for tag in image_tags if tag.get('main_image') == '1'), None)
                if main_image_tag is not None:
                    image_filename_from_xml = (main_image_tag.text or '').strip()
                else:
                    image_filename_from_xml = (image_tags[0].text or '').strip()

            final_image_url = _get_cloudinary_url(image_filename_from_xml) or default_image_url

            price = 0.0
            in_stock = False

            offer_node = root.find(f".//Предложение[Ид='{product_id_from_xml}']")
            if offer_node is not None:
                price_node = offer_node.find('.//ЦенаЗаЕдиницу')
                if price_node is not None and price_node.text:
                    try:
                        price_text = price_node.text.replace(',', '.').replace('\xa0', '')
                        price = float(re.match(r"[\d.]+", price_text).group(0))
                    except (ValueError, AttributeError):
                        pass
                quantity_node = offer_node.find('Количество')
                if quantity_node is not None and quantity_node.text:
                    try:
                        if int(float(quantity_node.text.strip())) > 0: in_stock = True
                    except (ValueError, TypeError):
                        pass

            if not in_stock:
                stock_prop_node = product_node.find(".//ЗначенияСвойства[Ид='ИД-Наличие']/Значение")
                if stock_prop_node is not None and stock_prop_node.text:
                    if stock_prop_node.text.strip().lower() == 'true':
                        in_stock = True

            brand = None
            if description:
                clean_description = description.replace('<br>', '\n').replace('<BR>', '\n')
                brand_keywords = ['виробник:', 'бренд:', 'виробництво:', 'торгова марка:']
                known_brands = ['Ariston', 'Aquapulse', 'Atlantic', 'Gorenje', 'Eldom', 'Forwater', 'Frap',
                                'Immergas', 'Itap', 'KRAZ', 'Lidz', 'Modus', 'Novatec', 'Optima', 'Oasis',
                                'Pedrollo', 'Pentax', 'Purflux', 'Q-tap', 'Rudis', 'Santehplast', 'Sprut',
                                'Aquatica', 'Thermo Alliance', 'Vents', 'Vital', 'Wilo', 'Zanussi', 'Zegor',
                                'Aqua', 'Арма', 'Донтерм', 'Прометей', 'Насоси плюс обладнання', 'Опалення', 'Gerts']
                for keyword in brand_keywords:
                    if keyword in clean_description.lower():
                        start_index = clean_description.lower().find(keyword) + len(keyword)
                        brand_candidate = clean_description[start_index:].strip().split('\n')[0].strip()
                        if brand_candidate: brand = brand_candidate; break
                if not brand:
                    for known_brand in sorted(known_brands, key=len, reverse=True):
                        if re.search(r'\b' + re.escape(known_brand) + r'\b', clean_description, re.IGNORECASE):
                            brand = known_brand;
                            break
            if brand:
                brand = re.sub(r'<[^>]+>', '', brand).replace('&nbsp;', ' ').strip()
                brand = brand[:100] if brand else None

            product_data = {'name': name, 'price': price, 'description': description, 'category': category,
                            'brand': brand, 'image': final_image_url, 'in_stock': in_stock}
            if name in existing_products_map:
                product_data['id'] = existing_products_map[name]
                products_to_update.append(product_data)
            else:
                products_to_add.append(product_data)

        updated_count = len(products_to_update)
        added_count = len(products_to_add)
        print(f"Завершення циклу. Підготовлено до оновлення: {updated_count}, до додавання: {added_count}.")

        if products_to_add:
            print("Виконую пакетне додавання нових товарів...")
            db.session.bulk_insert_mappings(Product, products_to_add)
            print("Пакетне додавання завершено.")
        if products_to_update:
            print("Виконую пакетне оновлення існуючих товарів...")
            db.session.bulk_update_mappings(Product, products_to_update)
            print("Пакетне оновлення завершено.")
        if products_to_add or products_to_update:
            print("Зберігаю зміни в базі даних (commit)...")
            db.session.commit()
            print("Зміни успішно збережено.")
        else:
            print("Немає товарів для додавання або оновлення.")
        message = f"Імпорт CommerceML успішно завершено. Оновлено: {updated_count}, Додано нових: {added_count}."
        print(message)
        return "success"
    except Exception as e:
        db.session.rollback()
        import traceback
        error_details = traceback.format_exc()
        print(f"КРИТИЧНА ПОМИЛКА під час обробки файлу: {e}\n{error_details}")
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


@app.route('/api/np/cities')
def find_np_cities():
    api_key = os.getenv('NOVA_POSHTA_API_KEY')
    query = request.args.get('q', '')
    if not api_key: return jsonify({"error": "API-ключ Нової Пошти не налаштовано на сервері."}), 500
    if len(query) < 2: return jsonify([])
    payload = {"apiKey": api_key, "modelName": "Address", "calledMethod": "searchSettlements",
               "methodProperties": {"CityName": query, "Limit": "20"}}
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
    warehouse_type = request.args.get('type', 'branch')
    if not api_key: return jsonify({"error": "API-ключ Нової Пошти не налаштовано на сервері."}), 500
    if not city_ref: return jsonify([])
    POSTOMAT_REF = "f9316480-5f2d-425d-bc2c-ac73a02de323"
    BRANCH_REFS = {"6f8c7162-4b72-4b0a-88e5-906948c6a92f", "841339c7-591a-42e2-8234-7a0a00f0ed6f",
                   "9a6886f2-89b7-41b0-9b0c-e675a080cb28"}
    payload = {"apiKey": api_key, "modelName": "AddressGeneral", "calledMethod": "getWarehouses",
               "methodProperties": {"SettlementRef": city_ref, "Limit": "500"}}
    try:
        response = requests.post("https://api.novaposhta.ua/v2.0/json/", json=payload, timeout=7)
        response.raise_for_status()
        data = response.json()
        if data['success']:
            all_warehouses = data.get('data', [])
            filtered_warehouses = []
            if warehouse_type == 'postomat':
                for wh in all_warehouses:
                    if wh.get('TypeOfWarehouseRef') == POSTOMAT_REF: filtered_warehouses.append(wh['Description'])
            elif warehouse_type == 'branch':
                for wh in all_warehouses:
                    if wh.get('TypeOfWarehouseRef') in BRANCH_REFS: filtered_warehouses.append(wh['Description'])
            return jsonify(filtered_warehouses)
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
    current_category, main_category, subcategories = None, None, []
    if category_slug:
        category_name = category_slug.replace('-', ' ')
        for main_cat, data in hierarchy.items():
            if main_cat.lower() == category_name.lower():
                current_category, main_category = main_cat, main_cat
                subcategories = list(data.get('subcategories', {}).keys())
                break
            for subcat in data.get('subcategories', {}):
                if subcat.lower() == category_name.lower():
                    current_category, main_category = subcat, main_cat
                    break
            if current_category: break

    query = Product.query.filter(Product.in_stock == True)

    if search_query: query = query.filter(Product.name.ilike(f'%{search_query}%'))
    if current_category:
        if main_category == current_category:
            query = query.filter(Product.category.in_([main_category] + subcategories))
        else:
            query = query.filter(Product.category == current_category)
    if min_price: query = query.filter(Product.price >= min_price)
    if max_price: query = query.filter(Product.price <= max_price)

    products_pagination = query.order_by(Product.id.desc()).paginate(page=page, per_page=12, error_out=False)
    html = render_template('_products_grid_items.html', products=products_pagination.items)
    response = make_response(html)
    response.headers['X-More-Available'] = 'true' if products_pagination.has_next else 'false'
    return response


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(is_admin=True).first():
            print(">>> Створення адміністратора...")
            admin = User(username='admin', first_name='Admin', last_name='User', email='artemcool200911@gmail.com',
                         is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print(">>> Адміністратора створено. Логін: admin, Пароль: admin123")
    app.run(debug=True, port=5000)
