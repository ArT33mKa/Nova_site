import os
from datetime import datetime, timezone
from flask import Flask, render_template, session
from flask_login import current_user
from dotenv import load_dotenv

# Розширення та моделі
from extensions import db, login_manager, csrf, oauth
from models import User
from utils import shop_info, get_image

# Blueprints (лише локальні: каталог/товари, кошик, пошук)
from routes.api import api_bp
from routes.cart import cart_bp
from routes.main import main_bp
from routes.auth import auth_bp
from routes.account import account_bp
from routes.favorites import favorites_bp
from routes.exchange import exchange_bp
from routes.payment import payment_bp

load_dotenv()

app = Flask(__name__)

# ЛОГУВАННЯ (видимість у fly logs)
import logging as _logging
_logging.basicConfig(level=_logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
app.logger.setLevel(_logging.INFO)

# КОНФІГУРАЦІЯ (локальний запуск)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.secret_key = os.getenv("FLASK_SECRET", "nova-secret")
db_url = os.getenv('DATABASE_URL', 'sqlite:///site.db')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ІНІЦІАЛІЗАЦІЯ
db.init_app(app)
csrf.init_app(app)
login_manager.init_app(app)
login_manager.login_message_category = "info"

# Google OAuth (Authlib)
oauth.init_app(app)
oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_OAUTH_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_OAUTH_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

app.jinja_env.add_extension('jinja2.ext.do')

# РЕЄСТРАЦІЯ BLUEPRINTS
app.register_blueprint(api_bp)
app.register_blueprint(cart_bp)
app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(account_bp)
app.register_blueprint(favorites_bp)
app.register_blueprint(exchange_bp)
app.register_blueprint(payment_bp)
csrf.exempt(exchange_bp)  # машинний обмін з 1С/BAF — без CSRF
csrf.exempt(payment_bp)  # вебхук від monobank — без CSRF


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# Контекстні змінні (доступні у всіх шаблонах)
@app.context_processor
def inject_global_vars():
    if current_user.is_authenticated:
        cart_ids = {item.product_id for item in current_user.cart_items}
    else:
        cart_ids = {int(pid) for pid in session.get('cart', {}).keys() if pid.isdigit()}

    return {
        'now': datetime.now(timezone.utc),
        'shop': shop_info,
        'cart_ids': cart_ids,
        'get_image': get_image
    }


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.after_request
def inject_seo(response):
    """Інжектимо SEO-теги (description, canonical, Open Graph) та GA4 у <head>."""
    try:
        ctype = response.content_type or ""
        if "text/html" not in ctype or response.direct_passthrough:
            return response
        body = response.get_data(as_text=True)
        if "</head>" not in body:
            return response
        import re as _re, html as _html
        from flask import request as _rq

        m = _re.search(r"<title>(.*?)</title>", body, _re.S)
        page_title = _html.escape((m.group(1).strip() if m else "НОВА ХВИЛЯ"), quote=True)

        extra = []
        if 'name="description"' not in body:
            desc = ("НОВА ХВИЛЯ — професійна сантехніка, насоси, водонагрівачі, "
                    "газове та опалювальне обладнання. Гарантія та доставка по всій Україні.")
            extra.append('<meta name="description" content="%s">' % _html.escape(desc, quote=True))
        if 'rel="canonical"' not in body:
            extra.append('<link rel="canonical" href="%s">' % _html.escape(_rq.base_url, quote=True))
        if 'property="og:' not in body:
            extra.append('<meta property="og:type" content="website">')
            extra.append('<meta property="og:site_name" content="НОВА ХВИЛЯ">')
            extra.append('<meta property="og:title" content="%s">' % page_title)
            extra.append('<meta property="og:url" content="%s">' % _html.escape(_rq.base_url, quote=True))
            extra.append('<meta name="twitter:card" content="summary">')

        ga4 = os.getenv("GA4_MEASUREMENT_ID")
        if ga4 and "gtag/js" not in body:
            extra.append('<script async src="https://www.googletagmanager.com/gtag/js?id=%s"></script>' % ga4)
            extra.append("<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','%s');</script>" % ga4)

        if extra:
            body = body.replace("</head>", chr(10).join(extra) + chr(10) + "</head>", 1)
            response.set_data(body)
    except Exception:
        pass
    return response


def ensure_schema():
    """Невелика міграція: додає колонку product.external_id (звірка з 1С/BAF), якщо її немає."""
    from sqlalchemy import text, inspect as sa_inspect
    try:
        insp = sa_inspect(db.engine)
        cols = [c['name'] for c in insp.get_columns('product')]
        if 'external_id' not in cols:
            db.session.execute(text('ALTER TABLE product ADD COLUMN external_id VARCHAR(64)'))
            db.session.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ix_product_external_id ON product (external_id)'))
            db.session.commit()
            print(">>> [schema] Додано колонку product.external_id")
        if 'image_hash' not in cols:
            db.session.execute(text('ALTER TABLE product ADD COLUMN image_hash VARCHAR(128)'))
            db.session.commit()
            print(">>> [schema] Додано колонку product.image_hash")
        order_cols = [c['name'] for c in insp.get_columns('order')]
        if 'payment_id' not in order_cols:
            db.session.execute(text('ALTER TABLE "order" ADD COLUMN payment_id VARCHAR(64)'))
            db.session.commit()
            print(">>> [schema] Додано колонку order.payment_id")
    except Exception as e:
        print(">>> [schema] Помилка міграції: %s" % e)


# Таблиці + потрібні колонки при кожному старті (локально та на fly.io)
with app.app_context():
    db.create_all()
    ensure_schema()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
