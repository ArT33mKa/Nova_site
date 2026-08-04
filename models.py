from datetime import datetime, timezone
from flask import current_app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
from extensions import db


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(64), unique=True, nullable=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    children = db.relationship('Category', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    products = db.relationship('Product', backref='category_rel', lazy='dynamic')


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    is_email_verified = db.Column(db.Boolean, default=False)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    avatar_url = db.Column(db.String(255), nullable=True)

    reviews = db.relationship('Review', backref='author', lazy='dynamic')
    orders = db.relationship('Order', backref='customer', lazy='dynamic')
    cart_items = db.relationship('CartItem', back_populates='user', lazy='dynamic', cascade="all, delete-orphan")
    favorites = db.relationship('Favorite', backref='user', lazy='dynamic', cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_email_verify_token(self):
        s = URLSafeTimedSerializer(current_app.secret_key)
        return s.dumps({'user_id': self.id, 'email': self.email})

    def get_email_change_token(self, new_email):
        # Токен для підтвердження НОВОЇ пошти (сама пошта зберігається лише в токені,
        # в акаунт вона запишеться лише після переходу за посиланням).
        s = URLSafeTimedSerializer(current_app.secret_key)
        return s.dumps({'user_id': self.id, 'email': new_email})

    @staticmethod
    def verify_email_token(token, max_age=86400):
        s = URLSafeTimedSerializer(current_app.secret_key)
        try:
            data = s.loads(token, max_age=max_age)
            user_id = data.get('user_id')
            email = data.get('email')
        except Exception:
            return None, None
        return User.query.get(user_id), email

    def get_reset_token(self):
        s = URLSafeTimedSerializer(current_app.secret_key)
        return s.dumps({'user_id': self.id})

    @staticmethod
    def verify_reset_token(token, max_age=1800):
        s = URLSafeTimedSerializer(current_app.secret_key)
        try:
            data = s.loads(token, max_age=max_age)
            user_id = data.get('user_id')
        except Exception:
            return None
        return User.query.get(user_id)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(64), unique=True, nullable=True, index=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    image = db.Column(db.String(255), nullable=True)
    image_hash = db.Column(db.String(128), nullable=True)
    category = db.Column(db.String(100))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    in_stock = db.Column(db.Boolean, default=True)

    rating = db.Column(db.Float, default=0.0)
    reviews_count = db.Column(db.Integer, default=0)
    views_count = db.Column(db.Integer, default=0)
    buy_count = db.Column(db.Integer, default=0)
    global_score = db.Column(db.Float, default=0.0, index=True)

    reviews = db.relationship('Review', backref='product', lazy='dynamic', cascade="all, delete-orphan")

    def update_global_score(self):
        b = self.buy_count or 0
        r = self.rating or 0
        v = self.views_count or 0
        price = self.price or 0

        score = (b * 10) + (r * 5) + (v * 0.1)
        score += (price * 0.02)

        if price < 100:
            score = score * 0.2

        if not self.image or 'no_image' in self.image or 'default' in self.image:
            score = -10000.0

        self.global_score = score


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False, default=0)
    text = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    author_name = db.Column(db.String(100), nullable=True)
    author_email = db.Column(db.String(120), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    review_type = db.Column(db.String(50), nullable=False, default='review')
    parent_id = db.Column(db.Integer, db.ForeignKey('review.id'), nullable=True)

    replies = db.relationship('Review', backref=db.backref('parent', remote_side=[id]), lazy='dynamic',
                              cascade="all, delete-orphan", order_by='Review.timestamp.asc()')
    votes = db.relationship('ReviewVote', backref='review', lazy='dynamic', cascade="all, delete-orphan")

    @property
    def likes_count(self):
        return self.votes.filter_by(value=1).count()

    @property
    def dislikes_count(self):
        return self.votes.filter_by(value=-1).count()

class ReviewVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    review_id = db.Column(db.Integer, db.ForeignKey('review.id'), nullable=False)
    value = db.Column(db.Integer, nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'review_id', name='_user_review_vote_uc'),)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(50), nullable=False, default='Нове')
    payment_id = db.Column(db.String(64), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    delivery_method = db.Column(db.String(50))
    delivery_city = db.Column(db.String(100), nullable=True)
    delivery_warehouse = db.Column(db.String(255), nullable=True)
    payment_method = db.Column(db.String(50))
    total_cost = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    comment = db.Column(db.Text, nullable=True)

    items = db.relationship('OrderItem', backref='order', lazy='dynamic', cascade="all, delete-orphan")

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    product = db.relationship('Product')

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    user = db.relationship('User', back_populates='cart_items')
    product = db.relationship('Product')
    __table_args__ = (db.UniqueConstraint('user_id', 'product_id', name='_user_product_uc'),)

    @property
    def item_total(self):
        return self.product.price * self.quantity

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'product_id', name='_user_product_fav_uc'),)

class CategoryView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    views = db.Column(db.Integer, default=0)

class OAuth(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    token = db.Column(db.JSON, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship(User)