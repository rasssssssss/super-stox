from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    watchlist_items = db.relationship('Watchlist', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
    
    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

class Watchlist(db.Model):
    __tablename__ = 'watchlists'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    ticker = db.Column(db.String(20), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'ticker', name='unique_user_ticker'),)

class StockCache(db.Model):
    __tablename__ = 'stock_cache'
    
    ticker = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(200))
    sector = db.Column(db.String(100))
    industry = db.Column(db.String(100))
    market_cap = db.Column(db.BigInteger)
    current_price = db.Column(db.Float)
    change = db.Column(db.Float)
    change_percent = db.Column(db.Float)
    volume = db.Column(db.BigInteger)
    avg_volume = db.Column(db.BigInteger)
    pe_ratio = db.Column(db.Float)
    week_52_high = db.Column(db.Float)
    week_52_low = db.Column(db.Float)
    description = db.Column(db.Text)
    historical_data = db.Column(db.Text)
    is_real_data = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)