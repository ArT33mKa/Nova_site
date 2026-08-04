# -*- coding: utf-8 -*-
"""
Обмін з 1С/BAF через протокол CommerceML 2 («Обмін з сайтом»).
BAF за розкладом вивантажує товари (назви, ціни, наявність, категорії, фото)
на цей ендпойнт, а сайт оновлює каталог, звіряючи товари за кодом 1С (Ід -> external_id).

Налаштування в .env:
    EXCHANGE_LOGIN=...          логін для вузла обміну в BAF
    EXCHANGE_PASSWORD=...       пароль для вузла обміну в BAF
    EXCHANGE_PRICE_TYPE_ID=...  (необов'язково) Ід типу ціни, який брати на сайт
"""
import os
import shutil
import hashlib
import zipfile
import xml.etree.ElementTree as ET

import base64
import io
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import text
from flask import Blueprint, request, Response, current_app, jsonify
from flask_login import current_user

from extensions import db
from models import Product, Category
from utils import slugify, upload_product_image, cloudinary_upload_bytes, _ensure_cloudinary

exchange_bp = Blueprint('exchange', __name__)

EXCHANGE_LOGIN = os.getenv('EXCHANGE_LOGIN', 'baf')
EXCHANGE_PASSWORD = os.getenv('EXCHANGE_PASSWORD', 'baf')
EXCHANGE_PRICE_TYPE_ID = os.getenv('EXCHANGE_PRICE_TYPE_ID')
COOKIE_NAME = 'nova_1c'
TOKEN = hashlib.md5((EXCHANGE_LOGIN + ':' + EXCHANGE_PASSWORD).encode('utf-8')).hexdigest()
FILE_LIMIT = 100 * 1024 * 1024  # 100 МБ — одним шматком, без розбиття


# ---------- допоміжні ----------

def _root_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _tmp_dir():
    return os.path.join(_root_dir(), 'instance', '1c_exchange')


def _txt(*lines):
    body = "\n".join(str(x) for x in lines)
    return Response(body, mimetype='text/plain; charset=utf-8')


def _authed():
    a = request.authorization
    if a and a.username == EXCHANGE_LOGIN and a.password == EXCHANGE_PASSWORD:
        return True
    return request.cookies.get(COOKIE_NAME) == TOKEN


def _local(tag):
    return tag.split('}', 1)[-1] if isinstance(tag, str) else tag


def _find(el, name):
    if el is None:
        return None
    for c in list(el):
        if _local(c.tag) == name:
            return c
    return None


def _findall(el, name):
    if el is None:
        return []
    return [c for c in list(el) if _local(c.tag) == name]


def _text(el, name):
    c = _find(el, name)
    if c is not None and c.text:
        return c.text.strip()
    return None


# ---------- ендпойнт ----------

@exchange_bp.route('/1c_exchange', methods=['GET', 'POST'])
def exchange():
    typ = request.args.get('type', '')
    mode = request.args.get('mode', '')
    current_app.logger.info(
        '1C exchange hit: method=%s type=%s mode=%s filename=%s has_auth=%s',
        request.method, typ, mode, request.args.get('filename', ''), bool(request.authorization)
    )

    # 1) Авторизація
    if mode == 'checkauth':
        a = request.authorization
        if a and a.username == EXCHANGE_LOGIN and a.password == EXCHANGE_PASSWORD:
            resp = _txt('success', COOKIE_NAME, TOKEN)
            resp.set_cookie(COOKIE_NAME, TOKEN)
            return resp
        return _txt('failure', 'Hевiрний логiн або пароль обмiну')

    if not _authed():
        return _txt('failure', 'Потрiбна авторизацiя')

    # 2) Ініціалізація сесії обміну
    if mode == 'init':
        d = _tmp_dir()
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d, exist_ok=True)
        return _txt('zip=no', 'file_limit=%d' % FILE_LIMIT)

    # 3) Прийом файлів (XML + фото)
    if mode == 'file':
        filename = request.args.get('filename', '')
        if not filename:
            return _txt('failure', 'He вказано iмя файлу')
        rel = filename.replace('\\', '/').lstrip('/')
        if '..' in rel.split('/'):
            return _txt('failure', 'Heдопустиме iмя файлу')
        # Зображення НЕ пишемо на диск fly.io — одразу у Cloudinary (звязок ім’я->URL у спільній БД)
        if _is_image_name(rel):
            _store_exchange_image(rel, request.get_data())
            return _txt('success')
        target = os.path.join(_tmp_dir(), *rel.split('/'))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, 'ab') as f:
            f.write(request.get_data())
        if rel.lower().endswith('.zip'):
            try:
                with zipfile.ZipFile(target) as z:
                    z.extractall(_tmp_dir())
            except Exception as e:
                current_app.logger.warning('1C zip extract failed: %s', e)
        return _txt('success')

    # 4) Імпорт завантаженого файлу в БД
    if mode == 'import':
        filename = request.args.get('filename', '')
        rel = filename.replace('\\', '/').lstrip('/')
        path = os.path.join(_tmp_dir(), *rel.split('/')) if rel else None
        if not path or not os.path.isfile(path):
            return _txt('failure', 'Файл не знайдено: %s' % filename)
        try:
            process_commerceml(path, _tmp_dir())
            return _txt('success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception('Помилка iмпорту 1C')
            return _txt('failure', 'Помилка iмпорту: %s' % e)

    # 5) Вивантаження замовлень на 1С (type=sale) — поки порожньо
    if typ == 'sale' and mode == 'query':
        return _txt('<?xml version="1.0" encoding="UTF-8"?>',
                    '<КоммерческаяИнформация ВерсияСхемы="2.05"></КоммерческаяИнформация>')

    # init/success/complete та інше — підтверджуємо
    return _txt('success')


# ---------- діагностика ----------

@exchange_bp.route('/1c_exchange/diag')
def exchange_diag():
    """Швидкий звіт про стан бази товарів. Доступ: адмін або ?key=<EXCHANGE_PASSWORD>."""
    key = request.args.get('key', '')
    is_admin = getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'is_admin', False)
    if not (is_admin or (key and key == EXCHANGE_PASSWORD)):
        return _txt('failure', 'forbidden')
    total = Product.query.count()
    priced = Product.query.filter(Product.price > 1).count()
    in_stock = Product.query.filter(Product.in_stock == True).count()
    with_img = Product.query.filter(Product.image != None, Product.image != '').count()
    cats = Category.query.count()
    lines = [
        'EXCHANGE_LOGIN_set=%s' % bool(os.getenv('EXCHANGE_LOGIN')),
        'EXCHANGE_PASSWORD_set=%s' % bool(os.getenv('EXCHANGE_PASSWORD')),
        'EXCHANGE_PRICE_TYPE_ID=%s' % (EXCHANGE_PRICE_TYPE_ID or '(не задано)'),
        'total_products=%d' % total,
        'price_gt_1_visible=%d' % priced,
        'price_le_1_hidden=%d' % (total - priced),
        'in_stock=%d' % in_stock,
        'with_image=%d' % with_img,
        'categories=%d' % cats,
        '--- last 15 products ---',
    ]
    for p in Product.query.order_by(Product.id.desc()).limit(15).all():
        lines.append('#%s | %s | price=%s | stock=%s | img=%s | ext=%s' % (
            p.id, (p.name or '')[:40], p.price, p.in_stock, bool(p.image), p.external_id))
    return _txt(*lines)


@exchange_bp.route('/1c_exchange/lastxml')
def exchange_lastxml():
    # Останній отриманий XML (фрагмент) для діагностики. Доступ: ?key=<EXCHANGE_PASSWORD>.
    key = request.args.get('key', '')
    is_admin = getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'is_admin', False)
    if not (is_admin or (key and key == EXCHANGE_PASSWORD)):
        return _txt('failure', 'forbidden')
    try:
        db.session.execute(text(
            'CREATE TABLE IF NOT EXISTS exchange_debug (id INTEGER PRIMARY KEY, content TEXT)'))
        row = db.session.execute(text('SELECT content FROM exchange_debug WHERE id=1')).fetchone()
        return _txt(row[0] if row else '(порожньо)')
    except Exception as e:
        return _txt('error: %s' % e)


@exchange_bp.route('/1c_exchange/cleanup', methods=['GET', 'POST'])
def exchange_cleanup():
    """Видаляє тестові/демо-товари (ті, що НЕ мають external_id з 1С).
    Доступ: адмін або ?key=<EXCHANGE_PASSWORD>.
    Без confirm=1 — лише показує, що буде видалено (нічого не чіпає).
    З &confirm=1 — видаляє товари без external_id разом із залежними записами.
    """
    from models import Review, ReviewVote, CartItem, Favorite, OrderItem
    key = request.args.get('key', '')
    is_admin = getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'is_admin', False)
    if not (is_admin or (key and key == EXCHANGE_PASSWORD)):
        return _txt('failure', 'forbidden')

    wipe_all = request.args.get('all', '') in ('1', 'true', 'yes')
    if wipe_all:
        victims = Product.query.all()
    else:
        victims = Product.query.filter((Product.external_id == None) | (Product.external_id == '')).all()
    confirm = request.args.get('confirm', '') in ('1', 'true', 'yes')

    if not confirm:
        lines = ['DRY RUN — нічого не видалено. Додай &confirm=1 щоб видалити.',
                 ('режим: ПОВНЕ ОЧИЩЕННЯ — усі товари + категорії' if wipe_all
                  else 'режим: лише тестові товари (без 1С-кода). Для повного очищення додай &all=1'),
                 'товарів буде видалено: %d' % len(victims),
                 'категорій буде видалено: %d' % (Category.query.count() if wipe_all else 0),
                 '--- перші 30 ---']
        for p in victims[:30]:
            lines.append('#%s | %s | price=%s | ext=%s' % (p.id, (p.name or '')[:40], p.price, p.external_id))
        return _txt(*lines)

    ids = [p.id for p in victims]
    deleted = 0
    if ids:
        review_ids = [r.id for r in Review.query.filter(Review.product_id.in_(ids)).all()]
        if review_ids:
            ReviewVote.query.filter(ReviewVote.review_id.in_(review_ids)).delete(synchronize_session=False)
        Review.query.filter(Review.product_id.in_(ids)).delete(synchronize_session=False)
        CartItem.query.filter(CartItem.product_id.in_(ids)).delete(synchronize_session=False)
        Favorite.query.filter(Favorite.product_id.in_(ids)).delete(synchronize_session=False)
        OrderItem.query.filter(OrderItem.product_id.in_(ids)).delete(synchronize_session=False)
        deleted = Product.query.filter(Product.id.in_(ids)).delete(synchronize_session=False)
    cats_deleted = 0
    if wipe_all:
        try:
            from models import CategoryView
            CategoryView.query.delete(synchronize_session=False)
        except Exception:
            pass
        cats_deleted = Category.query.delete(synchronize_session=False)
    db.session.commit()
    current_app.logger.info('1C cleanup: deleted %d products (wipe_all=%s), categories=%d',
                            deleted, wipe_all, cats_deleted)
    return _txt('OK', 'видалено товарів: %d' % deleted, 'видалено категорій: %d' % cats_deleted)


# ---------- зображення: завжди прямо у Cloudinary, без диска fly.io ----------

IMAGE_EXTS = ('.jpg', '.jpeg', '.jfif', '.png', '.gif', '.webp', '.bmp')


def _is_image_name(name):
    return os.path.splitext(name)[1].lower() in IMAGE_EXTS


def _ensure_image_map_table():
    db.session.execute(text(
        'CREATE TABLE IF NOT EXISTS exchange_image_map (filename TEXT PRIMARY KEY, url TEXT)'))


def _store_exchange_image(rel, raw):
    """Вантажить байти зображення НАПРЯМУ в Cloudinary і зберігає зв'язок filename -> URL
    у спільній БД. Нічого не пише на диск fly.io."""
    if not raw:
        return None
    public_id = 'baf_' + hashlib.md5(rel.encode('utf-8')).hexdigest()
    url = cloudinary_upload_bytes(raw, public_id)
    if not url:
        current_app.logger.warning('1C image: НЕ вдалося вивантажити у Cloudinary: %s', rel)
        return None
    try:
        _ensure_image_map_table()
        db.session.execute(text('DELETE FROM exchange_image_map WHERE filename = :f'), {'f': rel})
        db.session.execute(text('INSERT INTO exchange_image_map (filename, url) VALUES (:f, :u)'),
                           {'f': rel, 'u': url})
        db.session.commit()
    except Exception:
        db.session.rollback()
    return url


def _lookup_exchange_image(rel):
    try:
        _ensure_image_map_table()
        row = db.session.execute(
            text('SELECT url FROM exchange_image_map WHERE filename = :f'), {'f': rel}).fetchone()
        return row[0] if row else None
    except Exception:
        db.session.rollback()
        return None


# ---------- прямий JSON-пуш від кастомної обробки 1С ----------

def _save_image_b64(b64, ext, ext_id):
    """Декодує base64-зображення і вантажить ЛИШЕ у Cloudinary (без локального фолбеку на сайт).
    Повертає URL з Cloudinary або None, якщо завантаження не вдалося (пише результат у логи)."""
    try:
        raw = base64.b64decode(b64)
    except Exception:
        current_app.logger.warning('1C image: помилка декодування base64 для %s', ext_id)
        return None
    if not raw:
        return None
    url = cloudinary_upload_bytes(raw, ext_id)
    if url:
        current_app.logger.info('1C image: вивантажено у Cloudinary — %s -> %s', ext_id, url)
        return url
    current_app.logger.warning('1C image: НЕ вдалося вивантажити у Cloudinary для %s', ext_id)
    return None


def _to_float(val):
    if val is None:
        return None
    try:
        return float(str(val).replace('\xa0', '').replace(' ', '').replace(',', '.'))
    except (ValueError, TypeError):
        return None


@exchange_bp.route('/1c_exchange/push', methods=['POST'])
def exchange_push():
    """Приймає JSON-пакет від кастомної обробки 1С (групи + товари).
    Авторизація: HTTP Basic (логін/пароль обміну) або ?key=<EXCHANGE_PASSWORD>.

    Формат тіла:
    {
      "categories": [{"id": "<Ід групи>", "name": "...", "parent_id": "<Ід батька|порожньо>"}],
      "products": [{
          "id": "<Ід номенклатури>", "name": "...", "description": "...",
          "group_id": "<Ід групи>", "price": 1234.5, "stock": 1,
          "image_b64": "<base64|необов'язково>", "image_ext": ".jpg"
      }]
    }
    """
    key = request.args.get('key', '')
    if not (_authed() or (key and key == EXCHANGE_PASSWORD)):
        return jsonify({'status': 'error', 'error': 'forbidden'}), 403

    data = request.get_json(force=True, silent=True) or {}
    cats = data.get('categories') or []
    prods = data.get('products') or []
    current_app.logger.info('1C push start: categories=%d products=%d', len(cats), len(prods))

    # 1) Категорії: спершу створюємо/оновлюємо, тоді проставляємо батьків
    cmap = {}
    for c in cats:
        ext = str(c.get('id') or '').strip()
        if not ext:
            continue
        name = (c.get('name') or 'Без назви')[:100]
        cat = Category.query.filter_by(external_id=ext).first()
        if cat is None:
            cat = Category(external_id=ext)
            db.session.add(cat)
        cat.name = name
        if not cat.slug:
            cat.slug = _unique_slug(name)
        db.session.flush()
        cmap[ext] = cat
    for c in cats:
        ext = str(c.get('id') or '').strip()
        pid = str(c.get('parent_id') or '').strip()
        if ext in cmap and pid and pid in cmap:
            cmap[ext].parent_id = cmap[pid].id
    db.session.flush()

    created = updated = imgs = 0
    for it in prods:
        ext = str(it.get('id') or '').strip()
        if not ext:
            continue
        p = Product.query.filter_by(external_id=ext).first()
        if p is None:
            p = Product(external_id=ext, price=0.0)
            db.session.add(p)
            created += 1
        else:
            updated += 1
        if it.get('name'):
            p.name = str(it['name'])[:100]
        if it.get('description') is not None:
            p.description = str(it['description'])
        gid = str(it.get('group_id') or '').strip()
        if gid:
            c = Category.query.filter_by(external_id=gid).first()
            if c is not None:
                p.category_id = c.id
                p.category = c.name
        price = _to_float(it.get('price'))
        if price is not None:
            p.price = price
        if it.get('stock') is not None:
            qty = _to_float(it.get('stock'))
            p.in_stock = (qty > 0) if qty is not None else bool(it.get('stock'))
        b64 = it.get('image_b64')
        if b64:
            fn = _save_image_b64(b64, it.get('image_ext'), ext)
            if fn:
                p.image = fn
                imgs += 1
        p.update_global_score()

    db.session.commit()
    current_app.logger.info(
        '1C push done: received=%d created=%d updated=%d images=%d categories=%d',
        len(prods), created, updated, imgs, len(cats))
    return jsonify({'status': 'ok', 'received': len(prods), 'created': created,
                    'updated': updated, 'images': imgs, 'categories': len(cats)})


# ---------- оптимізований двофазний обмін (sync + push_images) ----------

def _unique_slug_cached(name, used):
    """Slug без запиту в БД у циклі — перевіряємо по множині зайнятих."""
    base = slugify(name) or 'cat'
    s, i = base, 1
    while s in used:
        i += 1
        s = "%s-%d" % (base, i)
    used.add(s)
    return s


def _upsert_categories(cats):
    """Створює/оновлює категорії та проставляє батьків (без N+1). Повертає {external_id: Category}."""
    ext_ids = [str(c.get('id') or '').strip() for c in cats if str(c.get('id') or '').strip()]
    existing = {}
    if ext_ids:
        for cat in Category.query.filter(Category.external_id.in_(ext_ids)).all():
            existing[cat.external_id] = cat
    used_slugs = {row[0] for row in db.session.query(Category.slug).all() if row[0]}

    cmap = {}
    for c in cats:
        ext = str(c.get('id') or '').strip()
        if not ext:
            continue
        name = (c.get('name') or 'Без назви')[:100]
        cat = existing.get(ext)
        if cat is None:
            cat = Category(external_id=ext)
            db.session.add(cat)
            existing[ext] = cat
        cat.name = name
        if not cat.slug:
            cat.slug = _unique_slug_cached(name, used_slugs)
        cmap[ext] = cat
    db.session.flush()
    for c in cats:
        ext = str(c.get('id') or '').strip()
        pid = str(c.get('parent_id') or '').strip()
        if ext in cmap and pid and pid in cmap:
            cmap[ext].parent_id = cmap[pid].id
    db.session.flush()
    return cmap


@exchange_bp.route('/1c_exchange/sync', methods=['POST'])
def exchange_sync():
    """ФАЗА 1: приймає дані товарів (без фото) + хеш кожного фото.
    Оновлює каталог і повертає список external_id, чиї фото треба надіслати
    (нові або змінені). Фото в цей ендпойнт НЕ передаються.

    Тіло:
    {
      "categories": [{"id","name","parent_id"}],
      "products": [{"id","name","description","group_id","price","stock","image_hash"}]
    }
    Відповідь: {"status":"ok","need_images":[...],"created":N,"updated":M,"categories":K}

    ОПТИМІЗОВАНО 2026-08-04: підтримка великих пакетів (без обмеження на кількість товарів)
    """
    key = request.args.get('key', '')
    if not (_authed() or (key and key == EXCHANGE_PASSWORD)):
        current_app.logger.warning('1C sync: доступ заборонено (неправильна авторизація)')
        return jsonify({'status': 'error', 'error': 'forbidden'}), 403

    try:
        data = request.get_json(force=True, silent=True) or {}
    except Exception as e:
        current_app.logger.error('1C sync: помилка парсингу JSON: %s', e, exc_info=True)
        return jsonify({'status': 'error', 'error': 'invalid_json', 'details': str(e)}), 400

    cats = data.get('categories') or []
    prods = data.get('products') or []
    current_app.logger.info('1C sync START: отримано категорій=%d, товарів=%d (розмір запиту: %d байт)',
                           len(cats), len(prods), request.content_length or 0)

    current_app.logger.info('1C sync: обробка категорій...')
    _upsert_categories(cats)
    all_cats = {c.external_id: c for c in Category.query.filter(Category.external_id.isnot(None)).all()}
    current_app.logger.info('1C sync: категорій в БД: %d', len(all_cats))

    ext_ids = [str(it.get('id') or '').strip() for it in prods if str(it.get('id') or '').strip()]
    existing = {}
    if ext_ids:
        for p in Product.query.filter(Product.external_id.in_(ext_ids)).all():
            existing[p.external_id] = p
    current_app.logger.info('1C sync: знайдено існуючих товарів: %d з %d', len(existing), len(ext_ids))

    need_images = []
    created = updated = 0
    for it in prods:
        ext = str(it.get('id') or '').strip()
        if not ext:
            continue
        p = existing.get(ext)
        if p is None:
            p = Product(external_id=ext, price=0.0)
            db.session.add(p)
            existing[ext] = p
            created += 1
        else:
            updated += 1
        if it.get('name'):
            p.name = str(it['name'])[:100]
        if it.get('description') is not None:
            p.description = str(it['description'])
        gid = str(it.get('group_id') or '').strip()
        if gid and gid in all_cats:
            p.category_id = all_cats[gid].id
            p.category = all_cats[gid].name
        price = _to_float(it.get('price'))
        if price is not None:
            p.price = price
        if it.get('stock') is not None:
            qty = _to_float(it.get('stock'))
            p.in_stock = (qty > 0) if qty is not None else bool(it.get('stock'))
        ih = str(it.get('image_hash') or '').strip()
        image_missing_or_invalid = (not p.image) or (not str(p.image).startswith('http'))
        if ih and (image_missing_or_invalid or p.image_hash != ih):
            need_images.append(ext)
            current_app.logger.debug('1C sync: товар %s потребує фото (hash=%s, current_image=%s)',
                                    ext, ih[:20], p.image[:50] if p.image else 'немає')
        p.update_global_score()

    db.session.commit()
    current_app.logger.info(
        '1C sync ЗАВЕРШЕНО: отримано=%d, створено=%d, оновлено=%d, потрібно фото=%d, категорій=%d',
        len(prods), created, updated, len(need_images), len(cats))

    if need_images:
        current_app.logger.info('1C sync: список товарів для фото (перші 20): %s', need_images[:20])

    return jsonify({'status': 'ok', 'need_images': need_images, 'created': created,
                    'updated': updated, 'categories': len(cats)})


@exchange_bp.route('/1c_exchange/push_images', methods=['POST'])
def exchange_push_images():
    """ФАЗА 2: приймає base64 ЛИШЕ для товарів, які запросив /sync.
    Тіло: {"images": [{"id","image_b64","image_ext","image_hash"}]}
    Кожне фото вантажиться ЛИШЕ у Cloudinary (жодного локального диска Fly).

    ОПТИМІЗОВАНО 2026-08-04:
    - підтримка великих пакетів (без обмеження на кількість фото)
    - збільшений timeout для завантаження
    - краще логування помилок
    """
    key = request.args.get('key', '')
    if not (_authed() or (key and key == EXCHANGE_PASSWORD)):
        current_app.logger.warning('1C push_images: доступ заборонено (неправильна авторизація)')
        return jsonify({'status': 'error', 'error': 'forbidden'}), 403

    try:
        data = request.get_json(force=True, silent=True) or {}
    except Exception as e:
        current_app.logger.error('1C push_images: помилка парсингу JSON: %s', e, exc_info=True)
        return jsonify({'status': 'error', 'error': 'invalid_json', 'details': str(e)}), 400

    imgs = data.get('images') or []
    current_app.logger.info('1C push_images START: отримано %d фото для завантаження (розмір запиту: %d байт)',
                           len(imgs), request.content_length or 0)

    if not _ensure_cloudinary():
        current_app.logger.error(
            '1C push_images FATAL: Cloudinary НЕ налаштований! '
            'Перевір змінні: CLOUDINARY_CLOUD_NAME=%s, CLOUDINARY_API_KEY=%s, CLOUDINARY_API_SECRET=%s',
            bool(os.getenv("CLOUDINARY_CLOUD_NAME")),
            bool(os.getenv("CLOUDINARY_API_KEY")),
            bool(os.getenv("CLOUDINARY_API_SECRET")))
        return jsonify({'status': 'error', 'error': 'cloudinary_not_configured',
                        'received': len(imgs), 'images': 0}), 500

    current_app.logger.info('1C push_images: Cloudinary налаштований успішно, починаємо завантаження')

    def _work(im):
        ext = str(im.get('id') or '').strip()
        b64 = im.get('image_b64')
        img_hash = str(im.get('image_hash') or '').strip()

        current_app.logger.debug('1C push_images: обробка товару %s (hash=%s)', ext, img_hash[:20] if img_hash else 'немає')

        if not ext:
            current_app.logger.warning('1C push_images: пропущено фото без id товару')
            return {'id': ext, 'ok': False, 'error': 'відсутній id товару'}
        if not b64:
            current_app.logger.warning('1C push_images: товар %s - відсутні дані image_b64', ext)
            return {'id': ext, 'ok': False, 'error': 'відсутній image_b64'}

        try:
            raw = base64.b64decode(b64)
            current_app.logger.debug('1C push_images: товар %s - декодовано %d байт', ext, len(raw))
        except Exception as e:
            current_app.logger.error('1C push_images: товар %s - помилка декодування base64: %s', ext, e)
            return {'id': ext, 'ok': False, 'error': 'помилка декодування base64: %s' % e}

        if not raw:
            current_app.logger.warning('1C push_images: товар %s - порожні дані після декодування', ext)
            return {'id': ext, 'ok': False, 'error': 'порожні дані після декодування base64'}

        try:
            current_app.logger.info('1C push_images: товар %s - завантажую %d байт у Cloudinary...', ext, len(raw))
            url = cloudinary_upload_bytes(raw, ext)
            if url:
                current_app.logger.info('1C push_images: товар %s - УСПІХ! URL: %s', ext, url)
            else:
                current_app.logger.error('1C push_images: товар %s - Cloudinary повернув None (помилка завантаження)', ext)
        except Exception as e:
            current_app.logger.error('1C push_images: товар %s - виняток при завантаженні в Cloudinary: %s', ext, e, exc_info=True)
            return {'id': ext, 'ok': False, 'error': 'виняток Cloudinary: %s' % e}

        if not url:
            return {'id': ext, 'ok': False, 'error': 'Cloudinary не повернув URL (помилка завантаження)'}

        return {'id': ext, 'ok': True, 'url': url, 'hash': img_hash}

    # мережеві завантаження в Cloudinary — паралельно; БД тут НЕ чіпаємо (сесія не потокобезпечна)
    # Збільшено кількість потоків до 20 для швидшого завантаження великих пакетів
    results = []
    if imgs:
        max_workers = min(20, len(imgs))  # не більше 20 потоків, але не більше ніж кількість фото
        current_app.logger.info('1C push_images: запускаю паралельне завантаження (%d потоків для %d фото)...',
                               max_workers, len(imgs))
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                results = list(pool.map(_work, imgs))
            current_app.logger.info('1C push_images: завантаження завершено, обробляю результати')
        except Exception as e:
            current_app.logger.error('1C push_images: критична помилка при паралельному завантаженні: %s',
                                    e, exc_info=True)
            return jsonify({'status': 'error', 'error': 'upload_failed', 'details': str(e)}), 500

    ok_results = [r for r in results if r.get('ok')]
    ext_ids = [r['id'] for r in ok_results]

    current_app.logger.info('1C push_images: успішно завантажено %d з %d фото', len(ok_results), len(imgs))

    existing = {}
    if ext_ids:
        current_app.logger.info('1C push_images: шукаю %d товарів у БД...', len(ext_ids))
        for p in Product.query.filter(Product.external_id.in_(ext_ids)).all():
            existing[p.external_id] = p
        current_app.logger.info('1C push_images: знайдено %d товарів у БД', len(existing))

    done = 0
    for r in ok_results:
        p = existing.get(r['id'])
        if p is None:
            current_app.logger.warning('1C push_images: товар %s не знайдено в БД, фото пропущено (можливо товар ще не створений)', r['id'])
            continue
        old_image = p.image
        p.image = r['url']
        if r['hash']:
            p.image_hash = r['hash']
        p.update_global_score()
        done += 1
        current_app.logger.info('1C push_images: товар %s - оновлено в БД: %s -> %s', r['id'], old_image or '(немає)', r['url'])

    for r in results:
        if not r.get('ok'):
            current_app.logger.error('1C push_images: ПОМИЛКА для товару %s: %s', r.get('id'), r.get('error'))

    try:
        db.session.commit()
        current_app.logger.info('1C push_images: зміни збережено в БД')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error('1C push_images: помилка збереження в БД: %s', e, exc_info=True)
        return jsonify({'status': 'error', 'error': 'database_error', 'details': str(e)}), 500

    failed = len(results) - len(ok_results)

    # Додаємо детальну статистику помилок для діагностики
    error_summary = {}
    for r in results:
        if not r.get('ok'):
            error_msg = r.get('error', 'невідома помилка')
            error_summary[error_msg] = error_summary.get(error_msg, 0) + 1

    current_app.logger.info(
        '1C push_images ЗАВЕРШЕНО: отримано=%d, завантажено в Cloudinary=%d, збережено в БД=%d, помилок=%d',
        len(imgs), len(ok_results), done, failed)

    if error_summary:
        current_app.logger.warning('1C push_images: розподіл помилок: %s', error_summary)

    response = {
        'status': 'ok',
        'received': len(imgs),
        'images': done,
        'failed': failed,
        'cloudinary_uploaded': len(ok_results),
        'db_saved': done
    }

    # Додаємо інформацію про помилки, якщо вони є
    if error_summary:
        response['error_summary'] = error_summary

    return jsonify(response)


# ---------- розбір CommerceML ----------

def _extract_price(ceny):
    price_els = _findall(ceny, 'Цена')
    if not price_els:
        return None
    chosen = None
    if EXCHANGE_PRICE_TYPE_ID:
        for ce in price_els:
            if _text(ce, 'ИдТипаЦены') == EXCHANGE_PRICE_TYPE_ID:
                chosen = ce
                break
    if chosen is None:
        chosen = price_els[0]
    val = _text(chosen, 'ЦенаЗаЕдиницу') or _text(chosen, 'Цена')
    if not val:
        return None
    try:
        return float(val.replace('\xa0', '').replace(' ', '').replace(',', '.'))
    except ValueError:
        return None


def _capture_debug(path, root):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            head = f.read(16000)
        tags = [_local(c.tag) for c in list(root)]
        sample = ''
        cat = None
        for c in list(root):
            if _local(c.tag) == 'Каталог':
                cat = c
        if cat is not None:
            tovary = _find(cat, 'Товары')
            tlist = _findall(tovary, 'Товар')
            if tlist:
                sample = ET.tostring(tlist[0], encoding='unicode')[:8000]
        info = ('FILE=%s\nROOT_TAGS=%s\nHAS_OFFERS_IN_FILE=%s\n--- FIRST TOVAR ---\n%s\n--- FILE HEAD ---\n%s'
                % (os.path.basename(path), tags, ('ПакетПредложений' in tags), sample, head))
        db.session.execute(text(
            'CREATE TABLE IF NOT EXISTS exchange_debug (id INTEGER PRIMARY KEY, content TEXT)'))
        db.session.execute(text('DELETE FROM exchange_debug WHERE id=1'))
        db.session.execute(text('INSERT INTO exchange_debug (id, content) VALUES (1, :c)'), {'c': info})
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


def process_commerceml(path, base_dir):
    tree = ET.parse(path)
    root = tree.getroot()
    _capture_debug(path, root)
    for child in list(root):
        ln = _local(child.tag)
        if ln == 'Классификатор':
            _import_classifier(child)
        elif ln == 'Каталог':
            _import_catalog(child, base_dir)
        elif ln == 'ПакетПредложений':
            _import_offers(child)
    db.session.commit()
    try:
        current_app.logger.info(
            '1C import done [%s]: products=%d, priced_gt_1=%d, in_stock=%d, categories=%d',
            os.path.basename(path),
            Product.query.count(),
            Product.query.filter(Product.price > 1).count(),
            Product.query.filter(Product.in_stock == True).count(),
            Category.query.count(),
        )
    except Exception:
        pass


def _unique_slug(name):
    base = slugify(name) or 'cat'
    s = base
    i = 1
    while Category.query.filter_by(slug=s).first():
        i += 1
        s = "%s-%d" % (base, i)
    return s


def _import_classifier(classifier):
    groups = _find(classifier, 'Группы')
    _walk_groups(groups, None)


def _walk_groups(groups_el, parent_id):
    for g in _findall(groups_el, 'Группа'):
        gid = _text(g, 'Ид')
        if not gid:
            continue
        name = (_text(g, 'Наименование') or 'Без назви')[:100]
        cat = Category.query.filter_by(external_id=gid).first()
        if cat is None:
            cat = Category(external_id=gid)
            db.session.add(cat)
        cat.name = name
        cat.parent_id = parent_id
        if not cat.slug:
            cat.slug = _unique_slug(name)
        db.session.flush()
        _walk_groups(_find(g, 'Группы'), cat.id)


def _import_catalog(catalog, base_dir):
    tovary = _find(catalog, 'Товары')
    for t in _findall(tovary, 'Товар'):
        raw_id = _text(t, 'Ид') or ''
        ext = raw_id.split('#', 1)[0]
        if not ext:
            continue
        p = Product.query.filter_by(external_id=ext).first()
        if p is None:
            p = Product(external_id=ext, price=0.0)
            db.session.add(p)
        p.name = (_text(t, 'Наименование') or 'Товар')[:100]
        desc = _text(t, 'Описание')
        if desc is not None:
            p.description = desc
        groups = _find(t, 'Группы')
        gid = _text(groups, 'Ид') if groups is not None else None
        if gid:
            c = Category.query.filter_by(external_id=gid).first()
            if c is not None:
                p.category_id = c.id
                p.category = c.name
        pics = _findall(t, 'Картинка')
        if pics and pics[0].text:
            fn = _save_image(pics[0].text.strip(), base_dir, ext)
            if fn:
                p.image = fn
        # деякі конфігурації BAF кладуть ціну прямо в Каталог (всередині Товар)
        pr = _extract_price(_find(t, 'Цены'))
        if pr is not None and pr > 0:
            p.price = pr
        p.update_global_score()


def _import_offers(pkg):
    offers = _find(pkg, 'Предложения')
    for o in _findall(offers, 'Предложение'):
        raw_id = _text(o, 'Ид') or ''
        ext = raw_id.split('#', 1)[0]
        if not ext:
            continue
        p = Product.query.filter_by(external_id=ext).first()
        if p is None:
            continue
        ceny = _find(o, 'Цены')
        price_els = _findall(ceny, 'Цена')
        if price_els:
            chosen = None
            if EXCHANGE_PRICE_TYPE_ID:
                for ce in price_els:
                    if _text(ce, 'ИдТипаЦены') == EXCHANGE_PRICE_TYPE_ID:
                        chosen = ce
                        break
            if chosen is None:
                chosen = price_els[0]
            val = _text(chosen, 'ЦенаЗаЕдиницу') or _text(chosen, 'Цена')
            if val:
                try:
                    p.price = float(val.replace('\xa0', '').replace(' ', '').replace(',', '.'))
                except ValueError:
                    pass
        qty = _text(o, 'Количество')
        if qty is None:
            ost = _find(o, 'Остатки')
            o2 = _find(ost, 'Остаток') if ost is not None else None
            if o2 is not None:
                qty = _text(o2, 'Количество')
                if qty is None:
                    sk = _find(o2, 'Склад')
                    qty = _text(sk, 'Количество') if sk is not None else None
        if qty is not None:
            try:
                p.in_stock = float(qty.replace(',', '.')) > 0
            except ValueError:
                pass
        p.update_global_score()


def _save_image(rel, base_dir, ext_id):
    rel = rel.replace('\\', '/').lstrip('/')
    url = _lookup_exchange_image(rel)
    if url:
        return url
    src = os.path.join(base_dir, *rel.split('/'))
    if not os.path.isfile(src):
        current_app.logger.warning('1C image: немає ні в Cloudinary-мапі, ні на диску: %s', rel)
        return None
    _, e = os.path.splitext(rel)
    e = (e or '.jpg').lower()
    safe = ''.join(ch for ch in ext_id if ch.isalnum() or ch in '-_') or 'img'
    # Вантажимо ЛИШЕ у Cloudinary, без локального фолбеку на сайт.
    url = upload_product_image(src, safe)
    if url:
        current_app.logger.info('1C image: вивантажено у Cloudinary — %s -> %s', ext_id, url)
        return url
    current_app.logger.warning('1C image: НЕ вдалося вивантажити у Cloudinary для %s', ext_id)
    return None
