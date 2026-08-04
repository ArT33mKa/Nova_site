from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user, login_required

from extensions import db, oauth
from models import User, OAuth
from utils import normalize_phone, generate_unique_username

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        remember = bool(request.form.get('remember'))

        user = User.query.filter_by(email=email).first()
        if user and user.password_hash and user.check_password(password):
            login_user(user, remember=remember)
            flash('Вітаємо! Ви увійшли в акаунт.', 'success')
            next_url = request.args.get('next')
            return redirect(next_url or url_for('main.index'))
        flash('Невірна пошта або пароль.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        first_name = (request.form.get('first_name') or '').strip()
        last_name = (request.form.get('last_name') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        phone = normalize_phone(request.form.get('phone'))
        password = request.form.get('password') or ''
        password2 = request.form.get('password2') or ''
        agree = request.form.get('agree')

        errors = []
        if not first_name or not last_name:
            errors.append("Вкажіть ім'я та прізвище.")
        if not email:
            errors.append('Вкажіть електронну пошту.')
        if len(password) < 6:
            errors.append('Пароль має містити щонайменше 6 символів.')
        if password != password2:
            errors.append('Паролі не співпадають.')
        if not agree:
            errors.append('Потрібно надати згоду на обробку персональних даних.')
        if email and User.query.filter_by(email=email).first():
            errors.append('Користувач з такою поштою вже існує.')
        if phone and User.query.filter_by(phone=phone).first():
            errors.append('Користувач з таким номером вже існує.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('auth/register.html', form=request.form)

        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            username=generate_unique_username(f"{first_name} {last_name}".strip() or email),
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Реєстрація успішна! Ласкаво просимо.', 'success')
        return redirect(url_for('main.index'))

    return render_template('auth/register.html', form={})


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Ви вийшли з акаунту.', 'info')
    return redirect(url_for('main.index'))


@auth_bp.route('/google')
def google_login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    redirect_uri = url_for('auth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route('/google/callback')
def google_callback():
    try:
        token = oauth.google.authorize_access_token()
    except Exception:
        flash('Не вдалося увійти через Google. Спробуйте ще раз.', 'danger')
        return redirect(url_for('auth.login'))

    userinfo = token.get('userinfo') or {}
    email = (userinfo.get('email') or '').strip().lower()
    if not email:
        flash('Google не надав електронну пошту.', 'danger')
        return redirect(url_for('auth.login'))

    # Об'єднання акаунтів за email: якщо користувач з такою поштою вже є — входимо в нього
    user = User.query.filter_by(email=email).first()
    if user is None:
        full_name = (userinfo.get('name') or '').strip()
        first_name = (userinfo.get('given_name') or '').strip()
        last_name = (userinfo.get('family_name') or '').strip()
        if not first_name:
            first_name = full_name.split(' ')[0] if full_name else 'Користувач'
        if not last_name:
            parts = full_name.split(' ', 1)
            last_name = parts[1].strip() if len(parts) > 1 else 'Google'
        user = User(
            first_name=first_name,
            last_name=last_name or 'Google',
            email=email,
            username=generate_unique_username(full_name or email),
            is_email_verified=bool(userinfo.get('email_verified')),
            avatar_url=userinfo.get('picture'),
        )
        db.session.add(user)
        db.session.flush()

    # Прив'язуємо запис OAuth (один на провайдера для користувача)
    link = OAuth.query.filter_by(provider='google', user_id=user.id).first()
    if link is None:
        link = OAuth(provider='google', user_id=user.id, token=token)
        db.session.add(link)
    else:
        link.token = token
    db.session.commit()

    login_user(user, remember=True)
    flash('Ви увійшли через Google.', 'success')
    next_url = request.args.get('next')
    return redirect(next_url or url_for('main.index'))
