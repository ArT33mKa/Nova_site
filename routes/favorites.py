from flask import Blueprint, request, jsonify, url_for
from flask_login import current_user

from extensions import db
from models import Product, Favorite
from utils import get_image

favorites_bp = Blueprint('favorites', __name__, url_prefix='/favorites')


def _product_dict(p):
    return {
        "id": p.id,
        "name": p.name,
        "price": p.price,
        "image": get_image(p.image),
        "in_stock": p.in_stock,
        "url": url_for('main.product_detail', product_id=p.id),
    }


@favorites_bp.route('/ids')
def ids():
    """Список id обраних товарів. Для гостя — порожній (стан у localStorage)."""
    if current_user.is_authenticated:
        rows = Favorite.query.filter_by(user_id=current_user.id).all()
        return jsonify(ids=[f.product_id for f in rows])
    return jsonify(ids=[])


@favorites_bp.route('/toggle', methods=['POST'])
def toggle():
    data = request.get_json(silent=True) or {}
    try:
        product_id = int(data.get('product_id'))
    except (TypeError, ValueError):
        return jsonify(status='error', message='Невірний товар'), 400

    product = Product.query.get(product_id)
    if not product:
        return jsonify(status='error', message='Товар не знайдено'), 404

    # Гість: стан зберігається на клієнті (localStorage)
    if not current_user.is_authenticated:
        return jsonify(status='guest')

    fav = Favorite.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if fav:
        db.session.delete(fav)
        active = False
    else:
        db.session.add(Favorite(user_id=current_user.id, product_id=product_id))
        active = True
    db.session.commit()
    count = Favorite.query.filter_by(user_id=current_user.id).count()
    return jsonify(status='success', active=active, count=count)


@favorites_bp.route('/items', methods=['POST'])
def items():
    """Деталі товарів за списком id (для рендера сайдбара обраного)."""
    data = request.get_json(silent=True) or {}
    raw_ids = data.get('ids')

    if current_user.is_authenticated and not raw_ids:
        ids_list = [f.product_id for f in Favorite.query.filter_by(user_id=current_user.id).all()]
    else:
        ids_list = []
        for x in (raw_ids or []):
            try:
                ids_list.append(int(x))
            except (TypeError, ValueError):
                continue

    if not ids_list:
        return jsonify(items=[])

    products = Product.query.filter(Product.id.in_(ids_list)).all()
    order = {pid: i for i, pid in enumerate(ids_list)}
    products.sort(key=lambda p: order.get(p.id, 0))
    return jsonify(items=[_product_dict(p) for p in products])
