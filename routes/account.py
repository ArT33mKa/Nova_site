from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user, logout_user

from extensions import db
from models import User
from utils import normalize_phone

account_bp = Blueprint('account', __name__, url_prefix='/account')


@account_bp.route('/', methods=['GET'])
@login_required
def settings():
    return render_template('account/settings.html')


@account_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    first_name = (request.form.get('first_name') or '').strip()
    last_name = (request.form.get('last_name') or '').strip()
    if not first_name or not last_name:
        flash("Ім'я та прізвище не можуть бути порожніми.", 'danger')
        return redirect(url_for('account.settings'))
    current_user.first_name = first_name
    current_user.last_name = last_name
    db.session.commit()
    flash('Дані профілю оновлено.', 'success')
    return redirect(url_for('account.settings'))


@account_bp.route('/update_email', methods=['POST'])
@login_required
def update_email():
    email = (request.form.get('email') or '').strip().lower()
    if not email:
        flash('Вкажіть електронну пошту.', 'danger')
        return redirect(url_for('account.settings'))
    existing = User.query.filter_by(email=email).first()
    if existing and existing.id != current_user.id:
        flash('Ця пошта вже використовується.', 'danger')
        return redirect(url_for('account.settings'))
    current_user.email = email
    db.session.commit()
    flash('Пошту оновлено.', 'success')
    return redirect(url_for('account.settings'))


@account_bp.route('/update_phone', methods=['POST'])
@login_required
def update_phone():
    phone = normalize_phone(request.form.get('phone'))
    if phone:
        existing = User.query.filter_by(phone=phone).first()
        if existing and existing.id != current_user.id:
            flash('Цей номер вже використовується.', 'danger')
            return redirect(url_for('account.settings'))
    current_user.phone = phone
    db.session.commit()
    flash('Номер телефону оновлено.', 'success')
    return redirect(url_for('account.settings'))


@account_bp.route('/update_password', methods=['POST'])
@login_required
def update_password():
    current = request.form.get('current_password') or ''
    new = request.form.get('new_password') or ''
    confirm = request.form.get('confirm_password') or ''
    if current_user.password_hash and not current_user.check_password(current):
        flash('Поточний пароль невірний.', 'danger')
        return redirect(url_for('account.settings'))
    if len(new) < 6:
        flash('Новий пароль має містити щонайменше 6 символів.', 'danger')
        return redirect(url_for('account.settings'))
    if new != confirm:
        flash('Нові паролі не співпадають.', 'danger')
        return redirect(url_for('account.settings'))
    current_user.set_password(new)
    db.session.commit()
    flash('Пароль оновлено.', 'success')
    return redirect(url_for('account.settings'))


@account_bp.route('/delete', methods=['POST'])
@login_required
def delete():
    user = current_user._get_current_object()
    logout_user()
    db.session.delete(user)
    db.session.commit()
    flash('Ваш акаунт видалено.', 'info')
    return redirect(url_for('main.index'))
