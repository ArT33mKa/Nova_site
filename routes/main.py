import math
from datetime import datetime, timezone, timedelta
from collections import Counter

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from flask_login import current_user
from sqlalchemy import func, case, or_ as db_or

from extensions import db
from models import Product, Category, CategoryView, OrderItem, Review
from utils import normalize_text, calculate_similarity, FakePagination, shop_info

main_bp = Blueprint('main', __name__)


def get_category_hierarchy():
    all_categories = Category.query.all()
    counts = db.session.query(Product.category_id, func.count(Product.id)).filter(Product.price > 1).group_by(
        Product.category_id).all()
    counts_dict = {cat_id: count for cat_id, count in counts if cat_id}

    def get_total_count(cat, cat_map):
        total = counts_dict.get(cat.id, 0)
        children = [c for c in all_categories if c.parent_id == cat.id]
        for child in children:
            total += get_total_count(child, cat_map)
        return total

    def build_tree(parent_id=None):
        tree = {}
        level_categories = [c for c in all_categories if c.parent_id == parent_id]
        for cat in level_categories:
            total_count = get_total_count(cat, all_categories)
            if total_count > 0:
                tree[cat.name] = {
                    'slug': cat.slug,
                    'count': total_count,
                    'subcategories': build_tree(cat.id)
                }
        return tree

    return build_tree(None)


@main_bp.route("/")
def index():
    hero_slides = [
        {'image': 'hero-bg.jpg', 'title': 'Професійна сантехніка та обладнання',
         'subtitle': 'Якісні товари для вашого дому з гарантією та доставкою'},
        {'image': 'hero-bg2.jpg', 'title': 'Надійні насоси для будь-яких потреб',
         'subtitle': 'Від найкращих виробників'},
        {'image': 'kotly.jpg', 'title': 'Все для систем опалення', 'subtitle': 'Котли, бойлери та комплектуючі'}
    ]

    popular_products_query = db.session.query(
        Product, func.sum(OrderItem.quantity).label('total_sold')
    ).join(OrderItem, OrderItem.product_id == Product.id).filter(Product.price > 1).group_by(Product.id).order_by(
        Product.in_stock.desc(), func.sum(OrderItem.quantity).desc()).limit(8).all()

    products = [p[0] for p in popular_products_query]

    if len(products) < 4:
        products = Product.query.filter(Product.price > 1, Product.in_stock == True).order_by(
            Product.global_score.desc()).limit(8).all()

    main_categories_hierarchy = get_category_hierarchy()

    def get_icon_for_category(name):
        n = name.lower()
        if 'насос' in n or 'станці' in n: return 'fas fa-water'
        if 'бойлер' in n or 'нагрівач' in n: return 'fas fa-temperature-high'
        if 'змішувач' in n or 'кран' in n or 'сифон' in n or 'мик' in n: return 'fas fa-sink'
        if 'вентиляц' in n or 'витяжк' in n or 'домовент' in n: return 'fas fa-fan'
        if 'газ' in n or 'колонк' in n or 'пальник' in n: return 'fas fa-fire'
        if 'опалення' in n or 'радіатор' in n or 'тепла підлога' in n: return 'fas fa-fire-alt'
        if 'труб' in n or 'фітинг' in n: return 'fas fa-project-diagram'
        if 'ванна' in n or 'душ' in n: return 'fas fa-bath'
        if 'кухня' in n: return 'fas fa-utensils'
        if 'автоматика' in n or 'електрика' in n: return 'fas fa-microchip'
        if 'інструмент' in n: return 'fas fa-tools'
        if 'полив' in n: return 'fas fa-cloud-rain'
        return 'fas fa-box-open'

    dynamic_categories = []
    for cat_name in sorted(main_categories_hierarchy.keys()):
        cat_data = main_categories_hierarchy.get(cat_name)
        dynamic_categories.append({
            'name': cat_name,
            'icon': get_icon_for_category(cat_name),
            'slug': cat_data['slug'] if cat_data else ''
        })

    return render_template("shop/index.html", products=products, hero_slides=hero_slides,
                           main_categories=dynamic_categories)
@main_bp.route('/catalog/', defaults={'category_slug': None})
@main_bp.route('/catalog/<path:category_slug>/')
def catalog(category_slug):
    page = request.args.get('page', 1, type=int)
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    search_query = request.args.get('search', '').strip()
    sort_option = request.args.get('sort', 'new')

    query = Product.query.filter(Product.price > 1)

    current_category = None
    if category_slug:
        target_slug = category_slug.strip('/').split('/')[-1]
        category = Category.query.filter_by(slug=target_slug).first()
        if category:
            current_category = category
            cat_ids = [category.id] + [child.id for child in category.children]
            query = query.filter(Product.category_id.in_(cat_ids))

            try:
                cv = CategoryView.query.filter_by(name=category.name).first()
                if not cv:
                    cv = CategoryView(name=category.name)
                    db.session.add(cv)
                cv.views += 1
                db.session.commit()
            except:
                db.session.rollback()

    user_interest = request.cookies.get('user_top_interest')
    order_clauses = [Product.in_stock.desc()]

    if sort_option == 'price_asc':
        order_clauses.append(Product.price.asc())
    elif sort_option == 'price_desc':
        order_clauses.append(Product.price.desc())
    elif sort_option == 'alpha':
        order_clauses.append(Product.name.asc())
    else:
        if user_interest:
            personalized_score = case((Category.slug == user_interest, Product.global_score + 1000), else_=Product.global_score)
            query = query.outerjoin(Category, Product.category_id == Category.id)
            order_clauses.append(personalized_score.desc())
        else:
            order_clauses.append(Product.global_score.desc())

    order_clauses.append(Product.id.desc())

    if min_price: query = query.filter(Product.price >= min_price)
    if max_price: query = query.filter(Product.price <= max_price)
    if request.args.get('in_stock'): query = query.filter(Product.in_stock == True)

    if search_query:
        strict_query = query.filter(db_or(
            Product.name.ilike(f'%{search_query}%'),
            Product.description.ilike(f'%{search_query}%')
        ))

        if strict_query.count() > 0:
            products_paginated = strict_query.order_by(*order_clauses).paginate(page=page, per_page=48)
        else:
            all_prods = query.all()
            scored = []
            for p in all_prods:
                score = calculate_similarity(search_query, p.name)
                if score > 0.25: scored.append((p, score))
            scored.sort(key=lambda x: x[1], reverse=True)
            items = [x[0] for x in scored]
            products_paginated = FakePagination(items, page, 48, len(items))
    else:
        products_paginated = query.order_by(*order_clauses).paginate(page=page, per_page=48)

    return render_template('shop/catalog.html',
                           products=products_paginated,
                           hierarchy=get_category_hierarchy(),
                           current_category=current_category.name if current_category else None,
                           category_slug=category_slug,
                           search_query=search_query)

@main_bp.route("/product/<int:product_id>")
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)

    view_key = f'viewed_{product_id}'
    if view_key not in session:
        product.views_count = (product.views_count or 0) + 1
        product.update_global_score()
        db.session.commit()
        session[view_key] = True

    similar = Product.query.filter(Product.category_id == product.category_id, Product.id != product.id) \
        .order_by(Product.in_stock.desc(), Product.global_score.desc()).limit(8).all()

    return render_template("shop/product_detail.html", product=product, similar_products=similar)

def get_reviews_data(product_id):
    product = Product.query.get_or_404(product_id)
    all_reviews_and_questions = product.reviews.order_by(Review.timestamp.desc()).all()

    reviews_only = [r for r in all_reviews_and_questions if r.review_type == 'review' and r.parent_id is None]
    questions_only = [q for q in all_reviews_and_questions if q.review_type == 'question' and q.parent_id is None]
    reviews_with_rating = [r for r in reviews_only if r.rating > 0]
    rating_counts = Counter([r.rating for r in reviews_with_rating])

    return {
        'product': product,
        'reviews': reviews_only,
        'questions': questions_only,
        'review_only_count': len(reviews_only),
        'rating_breakdown': {star: rating_counts.get(star, 0) for star in range(5, 0, -1)},
        'total_reviews_with_rating': len(reviews_with_rating)
    }

@main_bp.route("/product/<int:product_id>/reviews")
def product_reviews(product_id):
    return render_template("shop/reviews.html", **get_reviews_data(product_id), active_tab='reviews')

@main_bp.route("/product/<int:product_id>/questions")
def product_questions(product_id):
    return render_template("shop/questions.html", **get_reviews_data(product_id), active_tab='questions')

@main_bp.route('/product/<int:product_id>/add_review', methods=['POST'])
def add_review(product_id):
    product = Product.query.get_or_404(product_id)
    form = request.form

    if current_user.is_authenticated:
        recent_count = Review.query.filter(
            Review.user_id == current_user.id,
            Review.timestamp >= datetime.now(timezone.utc) - timedelta(hours=1)
        ).count()
        if recent_count >= 5:
            flash('Ви надсилаєте повідомлення занадто часто. Спробуйте пізніше.', 'warning')
            return redirect(request.referrer)

    new_review = Review(
        product_id=product_id,
        text=form.get('text'),
        author_name=current_user.first_name if current_user.is_authenticated else form.get('author_name', 'Анонім'),
        author_email=current_user.email if current_user.is_authenticated else form.get('author_email'),
        review_type=form.get('review_type', 'review'),
        parent_id=form.get('parent_id') if form.get('parent_id') else None,
        rating=int(form.get('rating', 0)) if form.get('review_type') == 'review' else 0,
        user_id=current_user.id if current_user.is_authenticated else None
    )

    db.session.add(new_review)

    if new_review.review_type == 'review' and not new_review.parent_id:
        db.session.flush()
        result = db.session.query(func.avg(Review.rating), func.count(Review.id)).filter(
            Review.product_id == product_id, Review.rating > 0, Review.review_type == 'review').one()
        product.rating = float(result[0] or 0)
        product.reviews_count = int(result[1] or 0)

    db.session.commit()
    flash('Ваш відгук додано!', 'success')
    return redirect(request.referrer or url_for('main.product_detail', product_id=product_id))