import os
import re
import tempfile
import threading
import requests
from lxml import etree as lxml_etree
from functools import wraps
from flask import Blueprint, request, jsonify, url_for, current_app
from flask_login import login_required, current_user
from sqlalchemy import func

from extensions import db, csrf
from models import Product, Category, CategoryView, Order, Favorite, Review
from utils import slugify, calculate_similarity, _get_cloudinary_url

api_bp = Blueprint('api', __name__, url_prefix='/api')

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        key = os.getenv('BAS_API_KEY', 'SUPER_SECRET_KEY_12345')
        if (request.headers.get('X-API-KEY') or request.args.get('key')) != key:
            return "failure\nInvalid API key.", 401
        return f(*args, **kwargs)
    return decorated_function

def require_bot_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not os.getenv('BOT_API_KEY') or request.headers.get('X-Bot-API-Key') != os.getenv('BOT_API_KEY'):
            return jsonify({"status": "error", "message": "Invalid API key"}), 401
        return f(*args, **kwargs)
    return decorated_function

@api_bp.route('/favorites/toggle', methods=['POST'])
@login_required
def toggle_favorite():
    data = request.get_json()
    product_id = data.get('product_id')
    if not product_id:
        return jsonify({'status': 'error', 'message': 'No product ID'}), 400

    fav = Favorite.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if fav:
        db.session.delete(fav)
        action = 'removed'
    else:
        db.session.add(Favorite(user_id=current_user.id, product_id=product_id))
        action = 'added'

    db.session.commit()
    count = Favorite.query.filter_by(user_id=current_user.id).count()
    return jsonify({'status': 'success', 'action': action, 'count': count})

@api_bp.route('/favorites/list', methods=['GET'])
def get_favorites_list():
    if current_user.is_authenticated:
        ids = [f.product_id for f in Favorite.query.filter_by(user_id=current_user.id).all()]
        return jsonify({'ids': ids})
    return jsonify({'ids': []})

@api_bp.route('/favorites/render', methods=['GET'])
@login_required
def render_favorites():
    favorites = Favorite.query.filter_by(user_id=current_user.id).order_by(Favorite.timestamp.desc()).all()
    products_data = []
    for f in favorites:
        p = Product.query.get(f.product_id)
        if p:
            products_data.append({
                'id': p.id,
                'name': p.name,
                'price': p.price,
                'image': p.image or '/static/img/no_image.png',
                'in_stock': p.in_stock,
                'url': url_for('main.product_detail', product_id=p.id)
            })
    return jsonify(products_data)

def process_bas_xml_background(tmp_path, app_instance):
    with app_instance.app_context():
        try:
            tree = lxml_etree.parse(tmp_path)
            root = tree.getroot()
            ns = {"ns": root.nsmap.get(None)} if root.nsmap.get(None) else {}

            groups_map = {}

            def parse_groups(groups_element, parent=None):
                for group_elem in groups_element.xpath("ns:Группа" if ns else "Группа", namespaces=ns):
                    g_id = group_elem.findtext("ns:Ид" if ns else "Ид", namespaces=ns)
                    name = group_elem.findtext("ns:Наименование" if ns else "Наименование", namespaces=ns)

                    category = Category.query.filter_by(external_id=g_id).first()
                    if not category:
                        category = Category(external_id=g_id, name=name, slug=slugify(name))
                        db.session.add(category)
                        db.session.flush()

                    category.parent_id = parent.id if parent else None
                    groups_map[g_id] = category

                    subgroups = group_elem.xpath("ns:Группы" if ns else "Группы", namespaces=ns)
                    if subgroups:
                        parse_groups(subgroups[0], parent=category)

            groups_root = root.xpath("//ns:Классификатор/ns:Группы" if ns else "//Классификатор/Группы", namespaces=ns)
            if groups_root:
                parse_groups(groups_root[0])
            db.session.commit()
            prices_map = {}
            offers = root.xpath("//ns:Предложение" if ns else "//Предложение", namespaces=ns)
            for offer in offers:
                p_id = (offer.findtext("ns:Ид" if ns else "Ид", namespaces=ns) or "").split('#')[0]
                if p_id:
                    price_node = offer.xpath(".//ns:ЦенаЗаЕдиницу" if ns else ".//ЦенаЗаЕдиницу", namespaces=ns)
                    price = float(price_node[0].text.replace(',', '.')) if price_node and price_node[0].text else 0.0
                    qty_node = offer.find("ns:Количество" if ns else "Количество", namespaces=ns)
                    in_stock = float(
                        qty_node.text.replace(',', '.')) > 0 if qty_node is not None and qty_node.text else False
                    prices_map[p_id] = (price, in_stock)

            products = root.xpath("//ns:Товар" if ns else "//Товар", namespaces=ns)
            for p_elem in products:
                p_id = (p_elem.findtext("ns:Ид" if ns else "Ид", namespaces=ns) or "").split('#')[0]
                name = (p_elem.findtext("ns:Наименование" if ns else "Наименование", namespaces=ns) or "").strip()
                desc = (p_elem.findtext("ns:Описание" if ns else "Описание", namespaces=ns) or "").strip()

                cat_id_xml = p_elem.xpath("ns:Группы/ns:Ид" if ns else "Группы/Ид", namespaces=ns)
                category_obj = groups_map.get(cat_id_xml[0].text) if cat_id_xml else None

                price, in_stock = prices_map.get(p_id, (0.0, False))

                if price > 1:
                    product = Product.query.filter_by(name=name).first()
                    if not product:
                        product = Product(name=name)
                        db.session.add(product)

                    product.price = price
                    product.in_stock = in_stock
                    product.description = desc
                    if category_obj:
                        product.category_id = category_obj.id
                        product.category = category_obj.name

            db.session.commit()
            print(">>> Імпорт завершено успішно")
        except Exception as e:
            db.session.rollback()
            print(f">>> Помилка імпорту: {e}")
        finally:
            if os.path.exists(tmp_path): os.remove(tmp_path)

@api_bp.route('/bas_import', methods=['POST'])
@csrf.exempt
@require_api_key
def bas_import():
    if 'file' not in request.files: return "failure\nNo file", 400
    file = request.files['file']
    fd, tmp_path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    file.save(tmp_path)
    app_instance = current_app._get_current_object()
    threading.Thread(target=process_bas_xml_background, args=(tmp_path, app_instance)).start()
    return "success\nImport started"

@api_bp.route('/search_suggestions')
def search_suggestions():
    query = request.args.get('q', '').strip()
    if len(query) < 2: return jsonify({'products': [], 'categories': []})
    prods = Product.query.filter(Product.name.ilike(f'%{query}%'), Product.price > 1).order_by(
        Product.in_stock.desc()).limit(5).all()
    cats = Category.query.filter(Category.name.ilike(f'%{query}%')).limit(3).all()
    return jsonify({
        'products': [{'name': p.name, 'url': url_for('main.product_detail', product_id=p.id), 'category': p.category,
                      'image': p.image or '/static/img/no_image.png'} for p in prods],
        'categories': [{'name': c.name, 'url': url_for('main.catalog', category_slug=c.slug)} for c in cats]
    })

@api_bp.route('/np/cities')
def find_np_cities():
    q, api_key = request.args.get('q', ''), os.getenv('NOVA_POSHTA_API_KEY')
    if len(q) < 2 or not api_key: return jsonify([])
    try:
        r = requests.post("https://api.novaposhta.ua/v2.0/json/",
                          json={"apiKey": api_key, "modelName": "Address", "calledMethod": "searchSettlements",
                                "methodProperties": {"CityName": q, "Limit": "20"}}, timeout=5)
        return jsonify([{'ref': c['Ref'], 'name': c['Present']} for c in r.json()['data'][0]['Addresses']])
    except:
        return jsonify([])

@api_bp.route('/np/warehouses')
def get_np_warehouses():
    city_ref, api_key = request.args.get('city_ref'), os.getenv('NOVA_POSHTA_API_KEY')
    if not city_ref or not api_key: return jsonify([])
    try:
        r = requests.post("https://api.novaposhta.ua/v2.0/json/",
                          json={"apiKey": api_key, "modelName": "Address", "calledMethod": "getWarehouses",
                                "methodProperties": {"SettlementRef": city_ref}}, timeout=5)
        return jsonify([w['Description'] for w in r.json()['data']])
    except:
        return jsonify([])
