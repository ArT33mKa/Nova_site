from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, flash
from flask_login import current_user

from extensions import db
from models import Product, CartItem, Order, OrderItem
from utils import get_image

cart_bp = Blueprint('cart', __name__)

@cart_bp.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    product_id = int(request.get_json().get("product_id"))
    if current_user.is_authenticated:
        cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
        if cart_item:
            cart_item.quantity += 1
        else:
            db.session.add(CartItem(user_id=current_user.id, product_id=product_id, quantity=1))
        db.session.commit()
        cart_count = sum(item.quantity for item in current_user.cart_items)
    else:
        cart = session.get("cart", {})
        cart[str(product_id)] = cart.get(str(product_id), 0) + 1
        session["cart"] = cart
        cart_count = sum(cart.values())
    return jsonify(status="success", message="Товар додано до кошика", cart_count=cart_count)

@cart_bp.route('/update_cart_quantity/<int:product_id>', methods=['POST'])
def update_cart_quantity(product_id):
    new_quantity = request.json.get('quantity')
    if current_user.is_authenticated:
        cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
        if cart_item:
            if new_quantity and new_quantity > 0:
                cart_item.quantity = new_quantity
            else:
                db.session.delete(cart_item)
            db.session.commit()
            return jsonify(status="success")
    else:
        cart = session.get("cart", {})
        if str(product_id) in cart:
            if new_quantity and new_quantity > 0:
                cart[str(product_id)] = new_quantity
            else:
                del cart[str(product_id)]
            session["cart"] = cart
            return jsonify(status="success")
    return jsonify(status="error", message="Товар не знайдено"), 404

@cart_bp.route('/get_cart')
def get_cart():
    cart_items, total = [], 0
    if current_user.is_authenticated:
        for item in CartItem.query.filter_by(user_id=current_user.id).all():
            if item.product:
                cart_items.append({
                    "id": item.product.id, "name": item.product.name, "price": item.product.price,
                    "image": get_image(item.product.image), "quantity": item.quantity, "in_stock": item.product.in_stock,
                    "url": url_for('main.product_detail', product_id=item.product.id)
                })
                total += item.product.price * item.quantity
    else:
        cart = session.get("cart", {})
        if cart:
            product_map = {str(p.id): p for p in Product.query.filter(
                Product.id.in_([int(pid) for pid in cart.keys() if pid.isdigit()])).all()}
            for product_id, quantity in cart.items():
                if product := product_map.get(product_id):
                    cart_items.append({
                        "id": product.id, "name": product.name, "price": product.price, "image": get_image(product.image),
                        "quantity": quantity, "in_stock": product.in_stock,
                        "url": url_for('main.product_detail', product_id=product.id)
                    })
                    total += product.price * quantity
    return jsonify({"items": cart_items, "total": total})

@cart_bp.route("/remove_from_cart/<int:product_id>", methods=["POST"])
def remove_from_cart(product_id):
    if current_user.is_authenticated:
        CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).delete()
        db.session.commit()
    else:
        cart = session.get("cart", {})
        if str(product_id) in cart: del cart[str(product_id)]
        session["cart"] = cart
    return jsonify(status="success")

@cart_bp.route('/api/checkout_summary')
def checkout_summary():
    buy_now_id = request.args.get('buy_now_id')
    items, subtotal = [], 0

    def add_item(product, quantity):
        nonlocal subtotal
        line = product.price * quantity
        subtotal += line
        items.append({
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "image": get_image(product.image),
            "quantity": quantity,
            "in_stock": product.in_stock,
            "line_total": line,
            "url": url_for('main.product_detail', product_id=product.id)
        })

    if buy_now_id:
        product = Product.query.get(buy_now_id)
        if product:
            add_item(product, 1)
    elif current_user.is_authenticated:
        for item in CartItem.query.filter_by(user_id=current_user.id).all():
            if item.product:
                add_item(item.product, item.quantity)
    else:
        cart = session.get("cart", {})
        if cart:
            product_map = {str(p.id): p for p in Product.query.filter(
                Product.id.in_([int(pid) for pid in cart.keys() if pid.isdigit()])).all()}
            for pid, qty in cart.items():
                if product := product_map.get(pid):
                    add_item(product, qty)

    return jsonify({"items": items, "subtotal": subtotal})

@cart_bp.route('/checkout', methods=['GET', 'POST'])
def checkout():
    buy_now_id = request.args.get('buy_now_id')
    cart_items, total_cost = [], 0

    class VirtualCartItem:
        def __init__(self, product_obj, quantity=1):
            self.product, self.quantity, self.item_total = product_obj, quantity, product_obj.price * quantity

    if buy_now_id:
        product = Product.query.get_or_404(buy_now_id)
        if not product.in_stock:
            flash('На жаль, цей товар закінчився.', 'danger')
            return redirect(url_for('main.product_detail', product_id=product.id))
        cart_items = [VirtualCartItem(product, quantity=1)]
        total_cost = product.price
    else:
        if current_user.is_authenticated:
            cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        else:
            session_cart = session.get('cart', {})
            if session_cart:
                products = Product.query.filter(Product.id.in_([int(pid) for pid in session_cart.keys()])).all()
                for p in products: cart_items.append(VirtualCartItem(p, quantity=session_cart.get(str(p.id), 1)))
        if not cart_items:
            flash('Ваш кошик порожній', 'warning')
            return redirect(url_for('main.catalog'))
        total_cost = sum(item.product.price * item.quantity for item in cart_items)

    if request.method == 'POST':
        try:
            new_order = Order(
                user_id=current_user.id if current_user.is_authenticated else None,
                customer_name=f"{request.form.get('customer_first_name')} {request.form.get('customer_last_name')}",
                customer_phone=request.form.get('customer_phone'),
                delivery_method=f"{request.form.get('delivery_method')}: {request.form.get('delivery_city', '')}, {request.form.get('delivery_warehouse', '')}",
                payment_method=request.form.get('payment_method'),
                comment=request.form.get('order_comment'),
                total_cost=total_cost,
                status='Нове'
            )
            db.session.add(new_order)
            db.session.commit()

            for item in cart_items:
                db.session.add(OrderItem(order_id=new_order.id, product_id=item.product.id, quantity=item.quantity, price=item.product.price))
                item.product.buy_count = (item.product.buy_count or 0) + item.quantity
                item.product.update_global_score()

            if not buy_now_id:
                if current_user.is_authenticated:
                    CartItem.query.filter_by(user_id=current_user.id).delete()
                else:
                    session.pop('cart', None)
            db.session.commit()

            if request.form.get('payment_method') == 'Онлайн-оплата карткою':
                return redirect(url_for('payment.pay', order_id=new_order.id))
            flash('Дякуємо! Ваше замовлення прийнято. Менеджер зв\'яжеться з вами.', 'success')
            return redirect(url_for('main.index'))
        except Exception as e:
            db.session.rollback()
            flash('Сталася помилка при оформленні. Перевірте дані.', 'danger')

    return render_template('shop/checkout.html', cart_items=cart_items, total_cost=total_cost)
