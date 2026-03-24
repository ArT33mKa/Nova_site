import random
import logging
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from firebase_admin import auth as firebase_auth

from extensions import db
from models import User, CartItem, Order, Review
from utils import generate_unique_username, normalize_phone_clean, send_email, shop_info

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

def merge_session_cart_to_db(user):
    session_cart = session.get('cart')
    if not session_cart:
        return
    try:
        db_cart_items = {item.product_id: item for item in user.cart_items}
        for product_id_str, quantity in session_cart.items():
            if not product_id_str.isdigit():
                continue
            product_id = int(product_id_str)
            if product_id in db_cart_items:
                db_cart_items[product_id].quantity += quantity
            else:
                new_item = CartItem(user_id=user.id, product_id=product_id, quantity=quantity)
                db.session.add(new_item)
        db.session.commit()
        session.pop('cart', None)
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error merging cart: {e}")

@auth_bp.route("/login", methods=["GET"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    return redirect(url_for('main.index', open_login='true', next=request.args.get('next')))

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Ви успішно вийшли з акаунту.", "success")
    return redirect(url_for('main.index'))

@auth_bp.route('/api/auth/firebase_verify', methods=['POST'])
def firebase_verify():
    try:
        data = request.get_json()
        token = data.get('token')
        intent = data.get('intent')

        if not token or not intent:
            return jsonify({'status': 'error', 'message': 'Відсутні необхідні дані'}), 400

        decoded_token = firebase_auth.verify_id_token(token)
        raw_phone = decoded_token.get('phone_number')

        if not raw_phone:
            return jsonify({'status': 'error', 'message': 'Номер телефону не підтверджено'}), 400

        phone = normalize_phone_clean(raw_phone)
        user = User.query.filter_by(phone=phone).first()

        if intent == 'login':
            if not user:
                return jsonify({'status': 'error', 'message': 'Користувача не знайдено. Будь ласка, зареєструйтесь.'}), 404

            login_user(user, remember=True)
            merge_session_cart_to_db(user)
            return jsonify({'status': 'success'})

        elif intent == 'register':
            if user:
                return jsonify({'status': 'error', 'message': 'Цей номер вже зареєстровано. Спробуйте увійти.'}), 409

            first_name = data.get('first_name', '').strip()
            last_name = data.get('last_name', '').strip()
            email = data.get('email', '').strip().lower()
            password = data.get('password', '')

            if not all([first_name, last_name, email, password]):
                return jsonify({'status': 'error', 'message': 'Всі поля мають бути заповнені'}), 400

            if User.query.filter_by(email=email).first():
                return jsonify({'status': 'error', 'message': 'Email вже використовується'}), 409

            new_user = User(
                phone=phone,
                first_name=first_name,
                last_name=last_name,
                email=email,
                username=generate_unique_username(first_name),
                is_email_verified=False
            )
            new_user.set_password(password)

            db.session.add(new_user)
            db.session.commit()

            login_user(new_user, remember=True)
            merge_session_cart_to_db(new_user)

            send_email(new_user.email, f"Вітаємо у {shop_info['name']}!",
                       render_template("email/welcome.html", user=new_user, shop=shop_info))

            return jsonify({'status': 'success'})

    except Exception as e:
        logger.error(f"Firebase verify error: {e}")
        return jsonify({'status': 'error', 'message': 'Критична помилка сервера'}), 500

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            token = user.get_reset_token()
            send_email(
                user.email,
                f"Відновлення пароля - {shop_info['name']}",
                render_template('email/password_reset.html', user=user, token=token, shop=shop_info)
            )
        flash('Якщо цей email зареєстрований, ви отримаєте інструкції протягом декількох хвилин.', 'info')
        return redirect(url_for('main.index'))
    return render_template('auth/forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    user = User.verify_reset_token(token)
    if not user:
        flash('Посилання недійсне або термін його дії закінчився.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')

        if not password or len(password) < 6:
            flash('Пароль має бути не менше 6 символів.', 'warning')
        elif password != confirm:
            flash('Паролі не співпадають.', 'warning')
        else:
            user.set_password(password)
            db.session.commit()
            flash('Ваш пароль успішно оновлено. Тепер ви можете увійти.', 'success')
            return redirect(url_for('main.index'))

    return render_template('auth/reset_password.html', token=token)

@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    user, email_from_token = User.verify_email_token(token)
    if not user or user.email != email_from_token:
        flash('Посилання для верифікації недійсне або застаріле.', 'danger')
        return redirect(url_for('main.index'))

    if not user.is_email_verified:
        user.is_email_verified = True
        db.session.commit()
        flash('Дякуємо! Ваш Email успішно підтверджено.', 'success')
    else:
        flash('Ваш Email вже було підтверджено раніше.', 'info')

    if current_user.is_authenticated:
        return redirect(url_for('auth.profile_settings'))
    login_user(user)
    return redirect(url_for('main.index'))

@auth_bp.route('/profile/settings', methods=['GET', 'POST'])
@login_required
def profile_settings():
    if request.method == 'POST':
        if 'update_info' in request.form:
            current_user.first_name = request.form.get('first_name', '').strip()
            current_user.last_name = request.form.get('last_name', '').strip()

            new_email = request.form.get('email', '').strip().lower()
            if new_email and new_email != current_user.email:
                if User.query.filter(User.email == new_email, User.id != current_user.id).first():
                    flash('Цей email вже використовується іншим користувачем.', 'danger')
                else:
                    current_user.email = new_email
                    current_user.is_email_verified = False
                    token = current_user.get_email_verify_token()
                    send_email(current_user.email, "Підтвердіть вашу нову пошту",
                               render_template('email/verify_email.html', user=current_user, token=token, shop=shop_info))
                    flash('Дані оновлено. Будь ласка, підтвердіть вашу нову пошту.', 'info')
            else:
                flash('Особисті дані оновлено.', 'success')

            db.session.commit()

        elif 'change_password' in request.form:
            curr_pass = request.form.get('current_password')
            new_pass = request.form.get('new_password')
            confirm = request.form.get('confirm_password')

            if current_user.password_hash and not current_user.check_password(curr_pass):
                flash('Поточний пароль невірний.', 'danger')
            elif not new_pass or len(new_pass) < 6:
                flash('Новий пароль занадто короткий.', 'warning')
            elif new_pass != confirm:
                flash('Нові паролі не співпадають.', 'warning')
            else:
                current_user.set_password(new_pass)
                db.session.commit()
                flash('Пароль успішно змінено.', 'success')

        return redirect(url_for('auth.profile_settings'))

    return render_template('user/profile_settings.html')

@auth_bp.route('/profile/orders')
@login_required
def my_orders():
    page = request.args.get('page', 1, type=int)
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.timestamp.desc()).paginate(page=page, per_page=10, error_out=False)
    return render_template('user/my_orders.html', orders=orders)

@auth_bp.route('/profile/reviews')
@login_required
def my_reviews():
    page = request.args.get('page', 1, type=int)
    reviews = Review.query.filter_by(user_id=current_user.id).order_by(Review.timestamp.desc()).paginate(page=page, per_page=10, error_out=False)
    return render_template('user/my_reviews.html', reviews=reviews)

@auth_bp.route('/api/auth/check_user_exists', methods=['POST'])
def check_user_exists():
    phone_raw = request.json.get('phone')
    if not phone_raw:
        return jsonify({'exists': False, 'error': 'Phone required'}), 400
    phone = normalize_phone_clean(phone_raw)
    user = User.query.filter_by(phone=phone).first()
    return jsonify({'exists': user is not None})