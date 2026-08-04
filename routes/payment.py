import os
import requests
from flask import Blueprint, redirect, url_for, request, flash, jsonify

from extensions import db
from models import Order

payment_bp = Blueprint('payment', __name__)

# Plata by mono (еквайринг Monobank)
MONO_API = "https://api.monobank.ua/api/merchant"


def _mono_token():
    return os.getenv("MONO_TOKEN")


@payment_bp.route('/payment/pay/<int:order_id>')
def pay(order_id):
    """Створює рахунок у monobank і веде клієнта на захищену сторінку оплати."""
    order = Order.query.get_or_404(order_id)
    token = _mono_token()
    if not token:
        flash("Онлайн-оплата тимчасово недоступна. Ваше замовлення прийнято — менеджер зв'яжеться з вами.", "warning")
        return redirect(url_for('main.index'))

    amount = int(round((order.total_cost or 0) * 100))
    if amount <= 0:
        flash("Некоректна сума замовлення.", "danger")
        return redirect(url_for('main.index'))

    payload = {
        "amount": amount,
        "ccy": 980,
        "merchantPaymInfo": {
            "reference": str(order.id),
            "destination": "Оплата замовлення №%s, НОВА ХВИЛЯ" % order.id,
        },
        "redirectUrl": url_for('payment.result', order_id=order.id, _external=True, _scheme='https'),
        "webHookUrl": url_for('payment.webhook', _external=True, _scheme='https'),
        "validity": 3600,
    }
    try:
        resp = requests.post(MONO_API + "/invoice/create", json=payload,
                             headers={"X-Token": token}, timeout=20)
        data = resp.json()
    except Exception:
        flash("Помилка з'єднання з платіжним сервісом. Спробуйте пізніше.", "danger")
        return redirect(url_for('main.index'))

    if resp.status_code != 200 or not data.get("pageUrl"):
        flash("Не вдалося створити рахунок на оплату. Замовлення збережено, менеджер зв'яжеться з вами.", "danger")
        return redirect(url_for('main.index'))

    order.payment_id = data.get("invoiceId")
    order.status = "Очікує оплати"
    db.session.commit()
    return redirect(data["pageUrl"])


@payment_bp.route('/payment/webhook', methods=['POST'])
def webhook():
    """Вебхук від monobank. Перевіряємо статус напряму в API (надійніше за підпис)."""
    token = _mono_token()
    try:
        body = request.get_json(force=True, silent=True) or {}
        invoice_id = body.get("invoiceId")
        if not invoice_id or not token:
            return jsonify(ok=True)

        resp = requests.get(MONO_API + "/invoice/status",
                            params={"invoiceId": invoice_id},
                            headers={"X-Token": token}, timeout=20)
        data = resp.json()
        status = data.get("status")

        order = Order.query.filter_by(payment_id=invoice_id).first()
        if order:
            if status == "success":
                order.status = "Оплачено"
            elif status in ("failure", "expired", "reversed"):
                order.status = "Оплата не пройшла"
            db.session.commit()
    except Exception:
        pass
    return jsonify(ok=True)


@payment_bp.route('/payment/result/<int:order_id>')
def result(order_id):
    """Сторінка, куди monobank повертає клієнта після оплати."""
    order = Order.query.get_or_404(order_id)
    if order.status == "Оплачено":
        flash("Дякуємо! Оплату отримано. Замовлення №%s в обробці." % order.id, "success")
    else:
        flash("Замовлення №%s оформлено. Якщо оплата ще обробляється, статус оновиться автоматично." % order.id, "info")
    return redirect(url_for('main.index'))
