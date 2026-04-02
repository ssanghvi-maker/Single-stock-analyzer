import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime
from tabulate import tabulate

# ================================
# CONFIG
# ================================

RISK_FREE_RATE = 0.04
MARKET_RETURN = 0.08

# Optional: manually define peers if auto fails
PEER_MAP = {
    "AAPL": ["MSFT", "GOOGL", "AMZN"],
    "NVDA": ["AMD", "INTC", "TSM"],
}

# ================================
# HELPER FUNCTIONS
# ================================

def get_stock_data(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info
    financials = stock.financials
    balance = stock.balance_sheet
    cashflow = stock.cashflow
    hist = stock.history(period="5y")
    return stock, info, financials, balance, cashflow, hist


def get_peers(ticker, info):
    if ticker in PEER_MAP:
        return PEER_MAP[ticker]
    
    sector = info.get("sector", "")
    industry = info.get("industry", "")
    
    # crude fallback: grab similar tickers via yfinance recommendations
    try:
        recs = yf.Ticker(ticker).recommendations
        if recs is not None:
            return list(set(recs['To Grade'].dropna().head(3)))
    except:
        pass
    
    return []


def compute_financial_metrics(info, financials, balance, cashflow):
    metrics = {}

    try:
        revenue = financials.loc["Total Revenue"]
        metrics["Revenue Growth"] = revenue.pct_change().mean()
    except:
        metrics["Revenue Growth"] = np.nan

    try:
        net_income = financials.loc["Net Income"]
        metrics["Net Income Growth"] = net_income.pct_change().mean()
    except:
        metrics["Net Income Growth"] = np.nan

    metrics["Gross Margin"] = info.get("grossMargins")
    metrics["Operating Margin"] = info.get("operatingMargins")
    metrics["ROE"] = info.get("returnOnEquity")
    metrics["PE"] = info.get("trailingPE")
    metrics["Forward PE"] = info.get("forwardPE")
    metrics["Debt/Equity"] = info.get("debtToEquity")

    return metrics


def get_peer_metrics(peers):
    peer_data = {}

    for p in peers:
        try:
            info = yf.Ticker(p).info
            peer_data[p] = {
                "PE": info.get("trailingPE"),
                "Revenue Growth": info.get("revenueGrowth"),
                "ROE": info.get("returnOnEquity")
            }
        except:
            continue

    return pd.DataFrame(peer_data).T


def insider_activity(ticker):
    try:
        stock = yf.Ticker(ticker)
        insider = stock.insider_transactions
        if insider is None or insider.empty:
            return 0
        
        buys = insider[insider["transactionType"] == "Buy"]
        sells = insider[insider["transactionType"] == "Sell"]
        
        score = len(buys) - len(sells)
        return score
    except:
        return 0


def macro_score():
    # crude macro proxy (can expand with real data APIs)
    # positive if rates stable / inflation cooling
    return np.random.uniform(-1, 1)


def industry_score(info):
    # proxy based on sector
    growth_sectors = ["Technology", "Healthcare"]
    if info.get("sector") in growth_sectors:
        return 1
    return 0


# ================================
# SCORING ENGINE
# ================================

def score_stock(metrics, peer_df, insider, macro, industry):
    score = 0

    # Growth
    if metrics["Revenue Growth"] and metrics["Revenue Growth"] > 0.05:
        score += 15
    if metrics["Net Income Growth"] and metrics["Net Income Growth"] > 0.05:
        score += 15

    # Profitability
    if metrics["Operating Margin"] and metrics["Operating Margin"] > 0.15:
        score += 10
    if metrics["ROE"] and metrics["ROE"] > 0.15:
        score += 10

    # Valuation vs peers
    if not peer_df.empty:
        peer_pe = peer_df["PE"].mean()
        if metrics["PE"] and peer_pe and metrics["PE"] < peer_pe:
            score += 10
        else:
            score -= 5

    # Balance sheet
    if metrics["Debt/Equity"] and metrics["Debt/Equity"] < 100:
        score += 5

    # Insider
    score += np.clip(insider, -10, 10)

    # Macro + Industry
    score += macro * 5
    score += industry * 5

    return round(score, 2)


def recommendation(score):
    if score >= 50:
        return "STRONG BUY"
    elif score >= 30:
        return "BUY"
    elif score >= 15:
        return "HOLD"
    elif score >= 0:
        return "SELL"
    else:
        return "STRONG SELL"


# ================================
# REPORT GENERATOR
# ================================

def generate_report(ticker):
    print(f"\nAnalyzing {ticker}...\n")

    stock, info, financials, balance, cashflow, hist = get_stock_data(ticker)

    metrics = compute_financial_metrics(info, financials, balance, cashflow)
    peers = get_peers(ticker, info)
    peer_df = get_peer_metrics(peers)

    insider = insider_activity(ticker)
    macro = macro_score()
    industry = industry_score(info)

    score = score_stock(metrics, peer_df, insider, macro, industry)
    rec = recommendation(score)

    # ================================
    # OUTPUT
    # ================================

    print("=== COMPANY OVERVIEW ===")
    print(info.get("longName"))
    print(info.get("sector"), "|", info.get("industry"))

    print("\n=== FINANCIAL METRICS ===")
    print(tabulate(metrics.items(), headers=["Metric", "Value"]))

    print("\n=== PEER COMPARISON ===")
    if not peer_df.empty:
        print(tabulate(peer_df, headers="keys"))
    else:
        print("No peer data available")

    print("\n=== INSIDER SCORE ===")
    print(insider)

    print("\n=== MACRO SCORE ===")
    print(round(macro, 2))

    print("\n=== INDUSTRY SCORE ===")
    print(industry)

    print("\n=== FINAL SCORE ===")
    print(score)

    print("\n=== RECOMMENDATION ===")
    print(rec)


# ================================
# MAIN
# ================================

if __name__ == "__main__":
    ticker = input("Enter stock ticker: ").upper()
    generate_report(ticker)
