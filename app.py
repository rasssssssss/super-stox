import logging
import os
import re
import secrets

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Watchlist
from data_manager import data_manager
from ai_analyzer import ai_analyzer
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY") or "demo-key-2026"
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL") or "sqlite:///superstox.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["JSON_SORT_KEYS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["REMEMBER_COOKIE_HTTPONLY"] = True
app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

if app.config["SECRET_KEY"] == "demo-key-2026":
    logging.getLogger("super_stox").warning(
        "Using default SECRET_KEY; set SECRET_KEY env var for production."
    )

_TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9\.\-]{0,9}$")
_ALLOWED_PERIODS = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}
_ALLOWED_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"}


def _normalize_ticker(raw: str) -> str:
    ticker = (raw or "").strip().upper()
    if not ticker or not _TICKER_RE.match(ticker):
        return ""
    return ticker


def _safe_request_id() -> str:
    return secrets.token_urlsafe(12)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def index():
    try:
        stocks = data_manager.get_trending()

        gainers = [
            stock for stock in stocks
            if stock.get("change_percent") is not None and stock.get("change_percent", 0) > 0
        ]

        gainers = sorted(
            gainers,
            key=lambda x: x.get("change_percent", 0),
            reverse=True
        )

        top_gainers = gainers[:10]

        return render_template(
            'index.html',
            stocks=top_gainers
        )

    except Exception as e:
        request_id = _safe_request_id()
        app.logger.exception("ERROR in index (request_id=%s): %s", request_id, e)
        return f"<h1>Error in dashboard</h1><p>Request ID: {request_id}</p>", 500


@app.route('/stock/<ticker>')
def stock_detail(ticker):
    try:
        ticker = _normalize_ticker(ticker)
        if not ticker:
            abort(404)

        stock = data_manager.get_stock(ticker)
        if not stock:
            abort(404)

        history = data_manager.get_history(ticker)
        analysis = ai_analyzer.generate_summary(stock, history)

        in_watchlist = False
        if current_user.is_authenticated:
            existing = Watchlist.query.filter_by(
                user_id=current_user.id,
                ticker=ticker
            ).first()
            in_watchlist = existing is not None

        return render_template(
            'detail.html',
            stock=stock,
            history=history,
            analysis=analysis,
            in_watchlist=in_watchlist
        )
    except Exception as e:
        request_id = _safe_request_id()
        app.logger.exception("ERROR in stock_detail (request_id=%s, ticker=%s): %s", request_id, ticker, e)
        return f"<h1>Error loading {ticker}</h1><p>Request ID: {request_id}</p>", 500


@app.route('/screener', methods=['GET', 'POST'])
def screener():
    try:
        filters = {}

        if request.method == 'POST':
            filters = {
                'ticker_query': request.form.get('ticker_query', ''),
                'min_price': request.form.get('min_price', ''),
                'max_price': request.form.get('max_price', ''),
                'min_market_cap': request.form.get('min_market_cap', ''),
                'sector': request.form.get('sector', ''),
                'max_pe': request.form.get('max_pe', ''),
                'min_roe': request.form.get('min_roe', ''),
                'max_debt_to_equity': request.form.get('max_debt_to_equity', ''),
                'min_current_ratio': request.form.get('min_current_ratio', ''),
                'min_operating_margin': request.form.get('min_operating_margin', ''),
                'min_dividend_yield': request.form.get('min_dividend_yield', ''),
                'max_price_to_book': request.form.get('max_price_to_book', ''),
                'max_price_to_sales': request.form.get('max_price_to_sales', ''),
                'min_profit_margin': request.form.get('min_profit_margin', ''),
                'max_beta': request.form.get('max_beta', '')
            }

        stocks = data_manager.screen_stocks(filters)

        sectors = [
            'Technology',
            'Healthcare',
            'Financial Services',
            'Consumer Cyclical',
            'Communication Services',
            'Consumer Defensive',
            'Energy',
            'Industrials',
            'Utilities',
            'Real Estate',
            'Materials'
        ]

        return render_template(
            'screener.html',
            stocks=stocks,
            sectors=sectors,
            filters=filters
        )

    except Exception as e:
        request_id = _safe_request_id()
        app.logger.exception("ERROR in screener (request_id=%s): %s", request_id, e)
        return f"<h1>Error in screener</h1><p>Request ID: {request_id}</p>", 500

@app.route('/watchlist')
@login_required
def watchlist():
    try:
        items = Watchlist.query.filter_by(user_id=current_user.id).all()
        stocks = []
        for item in items:
            try:
                stock_data = data_manager.get_stock(item.ticker)
                if not stock_data:
                    continue
                stock_data["history"] = data_manager.get_history(item.ticker)
                stocks.append(stock_data)
            except Exception:
                app.logger.exception("ERROR loading watchlist item ticker=%s", item.ticker)
                continue

        return render_template('watchlist.html', stocks=stocks)
    except Exception as e:
        request_id = _safe_request_id()
        app.logger.exception("ERROR in watchlist (request_id=%s): %s", request_id, e)
        return f"<h1>Error loading watchlist</h1><p>Request ID: {request_id}</p>", 500


@app.route('/api/watchlist/toggle', methods=['POST'])
@login_required
def toggle_watchlist():
    try:
        data = request.get_json() or {}
        ticker = _normalize_ticker(data.get("ticker", ""))

        if not ticker:
            return jsonify({'error': 'Invalid ticker'}), 400

        existing = Watchlist.query.filter_by(
            user_id=current_user.id,
            ticker=ticker
        ).first()

        if existing:
            db.session.delete(existing)
            db.session.commit()
            return jsonify({"status": "removed"})

        new_item = Watchlist(user_id=current_user.id, ticker=ticker)
        db.session.add(new_item)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return jsonify({"status": "added"})

        return jsonify({"status": "added"})
    except Exception as e:
        db.session.rollback()
        request_id = _safe_request_id()
        app.logger.exception("ERROR in toggle_watchlist (request_id=%s): %s", request_id, e)
        return jsonify({"error": "Failed to update watchlist", "request_id": request_id}), 500


@app.route('/api/stock/<ticker>')
def api_stock(ticker):
    try:
        ticker = _normalize_ticker(ticker)
        if not ticker:
            return jsonify({"error": "Invalid ticker"}), 400

        stock = data_manager.get_stock(ticker)
        if not stock:
            return jsonify({"error": "Ticker not found"}), 404
        return jsonify(stock)
    except Exception as e:
        request_id = _safe_request_id()
        app.logger.exception("ERROR in api_stock (request_id=%s, ticker=%s): %s", request_id, ticker, e)
        return jsonify({"error": "Failed to load stock", "request_id": request_id}), 500


@app.route('/api/history/<ticker>')
def api_history(ticker):
    try:
        ticker = _normalize_ticker(ticker)
        if not ticker:
            return jsonify({"error": "Invalid ticker"}), 400

        period = (request.args.get("period") or "6mo").strip()
        interval = (request.args.get("interval") or "1d").strip()

        if period not in _ALLOWED_PERIODS:
            return jsonify({"error": "Invalid period", "allowed": sorted(_ALLOWED_PERIODS)}), 400
        if interval not in _ALLOWED_INTERVALS:
            return jsonify({"error": "Invalid interval", "allowed": sorted(_ALLOWED_INTERVALS)}), 400

        history = data_manager.get_history(ticker, period=period, interval=interval)
        return jsonify(history)
    except Exception as e:
        request_id = _safe_request_id()
        app.logger.exception("ERROR in api_history (request_id=%s, ticker=%s): %s", request_id, ticker, e)
        return jsonify({"error": "Failed to load history", "request_id": request_id}), 500


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '')
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))

        flash('Invalid credentials', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not username or len(username) < 3:
            flash('Username must be at least 3 characters', 'error')
            return redirect(url_for('register'))

        if not password or len(password) < 6:
            flash('Password must be at least 6 characters', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('Username already taken', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('register'))

        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("That username or email is already registered", "error")
            return redirect(url_for("register"))

        login_user(new_user)
        flash('Account created successfully!', 'success')
        return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    debug = (os.getenv("FLASK_DEBUG") or "").strip() in {"1", "true", "True"}
    app.run(debug=debug, host="0.0.0.0", port=int(os.getenv("PORT") or "5000"))
