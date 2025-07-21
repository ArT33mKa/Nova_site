import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import func
from collections import Counter
import locale  # [НОВЕ] Імпорт для локалізації дати
import re
from flask import request, jsonify
import xml.etree.ElementTree as ET
from werkzeug.exceptions import Unauthorized

from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.consumer import oauth_authorized
from flask_dance.consumer.storage.sqla import SQLAlchemyStorage

# [ОНОВЛЕНО] Встановлюємо українську локаль для дат.
# Якщо на вашому сервері (включаючи Render, Heroku і т.д.) не встановлена ця локаль,
# дати будуть відображатися англійською. Це проблема середовища, а не коду.
try:
    locale.setlocale(locale.LC_TIME, 'uk_UA.UTF-8')
except locale.Error:
    print("ПОПЕРЕДЖЕННЯ: Локал 'uk_UA.UTF-8' не знайдено. Дати можуть відображатися англійською.")

load_dotenv()
app = Flask(__name__)
app.jinja_env.add_extension('jinja2.ext.do')
app.secret_key = os.getenv("FLASK_SECRET", "nova-secret")

database_url = os.getenv('DATABASE_URL', 'sqlite:///site.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Будь ласка, увійдіть, щоб виконати цю дію."
login_manager.login_message_category = "info"


# ────────────────────────────────
#  УТИЛІТА ДЛЯ EMAIL
# ────────────────────────────────
def send_email(to_address, subject, html_body):
    """Універсальна функція для надсилання листів."""
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


# ────────────────────────────────
#  МОДЕЛІ БАЗИ ДАНИХ
# ────────────────────────────────
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)
    avatar_url = db.Column(db.String(255), nullable=True)
    reviews = db.relationship('Review', backref='author', lazy='dynamic')

    def set_password(self, password): self.password_hash = generate_password_hash(password)

    def check_password(self, password): return check_password_hash(self.password_hash, password)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    image = db.Column(db.String(100))
    category = db.Column(db.String(100))
    brand = db.Column(db.String(50))
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

    replies = db.relationship(
        'Review',
        backref=db.backref('parent', remote_side=[id]),
        lazy='dynamic',
        cascade="all, delete-orphan",
        order_by='Review.timestamp.asc()'
    )


class Order(db.Model): id = db.Column(db.Integer, primary_key=True); user_id = db.Column(db.Integer,
                                                                                         db.ForeignKey('user.id'),
                                                                                         nullable=True); customer_name = db.Column(
    db.String(100), nullable=False); customer_phone = db.Column(db.String(20),
                                                                nullable=False); delivery_method = db.Column(
    db.String(50)); payment_method = db.Column(db.String(50)); total_cost = db.Column(db.Float,
                                                                                      nullable=False); timestamp = db.Column(
    db.DateTime, index=True, default=datetime.utcnow); items = db.relationship('OrderItem', backref='order',
                                                                               lazy='dynamic',
                                                                               cascade="all, delete-orphan")


class OrderItem(db.Model): id = db.Column(db.Integer, primary_key=True); order_id = db.Column(db.Integer,
                                                                                              db.ForeignKey('order.id'),
                                                                                              nullable=False); product_id = db.Column(
    db.Integer, db.ForeignKey('product.id'), nullable=False); quantity = db.Column(db.Integer,
                                                                                   nullable=False); price = db.Column(
    db.Float, nullable=False)


class OAuth(db.Model): id = db.Column(db.Integer, primary_key=True); provider = db.Column(db.String(50),
                                                                                          nullable=False); created_at = db.Column(
    db.DateTime, default=datetime.utcnow, nullable=False); token = db.Column(db.JSON,
                                                                             nullable=False); user_id = db.Column(
    db.Integer, db.ForeignKey(User.id), nullable=False); user = db.relationship(User)


google_blueprint = make_google_blueprint(scope=["openid", "https://www.googleapis.com/auth/userinfo.email",
                                                "https://www.googleapis.com/auth/userinfo.profile"],
                                         storage=SQLAlchemyStorage(OAuth, db.session, user=current_user))
app.register_blueprint(google_blueprint, url_prefix="/login")

shop_info = {
    "name": "НОВА ХВИЛЯ",
    "categories": [
        {'name': 'ПОЛИВОЧНА СИСТЕМА', 'image': 'irrigation.jpg', 'icon': 'irrigation.jpg'},
        {'name': 'НАСОСИ', 'image': 'pumps.jpg', 'icon': 'pumps.jpg'},
        {'name': 'БОЙЛЕРА', 'image': 'boilers.jpg', 'icon': 'boilers.jpg'},
        {'name': 'ЗМІШУВАЧІ', 'image': 'faucets.jpg', 'icon': 'faucets.jpg'},
        {'name': "ВИТЯЖКИ", 'image': 'hoods.jpg', 'icon': 'hoods.jpg'},
        {'name': "КОЛОНКИ", 'image': 'gas_parts.jpg', 'icon': 'gas_columns.jpg'},
        {'name': "СУШКА ДЛЯ РУШНИКІВ", 'image': 'towel_dryers.jpg', 'icon': 'towel_dryers.jpg'},
        {'name': "ЗАПЧАСТИНИ ДО ГАЗ ОБЛАДНАННЯ", 'image': 'gas_parts.jpg', 'icon': 'gas_parts.jpg'}
    ],
    "address": "вул. Гоголя, 47/2", "city": "м. Миргород",
    "phone": ["+38 (050) 670-62-16", "+38 (095) 752-32-58"], "email": "novakhvylia@gmail.com",
    "hours": {"Пн - Пт:": "8:00 - 17:00", "Субота:": "8:00 - 15:00", "Неділя:": "8:00 - 15:00"}
}


@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin: flash(
            'Доступ до цієї сторінки мають тільки адміністратори.', 'danger'); return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


@app.context_processor
def inject_now(): return {'now': datetime.utcnow(), 'shop': shop_info}


@app.route("/")
def index():
    hero_slides = [
        {'image': 'hero-bg.jpg', 'title': 'Професійна сантехніка та обладнання',
         'subtitle': 'Якісні товари для вашого дому з гарантією та доставкою'},
        {'image': 'hero-bg2.jpg', 'title': 'Надійні насоси для будь-яких потреб',
         'subtitle': 'Від найкращих виробників'},
        {'image': 'kotly.jpg', 'title': 'Все для систем опалення', 'subtitle': 'Котли, бойлери та комплектуючі'}
    ]
    products = Product.query.order_by(Product.id.desc()).limit(4).all()
    return render_template("index.html", products=products, hero_slides=hero_slides)


@app.route('/catalog')
def catalog():
    page = request.args.get('page', 1, type=int)
    query = Product.query
    if search_query := request.args.get('search', ''):
        query = query.filter(Product.name.ilike(f'%{search_query}%'))
    if category_arg := request.args.get('category'):
        query = query.filter(Product.category == category_arg.strip())
    if request.args.get('in_stock'):
        query = query.filter(Product.in_stock == True)
    if min_price := request.args.get('min_price', type=float):
        query = query.filter(Product.price >= min_price)
    if max_price := request.args.get('max_price', type=float):
        query = query.filter(Product.price <= max_price)
    if request.args.get('min_rating'):
        query = query.filter(Product.rating >= 4.0)
    if brands := request.args.getlist('brand'):
        query = query.filter(Product.brand.in_([b.strip() for b in brands]))

    products = query.paginate(page=page, per_page=9, error_out=False)
    brands = [b[0] for b in db.session.query(Product.brand).distinct().order_by(Product.brand).all() if b[0]]
    categories = [c[0] for c in db.session.query(Product.category).distinct().order_by(Product.category).all() if c[0]]

    return render_template('catalog.html', products=products, brands=brands, categories=categories)


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    similar_products = Product.query.filter(Product.category == product.category, Product.id != product.id).limit(
        4).all()
    return render_template("product_detail.html", product=product, similar_products=similar_products)


@app.route('/get_products_by_ids', methods=['POST'])
def get_products_by_ids():
    product_ids = request.json.get('ids', [])
    if not product_ids:
        return jsonify([])
    try:
        safe_product_ids = [int(pid) for pid in product_ids]
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid IDs provided'}), 400

    products = Product.query.filter(Product.id.in_(safe_product_ids)).all()

    products_data = [
        {
            'id': p.id, 'name': p.name, 'price': p.price, 'image': p.image, 'brand': p.brand,
            'in_stock': p.in_stock, 'url': url_for('product_detail', product_id=p.id)
        } for p in products
    ]
    return jsonify(products_data)


def get_reviews_data(product_id):
    product = Product.query.get_or_404(product_id)
    all_reviews_and_questions = product.reviews.order_by(Review.timestamp.desc())

    reviews_only = [r for r in all_reviews_and_questions if r.review_type == 'review' and r.parent_id is None]
    questions_only = [q for q in all_reviews_and_questions if q.review_type == 'question' and q.parent_id is None]

    reviews_with_rating = [r for r in reviews_only if r.rating > 0]
    total_with_rating_count = len(reviews_with_rating)
    ratings_list = [r.rating for r in reviews_with_rating]
    rating_counts = Counter(ratings_list)
    rating_breakdown = {star: rating_counts.get(star, 0) for star in range(5, 0, -1)}

    return {
        'product': product, 'reviews': reviews_only, 'questions': questions_only,
        'review_only_count': len(reviews_only), 'rating_breakdown': rating_breakdown,
        'total_reviews_with_rating': total_with_rating_count
    }


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
    new_review_data = {
        'product_id': product_id, 'text': form.get('text'),
        'author_name': form.get('author_name', 'Анонім'), 'author_email': form.get('author_email'),
        'review_type': form.get('review_type', 'review'),
        'parent_id': form.get('parent_id') if form.get('parent_id') else None
    }
    if new_review_data['review_type'] == 'review': new_review_data['rating'] = int(form.get('rating', 0))
    if current_user.is_authenticated:
        new_review_data['user_id'] = current_user.id
        new_review_data['author_name'] = current_user.username
    db.session.add(Review(**new_review_data))
    if new_review_data['review_type'] == 'review' and not new_review_data['parent_id']:
        result = db.session.query(func.avg(Review.rating), func.count(Review.id)).filter(
            Review.product_id == product_id, Review.rating > 0).one()
        product.rating = float(result[0] or 0)
        product.reviews_count = int(result[1] or 0)
    db.session.commit()
    flash('Дякуємо! Ваш запис було успішно додано.', 'success')
    review_type = request.form.get('review_type', 'review')
    if review_type == 'question':
        return redirect(url_for('product_questions', product_id=product_id))
    return redirect(url_for('product_reviews', product_id=product_id))


# ────────────────────────────────
#  АВТЕНТИФІКАЦІЯ
# ────────────────────────────────
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data.get('email')).first()
    if user and user.check_password(data.get('password')):
        login_user(user, remember=True)
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Невірний email або пароль"}), 401


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    email = data.get('email')
    if User.query.filter_by(email=email).first():
        return jsonify({"status": "error", "message": "Цей email вже зареєстровано"}), 400

    username_base = email.split('@')[0]
    username, counter = username_base, 1
    while User.query.filter_by(username=username).first():
        username = f"{username_base}_{counter}"
        counter += 1

    new_user = User(username=username, email=email)
    new_user.set_password(data.get('password'))
    db.session.add(new_user)
    db.session.commit()
    login_user(new_user, remember=True)

    subject = f"Вітаємо у {shop_info['name']}!"
    html_body = render_template("email/welcome.html", user=new_user, shop=shop_info)
    send_email(new_user.email, subject, html_body)

    return jsonify({"status": "success"})


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@oauth_authorized.connect_via(google_blueprint)
def google_logged_in(blueprint, token):
    if not token:
        flash("Не вдалося увійти через Google.", category="error")
        return redirect(url_for("index"))
    resp = blueprint.session.get("/oauth2/v2/userinfo")
    if not resp.ok:
        flash("Не вдалося отримати інформацію про користувача.", category="error")
        return redirect(url_for("index"))

    google_info = resp.json()
    email = google_info["email"]
    user = User.query.filter_by(email=email).first()
    if not user:
        username_base = google_info.get("name", email.split('@')[0])
        username, counter = username_base, 1
        while User.query.filter_by(username=username).first():
            username = f"{username_base}_{counter}"
            counter += 1
        user = User(email=email, username=username, avatar_url=google_info.get('picture'))
        user.set_password(os.urandom(16).hex())
        db.session.add(user)
        subject = f"Вітаємо у {shop_info['name']}!"
        html_body = render_template("email/welcome.html", user=user, shop=shop_info)
        send_email(user.email, subject, html_body)
    else:
        if not user.avatar_url and google_info.get('picture'):
            user.avatar_url = google_info.get('picture')
    db.session.commit()

    login_user(user)
    flash("Ви успішно увійшли через Google!", category="success")
    return redirect(url_for("index"))


# ────────────────────────────────
#  КОШИК ТА ОФОРМЛЕННЯ ЗАМОВЛЕННЯ
# ────────────────────────────────
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
            session["cart"] = cart
            return jsonify(status="success", message="Кількість оновлено")
        else:
            del cart[product_id_str]
            session["cart"] = cart
            return jsonify(status="success", message="Товар видалено з кошика")

    return jsonify(status="error", message="Товар не знайдено в кошику"), 404


@app.route('/get_cart')
def get_cart():
    cart = session.get("cart", {})
    cart_items = []
    total = 0
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
    product_id_str = str(product_id)
    if product_id_str in cart:
        del cart[product_id_str]
        session["cart"] = cart
    return jsonify(status="success", message="Товар видалено з кошика", cart_count=sum(cart.values()))


@app.route('/buy_now', methods=['POST'])
def buy_now():
    product_id = str(request.get_json().get("product_id"))
    session["cart"] = {product_id: 1}
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

        order = Order(
            customer_name=request.form.get('customer_name'),
            customer_phone=request.form.get('customer_phone'),
            delivery_method=request.form.get('delivery_method'),
            payment_method=request.form.get('payment_method'),
            total_cost=total_cost,
            user_id=current_user.id if current_user.is_authenticated else None
        )
        db.session.add(order)
        db.session.flush()

        order_items_for_email = []
        for pid, qty in cart.items():
            if p := product_map.get(pid):
                order_item = OrderItem(order_id=order.id, product_id=p.id, quantity=qty, price=p.price)
                db.session.add(order_item)
                order_items_for_email.append({'product': p, 'quantity': qty, 'price': p.price})

        db.session.commit()
        try:
            admin_email = os.getenv("SMTP_USER")
            if admin_email:
                subject = f"Нове замовлення #{order.id} на сайті {shop_info['name']}"
                html_body = render_template(
                    "email/order_notification.html",
                    order=order, items=order_items_for_email, shop=shop_info
                )
                send_email(admin_email, subject, html_body)
        except Exception as e:
            print(f">>> КРИТИЧНА ПОМИЛКА при відправці листа про замовлення: {e}")

        session.pop('cart', None)
        flash('Дякуємо! Ваше замовлення прийнято.', 'success')
        return redirect(url_for('index'))

    return render_template('checkout.html')


# ────────────────────────────────
#  АДМІН-ПАНЕЛЬ
# ────────────────────────────────
@app.route('/admin/reviews')
@login_required
@admin_required
def admin_reviews():
    page = request.args.get('page', 1, type=int)
    all_reviews = Review.query.order_by(Review.timestamp.desc())
    reviews = all_reviews.paginate(page=page, per_page=15, error_out=False)
    return render_template('admin_reviews.html', reviews=reviews)


@app.route("/admin/add_product", methods=['GET', 'POST'])
@login_required
@admin_required
def add_product():
    if request.method == 'POST':
        new_product = Product(
            name=request.form['name'], price=float(request.form['price']),
            description=request.form['description'], image=request.form['image'],
            category=request.form['category'], brand=request.form['brand'],
            in_stock='in_stock' in request.form
        )
        db.session.add(new_product);
        db.session.commit()
        flash(f"Товар '{new_product.name}' успішно додано!", "success")
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
        product.image = request.form['image']
        product.category = request.form['category']
        product.brand = request.form['brand']
        product.in_stock = 'in_stock' in request.form
        db.session.commit()
        flash(f"Товар '{product.name}' успішно оновлено!", "success")
        return redirect(url_for('catalog'))

    return render_template("edit_product.html", product=product)


@app.route("/admin/delete_review/<int:review_id>", methods=["POST"])
@login_required
@admin_required
def delete_review(review_id):
    review_to_delete = Review.query.get_or_404(review_id)
    product_id = review_to_delete.product_id
    is_admin_page = 'admin' in request.referrer
    db.session.delete(review_to_delete)
    db.session.commit()
    flash("Запис було успішно видалено.", "success")
    if is_admin_page:
        return redirect(url_for('admin_reviews'))
    return redirect(request.referrer or url_for('product_reviews', product_id=product_id))


@app.route("/admin/delete_product/<int:product_id>", methods=["POST"])
@login_required
@admin_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    flash(f"Товар '{product.name}' було видалено.", "success")
    db.session.delete(product);
    db.session.commit()
    return redirect(url_for('catalog'))


# ────────────────────────────────
#  ІНШІ МАРШРУТИ
# ────────────────────────────────
@app.route("/send_message", methods=["POST"])
def send_message():
    form = request.form
    subject = f"Нове повідомлення від {form.get('name')}"
    body = f"Ім'я: {form.get('name')}\nEmail: {form.get('email')}\n\nПовідомлення:\n{form.get('message')}"

    if send_email(os.getenv("SMTP_USER"), subject, body):
        return jsonify(status="success", message="✅ Повідомлення успішно надіслано!")
    else:
        return jsonify(status="error", message="❌ Помилка сервера при відправці повідомлення."), 500


@app.route("/favorites")
def favorites_page(): return render_template("favorites.html")


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
    print("BAS: пройдено етап handshake (get_1c_system_info).")
    return "success\nphpsessid\n1234567\nzip=no\nfile_limit=104857600"


@app.route('/api/bas_import', methods=['POST'], strict_slashes=False)
@require_api_key
def bas_import():
    if 'file' not in request.files:
        return "failure\nFile part is missing in the request.", 400

    cml_file = request.files['file']
    if cml_file.filename == '':
        return "failure\nNo selected file.", 400

    print(f"BAS: Отримано файл '{cml_file.filename}' для імпорту.")

    try:
        xml_data = cml_file.read().decode('utf-8')
        root = ET.fromstring(xml_data)

        # [ВИПРАВЛЕНО] Логіка для роботи з неймспейсами (головна зміна!)
        ns_map = {}
        if '}' in root.tag:
            namespace = root.tag.split('}')[0][1:]
            ns_map['ns'] = namespace
            print(f"Знайдено неймспейс: {namespace}")

        def find_element(parent, path):
            return parent.find(path, ns_map)

        def findall_elements(parent, path):
            return parent.findall(path, ns_map)

        def find_text(parent, path, default=''):
            el = parent.find(path, ns_map)
            return el.text.strip() if el is not None and el.text else default

        # Подальша логіка використовує нові функції для пошуку
        products_catalog = {}
        catalog_node = find_element(root, './/ns:Каталог')
        if catalog_node is None:
            print("ПОМИЛКА: Не знайдено тег <Каталог> у CML-файлі.")
            return "failure\nНе знайдено тег <Каталог>.", 400

        for product_node in findall_elements(catalog_node, './/ns:Товар'):
            product_id = find_text(product_node, 'ns:Ид')
            if not product_id: continue

            brand_name = find_text(find_element(product_node, 'ns:Изготовитель'), 'ns:Наименование', 'Без бренду')

            products_catalog[product_id] = {
                'name': find_text(product_node, 'ns:Наименование', 'Без назви'),
                'description': find_text(product_node, 'ns:Описание', ''),
                'brand': brand_name
            }

        offers_package = find_element(root, './/ns:ПакетПредложений')
        if offers_package is None:
            print("ПОМИЛКА: Не знайдено тег <ПакетПредложений> у CML-файлі.")
            return "failure\nНе знайдено тег <ПакетПредложений>.", 400

        updated_count, added_count = 0, 0
        for offer_node in findall_elements(offers_package, './/ns:Предложение'):
            offer_id = find_text(offer_node, 'ns:Ид')
            if not offer_id or offer_id not in products_catalog: continue

            price_text = find_text(find_element(offer_node, './/ns:Цена'), 'ns:ЦенаЗаЕдиницу', '0').replace(',', '.')
            price = 0.0
            try:
                price = float(re.match(r"[\d.]+", price_text).group(0))
            except (ValueError, AttributeError):
                pass

            stock_text = find_text(offer_node, 'ns:Количество', '0')
            try:
                in_stock = int(stock_text) > 0
            except ValueError:
                in_stock = False

            product_data = products_catalog[offer_id]
            product = Product.query.filter_by(name=product_data['name']).first()
            if product:
                product.price, product.description, product.brand, product.in_stock = price, product_data[
                    'description'], product_data['brand'], in_stock
                updated_count += 1
            else:
                db.session.add(Product(name=product_data['name'], price=price, description=product_data['description'],
                                       brand=product_data['brand'], in_stock=in_stock, category="Новинки з BAS",
                                       image="default.jpg"))
                added_count += 1

        db.session.commit()
        message = f"Імпорт CommerceML завершено. Оновлено: {updated_count}, Додано нових: {added_count}."
        print(message)
        return f"success\n{message}"

    except ET.ParseError as e:
        print(f"Помилка парсингу CML: {e}")
        return f"failure\nПомилка парсингу CML: {e}", 400
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        print(f"Критична помилка під час імпорту з BAS: {e}")
        return f"failure\nВнутрішня помилка сервера: {e}", 500

# ────────────────────────────────
#  ЗАПУСК ДОДАТКУ
# ────────────────────────────────
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(is_admin=True).first():
            print(">>> Створення адміністратора...")
            admin = User(username='admin', email='artemcool200911@gmail.com', is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin);
            db.session.commit()
            print(">>> Адміністратора створено. Логін: admin, Пароль: admin123")
    app.run(debug=True)