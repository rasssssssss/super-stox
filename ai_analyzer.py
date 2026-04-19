# ai_analyzer.py
class AIAnalyzer:
    def generate_summary(self, stock, history):
        if not stock:
            return "No stock data is available."

        ticker = stock.get("ticker", "Unknown")
        name = stock.get("name", ticker)
        price = stock.get("price", 0)
        change = stock.get("change", 0)
        change_percent = stock.get("change_percent", 0)
        sector = stock.get("sector", "Unknown")
        market_cap = stock.get("market_cap", 0)
        pe_ratio = stock.get("pe_ratio")
        volume = stock.get("volume", 0)

        trend_text = "Not enough historical data to describe the recent trend."
        if history and len(history) >= 2:
            first_close = history[0].get("close", 0)
            last_close = history[-1].get("close", 0)

            if first_close and last_close:
                trend_pct = ((last_close - first_close) / first_close) * 100
                if trend_pct > 5:
                    trend_text = f"Over the selected period, the stock has shown a noticeable upward trend of about {trend_pct:.2f}%."
                elif trend_pct < -5:
                    trend_text = f"Over the selected period, the stock has shown a noticeable downward trend of about {trend_pct:.2f}%."
                else:
                    trend_text = f"Over the selected period, the stock has moved relatively sideways with a change of {trend_pct:.2f}%."

        valuation_text = "Valuation data is limited."
        if pe_ratio is not None:
            valuation_text = f"The trailing P/E ratio is {pe_ratio:.2f}, which can help users compare valuation against similar firms in the same sector."

        move_direction = "up" if change >= 0 else "down"

        return (
            f"{name} ({ticker}) is currently trading at {price:.2f}, {move_direction} "
            f"{abs(change):.2f} points ({abs(change_percent):.2f}%) in the latest session. "
            f"It operates in the {sector} sector with a market capitalisation of approximately {market_cap:,}. "
            f"Latest reported trading volume is {volume:,}. "
            f"{trend_text} {valuation_text} "
            f"This summary is for educational use and should not be treated as financial advice."
        )


ai_analyzer = AIAnalyzer()
