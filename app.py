import os
import logging
from datetime import datetime, timezone
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import login_required, current_user
from flask_dance.contrib.google import make_google_blueprint
from flask_dance.consumer.storage.sqla import SQLAlchemyStorage
from dotenv import load_dotenv

# ІМПОРТИ РОЗШИРЕНЬ ТА МОДЕЛЕЙ
from extensions import db, login_manager, csrf
from models import User, OAuth
from utils import shop_info

# ІМПОРТИ BLUEPRINTS (Наші нові папки)
from routes.api import api_bp
from routes.admin import admin_bp
from routes.cart import cart_bp
from routes.auth import auth_bp
from routes.main import main_bp

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# КОНФІГУРАЦІЯ
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.secret_key = os.getenv("FLASK_SECRET", "nova-secret")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///site.db').replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ІНІЦІАЛІЗАЦІЯ
db.init_app(app)
csrf.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message_category = "info"

app.jinja_env.add_extension('jinja2.ext.do')


# РЕЄСТРАЦІЯ BLUEPRINTS
app.register_blueprint(api_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(cart_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)

# Google OAuth
google_bp = make_google_blueprint(
    scope=["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"],
    storage=SQLAlchemyStorage(OAuth, db.session, user=current_user)
)
app.register_blueprint(google_bp, url_prefix="/login")

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Контекстні змінні (доступні у всіх шаблонах)
@app.context_processor
def inject_global_vars():
    cart_ids = set()
    if current_user.is_authenticated:
        cart_ids = {item.product_id for item in current_user.cart_items}
    else:
        cart_ids = {int(pid) for pid in session.get('cart', {}).keys() if pid.isdigit()}

    return {
        'now': datetime.now(timezone.utc),
        'shop': shop_info,
        'cart_ids': cart_ids
    }

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)