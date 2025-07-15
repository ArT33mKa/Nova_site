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

# ────────────────────────────────
#  НОВІ ІМПОРТИ ДЛЯ GOOGLE OAUTH
# ────────────────────────────────
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.consumer import oauth_authorized
from flask_dance.consumer.storage.sqla import SQLAlchemyStorage

# ────────────────────────────────
#  INIT & CONFIG
# ────────────────────────────────
load_dotenv()
app = Flask(__name__)
app.jinja_env.add_extension('jinja2.ext.do')
app.secret_key = os.getenv("FLASK_SECRET", "nova-secret")

# Налаштування для Google OAuth з .env файлу
app.config["GOOGLE_OAUTH_CLIENT_ID"] = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
app.config["GOOGLE_OAUTH_CLIENT_SECRET"] = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")

# Нова, правильна версія
db_uri = os.getenv('DATABASE_URL')
if db_uri and db_uri.startswith('postgres://'):
    db_uri = db_uri.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri or 'sqlite:///site.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Будь ласка, увійдіть, щоб виконати цю дію."
login_manager.login_message_category = "info"


# ────────────────────────────────
#  MODELS (без змін)
# ────────────────────────────────
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    reviews = db.relationship('Review', backref='author', lazy='dynamic')
    orders = db.relationship('Order', backref='customer', lazy='dynamic')

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
    reviews = db.relationship('Review', backref='product', lazy='dynamic')


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    delivery_method = db.Column(db.String(50))
    payment_method = db.Column(db.String(50))
    total_cost = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    items = db.relationship('OrderItem', backref='order', lazy='dynamic', cascade="all, delete-orphan")


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)


# ────────────────────────────────
#  НОВА МОДЕЛЬ ДЛЯ ЗБЕРІГАННЯ OAuth
# ────────────────────────────────
class OAuth(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    token = db.Column(db.JSON, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=False)
    user = db.relationship(User)


# ────────────────────────────────
#  НАЛАШТУВАННЯ GOOGLE OAUTH
# ────────────────────────────────
google_blueprint = make_google_blueprint(
    scope=["openid", "https://www.googleapis.com/auth/userinfo.email",
           "https://www.googleapis.com/auth/userinfo.profile"],
    storage=SQLAlchemyStorage(OAuth, db.session, user=current_user)
)
app.register_blueprint(google_blueprint, url_prefix="/login")

# ────────────────────────────────
#  UTILITIES & HELPERS
# ────────────────────────────────
shop_info = {
    "name": "НОВА ХВИЛЯ",
    "categories": ['ПОЛИВОЧНА СИСТЕМА', 'НАСОСИ', 'БОЙЛЕРА', 'ЗМІШУВАЧІ', 'ДОМОВЕНТ', "ВИТЯЖКИ", "КОЛОНКИ",
                   "СУШКА ДЛЯ РУШНИКІВ", "ЗАПЧАСТИНИ ДО ГАЗ ОБЛАДНАННЯ"],
    "address": "вул. Гоголя, 47/2", "city": "м. Миргород", "phone": ["+38 (050) 670-62-16", "+38 (095) 752-32-58"],
    "email": "novakhvylia@gmail.com",
    "hours": {"Пн - Пт:": "8:00 - 17:00", "Субота:": "8:00 - 15:00", "Неділя:": "8:00–15:00"}
}


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


# ────────────────────────────────
#  PUBLIC ROUTES (без змін)
# ────────────────────────────────
@app.route("/")
def index():
    products = Product.query.order_by(Product.id.desc()).limit(4).all()
    return render_template("index.html", products=products)


@app.route('/catalog')
def catalog():
    page = request.args.get('page', 1, type=int)
    per_page = 9
    query = Product.query
    if category_arg := request.args.get('category'): query = query.filter(Product.category == category_arg)
    if request.args.get('in_stock'): query = query.filter(Product.in_stock == True)
    if min_price_arg := request.args.get('min_price', type=float): query = query.filter(Product.price >= min_price_arg)
    if max_price_arg := request.args.get('max_price', type=float): query = query.filter(Product.price <= max_price_arg)
    if request.args.get('min_rating'): query = query.filter(Product.rating >= 4.0)
    if brands_filter := request.args.getlist('brand'): query = query.filter(Product.brand.in_(brands_filter))
    products = query.paginate(page=page, per_page=per_page, error_out=False)
    brands = [b[0] for b in db.session.query(Product.brand).distinct().order_by(Product.brand).all() if b[0]]
    return render_template('catalog.html', products=products, brands=brands)


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    reviews = product.reviews.order_by(Review.timestamp.desc()).all()
    return render_template("product_detail.html", product=product, reviews=reviews)


@app.route("/product/<int:product_id>/add_review", methods=['POST'])
@login_required  # Дозволити залишати відгуки тільки залогіненим користувачам
def add_review(product_id):
    product = Product.query.get_or_404(product_id)

    rating = request.form.get('rating', type=int)
    text = request.form.get('text')

    # Перевірка, чи користувач надав оцінку
    if not rating or rating < 1 or rating > 5:
        flash('Будь ласка, оберіть оцінку від 1 до 5.', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))

    # Створення нового відгуку
    new_review = Review(
        rating=rating,
        text=text,
        user_id=current_user.id,  # ID поточного користувача
        product_id=product.id
    )
    db.session.add(new_review)

    # Оновлення середнього рейтингу та кількості відгуків у товару
    # Розраховуємо новий середній рейтинг
    total_rating = (product.rating * product.reviews_count) + rating
    product.reviews_count += 1
    product.rating = round(total_rating / product.reviews_count, 1)

    db.session.commit()  # Зберігаємо зміни в базі даних

    flash('Дякуємо! Ваш відгук було додано.', 'success')
    return redirect(url_for('product_detail', product_id=product_id))

# ────────────────────────────────
#  ADMIN ROUTES (без змін)
# ────────────────────────────────
@app.route("/admin")
@login_required
@admin_required
def admin_panel():
    products = Product.query.order_by(Product.id.desc()).all()
    return render_template("admin_panel.html", products=products)


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
        db.session.add(new_product)
        db.session.commit()
        flash(f"Товар '{new_product.name}' успішно додано!", "success")
        return redirect(url_for('admin_panel'))
    return render_template("add_product.html")


@app.route("/admin/delete_product/<int:product_id>")
@login_required
@admin_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    flash(f"Товар '{product.name}' було видалено.", "success")
    db.session.delete(product)
    db.session.commit()
    return redirect(url_for('admin_panel'))


# ────────────────────────────────
#  MESSAGING & CHECKOUT (без змін)
# ────────────────────────────────
@app.route("/send_message", methods=["POST"])
def send_message():
    name, email, message, app_password = request.form.get("name"), request.form.get("email"), request.form.get(
        "message"), os.getenv("EMAIL_PASS")
    if not all([name, email, message, app_password]): return jsonify(status="error",
                                                                     message="Помилка: не всі дані заповнені або відсутній пароль додатку."), 400
    smtp_user, receiver = "artemcool200911@gmail.com", "artemcool200911@gmail.com"
    msg = MIMEMultipart()
    msg["From"], msg["To"], msg[
        "Subject"] = f"Сайт Нова Хвиля <{smtp_user}>", receiver, f"Нове повідомлення з сайту від {name}"
    msg.attach(MIMEText(f"Ім'я: {name}\nEmail: {email}\n\nПовідомлення:\n{message}", "plain", "utf-8"))
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls();
            server.login(smtp_user, app_password);
            server.send_message(msg)
        return jsonify(status="success", message="✅ Повідомлення успішно надіслано!")
    except Exception as e:
        return jsonify(status="error", message=f"❌ Помилка сервера: {e}"), 500


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = session.get('cart', {})
    if not cart: flash('Ваш кошик порожній.', 'info'); return redirect(url_for('catalog'))
    if request.method == 'POST':
        products = Product.query.filter(Product.id.in_([int(pid) for pid in cart.keys()])).all()
        product_map = {str(p.id): p for p in products}
        total_cost = sum(product_map[pid].price * qty for pid, qty in cart.items())
        new_order = Order(
            customer_name=request.form.get('customer_name'), customer_phone=request.form.get('customer_phone'),
            delivery_method=request.form.get('delivery_method'), payment_method=request.form.get('payment_method'),
            total_cost=total_cost, user_id=current_user.id if current_user.is_authenticated else None
        )
        db.session.add(new_order);
        db.session.flush()
        for product_id, quantity in cart.items():
            product = product_map.get(product_id)
            order_item = OrderItem(order_id=new_order.id, product_id=product.id, quantity=quantity, price=product.price)
            db.session.add(order_item)
        db.session.commit();
        session.pop('cart', None);
        flash('Дякуємо! Ваше замовлення прийнято.', 'success')
        return redirect(url_for('index'))
    return render_template('checkout.html')


# ─────────── AUTH SYSTEM ───────────
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
    if User.query.filter_by(email=data.get('email')).first(): return jsonify(
        {"status": "error", "message": "Цей email вже зареєстровано"}), 400
    if User.query.filter_by(username=data.get('username')).first(): return jsonify(
        {"status": "error", "message": "Це ім'я користувача вже зайняте"}), 400
    new_user = User(username=data.get('username'), email=data.get('email'))
    new_user.set_password(data.get('password'))
    db.session.add(new_user);
    db.session.commit();
    login_user(new_user, remember=True)
    return jsonify({"status": "success"})


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/buy_now', methods=['POST'])
def buy_now():
    data = request.get_json()
    product_id = str(data.get("product_id"))

    # Створюємо новий кошик лише з цим товаром
    cart = {product_id: 1}
    session["cart"] = cart

    return jsonify(status="success", message="Готово до оформлення")

# ────────────────────────────────────────────────────────────────
#  ОБРОБНИК ДЛЯ ЗБЕРЕЖЕННЯ КОРИСТУВАЧА ПІСЛЯ ВХОДУ ЧЕРЕЗ GOOGLE
#  ЦЕЙ КОД ЗАМІНЮЄ ВАШ СТАРИЙ МАРШРУТ /login/google/complete
# ────────────────────────────────────────────────────────────────
@oauth_authorized.connect_via(google_blueprint)
def google_logged_in(blueprint, token):
    if not token:
        flash("Не вдалося увійти через Google.", category="error")
        return redirect(url_for("index"))

    resp = blueprint.session.get("/oauth2/v2/userinfo")
    if not resp.ok:
        flash("Не вдалося отримати інформацію про користувача з Google.", category="error")
        return redirect(url_for("index"))

    google_info = resp.json()
    email = google_info["email"]

    user = User.query.filter_by(email=email).first()
    if not user:
        # Користувача не знайдено, створюємо нового
        username = google_info.get("name", email.split('@')[0])
        # Перевірка, чи ім'я користувача не зайняте
        if User.query.filter_by(username=username).first():
            username = f"{username}_{os.urandom(4).hex()}"  # Додаємо унікальний суфікс

        user = User(email=email, username=username)
        user.set_password(os.urandom(16).hex())  # Встановлюємо випадковий безпечний пароль
        db.session.add(user)
        db.session.commit()

    login_user(user)
    flash("Ви успішно увійшли через Google!", category="success")
    return redirect(url_for("index"))


# ─────────── CART SYSTEM (без змін) ───────────
@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    # Розбиваємо на два рядки
    data = request.get_json()
    product_id = str(data.get("product_id"))

    cart = session.get("cart", {})
    cart[product_id] = cart.get(product_id, 0) + 1
    session["cart"] = cart
    return jsonify(status="success", message="Товар додано до кошика", cart_count=sum(cart.values()))


@app.route('/get_cart')
def get_cart():
    cart, cart_items, total = session.get("cart", {}), [], 0
    if cart:
        products = Product.query.filter(Product.id.in_([int(pid) for pid in cart.keys()])).all()
        product_map = {str(p.id): p for p in products}
        for product_id, quantity in cart.items():
            if product := product_map.get(product_id):
                cart_items.append(
                    {"id": product.id, "name": product.name, "price": product.price, "image": product.image,
                     "quantity": quantity})
                total += product.price * quantity
    return jsonify({"items": cart_items, "total": total})


@app.route("/remove_from_cart/<int:product_id>", methods=["POST"])
def remove_from_cart(product_id):
    cart = session.get("cart", {})
    if str(product_id) in cart: del cart[str(product_id)]; session["cart"] = cart
    return jsonify(status="success", message="Товар видалено з кошика", cart_count=sum(cart.values()))


@app.route("/cart")
def cart_page(): return render_template("cart.html", shop=shop_info)


# ─────────── OTHER ROUTES (без змін) ───────────
@app.route("/favorites")
def favorites_page(): return render_template("favorites.html", shop=shop_info)


# ────────────────────────────────
#  INITIALIZATION
# ────────────────────────────────
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if User.query.count() == 0:
            print(">>> Створення адміністратора...")
            admin = User(username='admin', email='artemcool200911@gmail.com', is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin);
            db.session.commit()
            print(">>> Адміністратора створено. Логін: admin, Пароль: admin123")
    app.run(debug=True)