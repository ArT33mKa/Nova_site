import os
from flask import Blueprint, request, jsonify, url_for
from models import Product, Category
from utils import get_image

api_bp = Blueprint('api', __name__, url_prefix='/api')

NP_API_URL = 'https://api.novaposhta.ua/v2.0/json/'


@api_bp.route('/search_suggestions')
def search_suggestions():
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify({'products': [], 'categories': []})
    prods = Product.query.filter(Product.name.ilike(f'%{query}%'), Product.price > 1).order_by(
        Product.in_stock.desc()).limit(5).all()
    cats = Category.query.filter(Category.name.ilike(f'%{query}%')).limit(3).all()
    return jsonify({
        'products': [{'name': p.name, 'url': url_for('main.product_detail', product_id=p.id), 'category': p.category,
                      'image': get_image(p.image)} for p in prods],
        'categories': [{'name': c.name, 'url': url_for('main.catalog', category_slug=c.slug)} for c in cats]
    })


def _np_request(model, method, properties):
    """Проксі-запит до API Нової Пошти. requests імпортуємо ліниво,
    щоб відсутність бібліотеки не ламала запуск сайту."""
    api_key = os.getenv('NOVA_POSHTA_API_KEY', '')
    if not api_key:
        return None, 'NOVA_POSHTA_API_KEY не налаштований'
    try:
        import requests
    except ImportError:
        return None, 'Бібліотека requests не встановлена'
    try:
        resp = requests.post(NP_API_URL, json={
            'apiKey': api_key,
            'modelName': model,
            'calledMethod': method,
            'methodProperties': properties,
        }, timeout=8)
        data = resp.json()
        if not data.get('success'):
            return None, ', '.join(data.get('errors') or ['Помилка Нової Пошти'])
        return data.get('data', []), None
    except Exception as e:
        return None, str(e)


@api_bp.route('/np/cities')
def np_cities():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify(cities=[])
    data, err = _np_request('Address', 'getCities', {'FindByString': q, 'Limit': '20'})
    if err:
        return jsonify(cities=[], error=err)
    cities = [{
        'ref': c.get('Ref'),
        'name': c.get('Description'),
        'area': c.get('AreaDescription', '')
    } for c in (data or [])]
    return jsonify(cities=cities)


@api_bp.route('/np/warehouses')
def np_warehouses():
    city_ref = request.args.get('city_ref', '').strip()
    q = request.args.get('q', '').strip()
    if not city_ref:
        return jsonify(warehouses=[])
    props = {'CityRef': city_ref, 'Limit': '50'}
    if q:
        props['FindByString'] = q
    data, err = _np_request('Address', 'getWarehouses', props)
    if err:
        return jsonify(warehouses=[], error=err)
    warehouses = [{'name': w.get('Description')} for w in (data or [])]
    return jsonify(warehouses=warehouses)


@api_bp.route('/price_range')
def price_range():
    """Повертає реальні мінімальну та максимальну ціни товарів
    (опціонально в межах конкретної категорії)."""
    from sqlalchemy import func
    q = Product.query.filter(Product.price > 1)
    raw_slug = request.args.get('category_slug', '') or ''
    slug = raw_slug.strip('/').split('/')[-1] if raw_slug else ''
    if slug:
        category = Category.query.filter_by(slug=slug).first()
        if category:
            cat_ids = [category.id] + [child.id for child in category.children]
            q = q.filter(Product.category_id.in_(cat_ids))
    row = q.with_entities(func.min(Product.price), func.max(Product.price)).first()
    pmin = row[0] if row and row[0] is not None else 0
    pmax = row[1] if row and row[1] is not None else 0
    import math as _math
    return jsonify(min=int(_math.floor(pmin)), max=int(_math.ceil(pmax)))
