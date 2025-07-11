import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.consumer.storage.session import SessionStorage

# ────────────────────────────────
#  INIT
# ────────────────────────────────
load_dotenv()                                              # .env → ENV
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "nova-secret")  # безпечніше через ENV

google_bp = make_google_blueprint(
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    scope=[
        "openid",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email"
    ],
    redirect_to="google_auth_complete",
    storage=SessionStorage()
)

app.register_blueprint(google_bp, url_prefix="/login")

# ────────────────────────────────
#  ДАНІ МАГАЗИНУ
# ────────────────────────────────
shop_info = {
    "name": "НОВА ХВИЛЯ",
    "city": "Миргород",
    "address": "вул. Гоголя 47/2",
    "phone": ["+380506706216", "+380957523258"],
    "email": "novakhvylia@gmail.com",
    "hours": {
        "Mon‑Fri": "09:00–18:00",
        "Fri": "до:20:00",
        "Sat": "09:00–17:00",
        "Sun": "10:00–16:00",
    },
    "categories": [
        "Бойлера", "Насоси", "Сантехніка",
        "Котли", "Змішувачі", "Газове обладнання", "Запчастини"
    ],
}

tovar_db = [
    {
        "id": 1,
        "name": "Бойлер Atlantic 80 л",
        "price": 4200,
        "desc": "Надійний електричний бойлер з гарантією 5 років.",
        "image": "boiler.jpg",
        "category": "Бойлера"
    },
    {
        "id": 2,
        "name": "Газовий котел Bosch",
        "price": 9600,
        "desc": "Енергоефективний котел для будинку на 150 м².",
        "image": "kotol.jpg",
        "category": "Котли"
    },
    {
        "id": 3,
        "name": "Змішувач Hansgrohe",
        "price": 1900,
        "desc": "Якісний змішувач для кухні.",
        "image": "zmyshuvach.jpg",
        "category": "Змішувачі"
    },
    {
        "id": 4,
        "name": "Насос погружний Pedrollo",
        "price": 3100,
        "desc": "Потужний насос для водопостачання.",
        "image": "nasos.jpg",
        "category": "Насоси"
    }
]



# ────────────────────────────────
#  ДОПОМІЖНІ
# ────────────────────────────────
def get_all_products():
    return tovar_db


def get_products_by_ids(ids):
    return [p for p in tovar_db if p["id"] in ids]


# ────────────────────────────────
#  ROUTES
# ────────────────────────────────
@app.route("/")
def index():
    products = get_all_products()
    cart_count = len(session.get("cart", []))
    return render_template(
        "index.html",
        products=products,
        cart_count=cart_count,
        shop=shop_info,
        user=session.get("user"),
        show_home_sections=True  # ← для головної
    )


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = next((p for p in tovar_db if p["id"] == product_id), None)
    return render_template(
        "product.html", product=product, shop=shop_info, user=session.get("user")
    )


@app.route("/add_to_cart/<int:product_id>")
def add_to_cart(product_id):
    cart = session.setdefault("cart", [])
    cart.append(product_id)
    session.modified = True
    return redirect(url_for("cart_page"))



@app.route("/cart")
def cart_page():
    cart = session.get("cart", [])
    products = get_products_by_ids(cart)
    counts = {pid: cart.count(pid) for pid in cart}
    return render_template(
        "cart.html",
        products=products,
        product_counts=counts,
        shop=shop_info,
        user=session.get("user"),
    )


# -----------------  ADMIN  -----------------
@app.route("/admin")
def admin():
    return render_template("admin.html", products=tovar_db, shop=shop_info)


@app.route("/admin/delete/<int:product_id>")
def delete_product(product_id):
    global tovar_db
    tovar_db = [p for p in tovar_db if p["id"] != product_id]
    return redirect(url_for("admin"))

@app.route("/catalog")
def catalog():
    products = get_all_products()
    categories = sorted(set(p.get('category', '') for p in products if 'category' in p))
    return render_template(
        "catalog.html",
        products=products,
        categories=categories,
        shop=shop_info,
        user=session.get("user"),
        show_home_sections=False  # ← нічого зайвого не показуємо
    )

@app.route("/admin/add", methods=["GET", "POST"])
def add_product():
    if request.method == "POST":
        new_product = {
            "id": max((p["id"] for p in tovar_db), default=0) + 1,
            "name": request.form["name"],
            "price": int(request.form["price"]),
            "desc": request.form["desc"],
            "image": request.form["image"],
            "category": request.form["category"]  # 🟢 ОБОВ'ЯЗКОВО
        }
        tovar_db.append(new_product)
        return redirect(url_for("admin"))
    return render_template("add_product.html", shop=shop_info, user=session.get("user"))


@app.route("/get_session_cart")
def get_session_cart():
    cart_ids = session.get("cart", [])
    products = get_products_by_ids(cart_ids)
    cart_data = []

    for pid in cart_ids:
        product = next((p for p in products if p["id"] == pid), None)
        if product:
            cart_data.append({
                "id": product["id"],
                "name": product["name"],
                "price": product["price"],
                "image": product["image"],
                "qty": cart_ids.count(pid)
            })

    return jsonify(cart=cart_data)



# -----------------  GOOGLE OAUTH  -----------------
@app.route("/google_auth_complete")
def google_auth_complete():
    if not google.authorized:
        return redirect(url_for("google.login"))

    # 🔒 Зберігаємо корзину перед оновленням session
    saved_cart = session.get("cart", [])

    # Отримуємо дані користувача з Google
    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        return "Google OAuth помилка", 500

    data = resp.json()
    session.clear()  # 🧹 очищає все (включно з cart)
    session["user"] = {
        "name": data.get("name"),
        "email": data.get("email"),
        "picture": data.get("picture"),
    }

    # 🛒 Повертаємо корзину назад у session
    session["cart"] = saved_cart

    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))


# -----------------  EMAIL (контактна форма)  -----------------
@app.route("/send_message", methods=["POST"])
def send_message():
    name = request.form["name"]
    email = request.form["email"]
    message = request.form["message"]

    smtp_user = "artemcool200911@gmail.com"
    receiver = "artemcool200911@gmail.com"
    app_password = os.getenv("EMAIL_PASS")  # Встановлено в .env

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = receiver
    msg["Subject"] = f"Нове повідомлення від {name}"
    msg.attach(MIMEText(f"Ім’я: {name}\nEmail: {email}\n\n{message}", "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(smtp_user, app_password)
            server.send_message(msg)
        return jsonify(status="success", message="✅ Повідомлення надіслано!")
    except Exception as e:
        return jsonify(status="error", message=f"❌ Помилка: {e}"), 500

@app.route("/favorites")
def favorites_page():
    return render_template("favorites.html", shop=shop_info, user=session.get("user"))

# ────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)
