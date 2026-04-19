import os
import time
from pathlib import Path
from typing import Any

import yfinance as yf

try:
    from alpha_vantage.techindicators import TechIndicators
except ImportError:
    TechIndicators = None


class DataManager:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent
        self.default_tickers = self._load_tickers()
        self.alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
        self._cache: dict[str, tuple[float, Any]] = {}
        self._stock_ttl_seconds = int(os.getenv("STOCK_CACHE_TTL_SECONDS") or "60")
        self._history_ttl_seconds = int(os.getenv("HISTORY_CACHE_TTL_SECONDS") or "300")
        self._trending_ttl_seconds = int(os.getenv("TRENDING_CACHE_TTL_SECONDS") or "60")

    def _load_tickers(self):
        try:
            tickers_path = self.base_dir / "tickers.txt"
            with tickers_path.open("r", encoding="utf-8") as f:
                tickers = []
                for line in f:
                    value = line.strip().upper()
                    if not value or value.startswith("#"):
                        continue
                    tickers.append(value)
                return tickers
        except Exception:
            return [
                "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
                "META", "TSLA", "JPM", "V", "WMT"
            ]

    def _safe_float(self, value, default=0.0):
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    def _safe_int(self, value, default=0):
        try:
            if value is None:
                return default
            return int(value)
        except Exception:
            return default

    def _extract_stock(self, ticker, info):
        current_price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        previous_close = info.get("previousClose") or info.get("regularMarketPreviousClose") or 0

        change = current_price - previous_close if previous_close else 0
        change_percent = (change / previous_close * 100) if previous_close else 0

        week_high = self._safe_float(info.get("fiftyTwoWeekHigh"))
        week_low = self._safe_float(info.get("fiftyTwoWeekLow"))

        return {
            "ticker": ticker.upper(),
            "name": info.get("shortName") or info.get("longName") or ticker.upper(),

            "current_price": self._safe_float(current_price),
            "price": self._safe_float(current_price),
            "change": self._safe_float(change),
            "change_percent": self._safe_float(change_percent),

            "market_cap": self._safe_int(info.get("marketCap")),
            "pe_ratio": self._safe_float(info.get("trailingPE")),
            "trailing_pe": self._safe_float(info.get("trailingPE")),
            "forward_pe": self._safe_float(info.get("forwardPE")),
            "peg_ratio": self._safe_float(info.get("pegRatio")),
            "price_to_book": self._safe_float(info.get("priceToBook")),
            "price_to_sales": self._safe_float(info.get("priceToSalesTrailing12Months")),
            "enterprise_to_ebitda": self._safe_float(info.get("enterpriseToEbitda")),
            "enterprise_to_revenue": self._safe_float(info.get("enterpriseToRevenue")),

            "return_on_equity": self._safe_float(info.get("returnOnEquity")),
            "return_on_assets": self._safe_float(info.get("returnOnAssets")),
            "gross_margin": self._safe_float(info.get("grossMargins")),
            "operating_margin": self._safe_float(info.get("operatingMargins")),
            "profit_margin": self._safe_float(info.get("profitMargins")),

            "debt_to_equity": self._safe_float(info.get("debtToEquity")),
            "current_ratio": self._safe_float(info.get("currentRatio")),
            "quick_ratio": self._safe_float(info.get("quickRatio")),

            "dividend_yield": self._safe_float(info.get("dividendYield")),
            "payout_ratio": self._safe_float(info.get("payoutRatio")),
            "beta": self._safe_float(info.get("beta")),

            "sector": info.get("sector") or "Unknown",
            "industry": info.get("industry") or "Unknown",
            "currency": info.get("currency") or "USD",
            "exchange": info.get("exchange") or info.get("fullExchangeName") or "Unknown",
            "website": info.get("website") or "",
            "description": info.get("longBusinessSummary") or "No company summary available.",
            "summary": info.get("longBusinessSummary") or "No company summary available.",

            "day_high": self._safe_float(info.get("dayHigh")),
            "day_low": self._safe_float(info.get("dayLow")),
            "fifty_two_week_high": week_high,
            "fifty_two_week_low": week_low,
            "week_52_high": week_high,
            "week_52_low": week_low,

            "volume": self._safe_int(info.get("volume")),
        }

    def _cache_get(self, key: str):
        entry = self._cache.get(key)
        if not entry:
            return None

        expires_at, value = entry
        if time.time() >= expires_at:
            self._cache.pop(key, None)
            return None

        return value

    def _cache_set(self, key: str, value: Any, ttl_seconds: int):
        ttl = max(0, int(ttl_seconds))
        self._cache[key] = (time.time() + ttl, value)

    def get_trending(self):
        cache_key = "trending"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        stocks = []
        for ticker in self.default_tickers:
            try:
                stock = yf.Ticker(ticker)
                info = stock.info or {}
                stocks.append(self._extract_stock(ticker, info))
            except Exception:
                continue

        self._cache_set(cache_key, stocks, self._trending_ttl_seconds)
        return stocks

    def get_stock(self, ticker):
        ticker = (ticker or "").upper().strip()
        if not ticker:
            return {}

        cache_key = f"stock:{ticker}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            stock = yf.Ticker(ticker)
            info = stock.info or {}
            data = self._extract_stock(ticker, info)
            data["indicators"] = self.get_technical_indicators(ticker)
        except Exception:
            return {}

        self._cache_set(cache_key, data, self._stock_ttl_seconds)
        return data

    def get_history(self, ticker, period="6mo", interval="1d"):
        ticker = (ticker or "").upper().strip()
        if not ticker:
            return []

        period = (period or "6mo").strip()
        interval = (interval or "1d").strip()

        cache_key = f"history:{ticker}:{period}:{interval}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            hist = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)
        except Exception:
            return []

        if hist is None or getattr(hist, "empty", True):
            return []

        history = []
        for idx, row in hist.iterrows():
            history.append(
                {
                    "date": idx.isoformat() if hasattr(idx, "isoformat") else str(idx),
                    "open": self._safe_float(row.get("Open")),
                    "high": self._safe_float(row.get("High")),
                    "low": self._safe_float(row.get("Low")),
                    "close": self._safe_float(row.get("Close")),
                    "volume": self._safe_int(row.get("Volume")),
                }
            )

        self._cache_set(cache_key, history, self._history_ttl_seconds)
        return history

    def screen_stocks(self, filters=None):
        filters = filters or {}
        stocks = self.get_trending()

        ticker_query = (filters.get("ticker_query") or "").strip().upper()

        min_price = self._safe_float(filters.get("min_price")) if filters.get("min_price") else None
        max_price = self._safe_float(filters.get("max_price")) if filters.get("max_price") else None
        min_market_cap = self._safe_float(filters.get("min_market_cap")) if filters.get("min_market_cap") else None
        sector = (filters.get("sector") or "").strip().lower()

        max_pe = self._safe_float(filters.get("max_pe")) if filters.get("max_pe") else None
        min_roe = self._safe_float(filters.get("min_roe")) if filters.get("min_roe") else None
        max_debt_to_equity = self._safe_float(filters.get("max_debt_to_equity")) if filters.get("max_debt_to_equity") else None
        min_current_ratio = self._safe_float(filters.get("min_current_ratio")) if filters.get("min_current_ratio") else None
        min_operating_margin = self._safe_float(filters.get("min_operating_margin")) if filters.get("min_operating_margin") else None
        min_dividend_yield = self._safe_float(filters.get("min_dividend_yield")) if filters.get("min_dividend_yield") else None
        max_price_to_book = self._safe_float(filters.get("max_price_to_book")) if filters.get("max_price_to_book") else None
        max_price_to_sales = self._safe_float(filters.get("max_price_to_sales")) if filters.get("max_price_to_sales") else None
        min_profit_margin = self._safe_float(filters.get("min_profit_margin")) if filters.get("min_profit_margin") else None
        max_beta = self._safe_float(filters.get("max_beta")) if filters.get("max_beta") else None

        filtered = []
        for stock in stocks:
            if ticker_query:
                ticker_match = ticker_query in (stock.get("ticker", "") or "").upper()
                name_match = ticker_query in (stock.get("name", "") or "").upper()
                if not ticker_match and not name_match:
                    continue

            if min_price is not None and stock["current_price"] < min_price:
                continue
            if max_price is not None and stock["current_price"] > max_price:
                continue
            if min_market_cap is not None and stock["market_cap"] < min_market_cap:
                continue
            if sector and stock["sector"].lower() != sector:
                continue
            if max_pe is not None and stock["trailing_pe"] > max_pe:
                continue
            if min_roe is not None and stock["return_on_equity"] < min_roe:
                continue
            if max_debt_to_equity is not None and stock["debt_to_equity"] > max_debt_to_equity:
                continue
            if min_current_ratio is not None and stock["current_ratio"] < min_current_ratio:
                continue
            if min_operating_margin is not None and stock["operating_margin"] < min_operating_margin:
                continue
            if min_dividend_yield is not None and stock["dividend_yield"] < min_dividend_yield:
                continue
            if max_price_to_book is not None and stock["price_to_book"] > max_price_to_book:
                continue
            if max_price_to_sales is not None and stock["price_to_sales"] > max_price_to_sales:
                continue
            if min_profit_margin is not None and stock["profit_margin"] < min_profit_margin:
                continue
            if max_beta is not None and stock["beta"] > max_beta:
                continue

            filtered.append(stock)

        return filtered

    def get_technical_indicators(self, ticker):
        if not self.alpha_vantage_key or TechIndicators is None:
            return {}

        try:
            ti = TechIndicators(key=self.alpha_vantage_key, output_format="json")

            sma_data, _ = ti.get_sma(symbol=ticker, interval="daily", time_period=20, series_type="close")
            rsi_data, _ = ti.get_rsi(symbol=ticker, interval="daily", time_period=14, series_type="close")

            latest_sma_key = max(sma_data) if sma_data else None
            latest_rsi_key = max(rsi_data) if rsi_data else None

            return {
                "sma20": sma_data.get(latest_sma_key, {}).get("SMA") if latest_sma_key else None,
                "rsi14": rsi_data.get(latest_rsi_key, {}).get("RSI") if latest_rsi_key else None,
            }
        except Exception:
            return {}


data_manager = DataManager()
