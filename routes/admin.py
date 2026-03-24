from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func
import cloudinary.uploader

from extensions import db
from models import Order, Review, Product, OrderItem

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Доступ до цієї сторінки мають тільки адміністратори.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/orders', methods=['GET', 'POST'])
@login_required
@admin_required
def orders():
    if request.method == 'POST':
        if order := Order.query.get(request.form.get('order_id')):
            order.status = request.form.get('status')
            db.session.commit()
            flash(f"Статус замовлення #{order.id} оновлено.", "success")
        return redirect(url_for('admin.orders', status=request.args.get('status', 'Нове')))

    status_filter = request.args.get('status', 'Нове')
    query = Order.query if status_filter == 'all' else Order.query.filter_by(status=status_filter)

    return render_template('admin/admin_orders.html', orders=query.order_by(Order.timestamp.desc()).paginate(
        page=request.args.get('page', 1, type=int), per_page=15, error_out=False),
                           all_statuses=['Нове', 'Відправлено', 'Виконано', 'Скасовано'], current_status=status_filter)

@admin_bp.route('/reviews')
@login_required
@admin_required
def reviews():
    return render_template('admin/admin_reviews.html', reviews=Review.query.order_by(Review.timestamp.desc()).paginate(
        page=request.args.get('page', 1, type=int), per_page=15, error_out=False))

@admin_bp.route("/edit_product/<int:product_id>", methods=['GET', 'POST'])
@login_required
@admin_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        product.name = request.form['name']
        product.price = float(request.form['price'])
        product.description = request.form['description']
        product.category = request.form['category']
        product.in_stock = 'in_stock' in request.form

        if 'image' in request.files and request.files['image'].filename != '':
            try:
                product.image = cloudinary.uploader.upload(request.files['image'], folder="products/products")['secure_url']
            except Exception as e:
                print(f"Помилка завантаження Cloudinary: {e}")

        db.session.commit()
        flash(f"Товар '{product.name}' оновлено!", "success")
        return redirect(url_for('main.catalog'))

    return render_template("admin/edit_product.html", product=product,
                           image_to_display=product.image.split('/')[-1] if product.image else '')

@admin_bp.route("/delete_review/<int:review_id>", methods=["POST"])
@login_required
@admin_required
def delete_review(review_id):
    review = Review.query.get_or_404(review_id)
    product = review.product
    db.session.delete(review)
    db.session.flush()

    result = db.session.query(func.avg(Review.rating), func.count(Review.id)).filter(
        Review.product_id == product.id, Review.rating > 0, Review.review_type == 'review').one()
    product.rating, product.reviews_count = float(result[0] or 0), int(result[1] or 0)
    db.session.commit()

    flash("Запис видалено, рейтинг товару оновлено.", "success")
    return redirect(request.referrer or url_for('admin.reviews'))

@admin_bp.route("/delete_product/<int:product_id>", methods=["POST"])
@login_required
@admin_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash(f"Товар '{product.name}' видалено.", "success")
    return redirect(url_for('main.catalog'))

@admin_bp.route('/recalc_scores')
@login_required
@admin_required
def recalc_scores():
    c = 0
    for p in Product.query.all():
        p.buy_count = int(
            db.session.query(func.sum(OrderItem.quantity)).filter(OrderItem.product_id == p.id).scalar() or 0)
        p.update_global_score()
        c += 1
    db.session.commit()
    return f"Оновлено рейтинг для {c} товарів."