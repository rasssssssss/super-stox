from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

app = FastAPI(title="Super Stox API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MOCK_STOCKS = [
    {"ticker": "AAPL", "company": "Apple Inc.", "sector": "Technology", "price": 212.44, "changePercent": 1.84, "marketCap": 3100000000000},
    {"ticker": "MSFT", "company": "Microsoft Corp.", "sector": "Technology", "price": 468.12, "changePercent": 0.91, "marketCap": 3500000000000},
    {"ticker": "NVDA", "company": "NVIDIA Corp.", "sector": "Technology", "price": 1098.63, "changePercent": -0.72, "marketCap": 2700000000000},
    {"ticker": "TSLA", "company": "Tesla Inc.", "sector": "Automotive", "price": 181.34, "changePercent": 2.61, "marketCap": 577000000000},
]

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class WatchlistRequest(BaseModel):
    user_id: int
    ticker: str

@app.get("/health")
def health():
    return {"status": "ok", "service": "fastapi"}

@app.get("/api/stocks")
def screen_stocks(
    query: Optional[str] = None,
    sector: Optional[str] = None,
    min_price: Optional[float] = Query(None, alias="minPrice"),
    max_price: Optional[float] = Query(None, alias="maxPrice"),
    min_market_cap: Optional[int] = Query(None, alias="minMarketCap"),
):
    data = MOCK_STOCKS
    if query:
        q = query.lower()
        data = [s for s in data if q in s["ticker"].lower() or q in s["company"].lower()]
    if sector:
        data = [s for s in data if s["sector"].lower() == sector.lower()]
    if min_price is not None:
        data = [s for s in data if s["price"] >= min_price]
    if max_price is not None:
        data = [s for s in data if s["price"] <= max_price]
    if min_market_cap is not None:
        data = [s for s in data if s["marketCap"] >= min_market_cap]
    return {"results": data, "count": len(data)}

@app.get("/api/stocks/{ticker}/history")
def stock_history(ticker: str):
    base = next((s for s in MOCK_STOCKS if s["ticker"] == ticker.upper()), None)
    if not base:
        raise HTTPException(status_code=404, detail="Ticker not found")
    today = datetime.utcnow().date()
    prices = [round(base["price"] * factor, 2) for factor in [0.94, 0.95, 0.97, 0.99, 1.01, 1.0]]
    history = [{"date": str(today - timedelta(days=5-i)), "close": prices[i]} for i in range(6)]
    return {"ticker": ticker.upper(), "history": history}

@app.get("/api/stocks/{ticker}/summary")
def stock_summary(ticker: str):
    base = next((s for s in MOCK_STOCKS if s["ticker"] == ticker.upper()), None)
    if not base:
        raise HTTPException(status_code=404, detail="Ticker not found")
    text = (
        f"{base['ticker']} is trading at ${base['price']:.2f} with a daily move of {base['changePercent']:.2f}%. "
        f"The assistant should describe trend, market context, and unusual volume without making investment recommendations."
    )
    return {"ticker": base["ticker"], "summary": text}

@app.post("/api/auth/register")
def register(payload: RegisterRequest):
    return {"message": "User registered", "email": payload.email, "password_hashing": "bcrypt(work_factor=12)"}

@app.post("/api/watchlist")
def save_watchlist(payload: WatchlistRequest):
    return {"message": "Ticker saved", "user_id": payload.user_id, "ticker": payload.ticker.upper()}
