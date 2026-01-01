"""
Stock analysis module using yfinance

Implements the "trader writer" methodology from:
CADIC, Philippe. "Investir sur la Bourse de Hong Kong avec Python, Excel et Saxo"

Key principle: Calculate performance over multiple periods (3m, 6m, 1y, 3y, 5y)
to identify "resilient" stocks that show consistent positive growth across all periods.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
from typing import Optional, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def calculate_performance(ticker: str, period_days: int) -> Optional[float]:
    """
    Calculate the performance of a stock over a specific period.

    This follows the "trader writer" methodology:
    - Fetch historical data for the exact period needed
    - Calculate: ((end_price - start_price) / start_price) * 100

    Args:
        ticker: Stock ticker symbol
        period_days: Number of days to look back

    Returns:
        Performance percentage or None if data unavailable
    """
    try:
        stock = yf.Ticker(ticker)
        end_date = datetime.today()
        start_date = end_date - timedelta(days=period_days)

        # Fetch data for the specific period (trader writer approach)
        data = stock.history(start=start_date, end=end_date)

        if data.empty or len(data) < 2:
            return None

        start_price = data['Close'].iloc[0]
        end_price = data['Close'].iloc[-1]

        performance = ((end_price - start_price) / start_price) * 100
        return performance

    except Exception as e:
        logger.warning(f"Error calculating {period_days}d performance for {ticker}: {e}")
        return None


def analyze_stock(ticker: str) -> dict:
    """
    Analyze a stock across multiple time periods using the "trader writer" methodology.

    This approach:
    1. Calculates performance over 5 periods: 3m, 6m, 1y, 3y, 5y
    2. Identifies "resilient" stocks (positive on ALL periods)
    3. Calculates volatility and extracts dividend yield

    Returns performance metrics, volatility, dividend yield, and chart data.
    """
    try:
        logger.info(f"Analyzing {ticker}...")
        stock = yf.Ticker(ticker)

        # Get 5 years of historical data for chart and volatility
        hist = stock.history(period="5y")

        if hist.empty:
            logger.warning(f"No historical data available for {ticker}")
            return {"ticker": ticker, "error": "No data available - ticker may be invalid"}

        current_price = float(hist['Close'].iloc[-1])

        # Calculate daily returns for volatility (annualized)
        returns = hist['Close'].pct_change().dropna()
        volatility = float(returns.std() * np.sqrt(252) * 100)

        # Get stock info with better error handling
        info = {}
        try:
            info = stock.info or {}
        except Exception as e:
            logger.warning(f"Could not fetch info for {ticker}: {e}")

        # Extract dividend yield (with fallback)
        dividend_yield = None
        try:
            if info.get('dividendYield'):
                dividend_yield = float(info.get('dividendYield')) * 100
            elif info.get('trailingAnnualDividendYield'):
                dividend_yield = float(info.get('trailingAnnualDividendYield')) * 100
        except (TypeError, ValueError):
            dividend_yield = None

        # Define periods following "trader writer" methodology
        # These are the key periods to evaluate stock resilience
        periods = {
            "perf_3m": 90,      # 3 months
            "perf_6m": 180,     # 6 months
            "perf_1y": 365,     # 1 year
            "perf_3y": 365 * 3, # 3 years
            "perf_5y": 365 * 5  # 5 years
        }

        # Calculate performance for each period using trader writer method
        perfs = {}
        for period_name, period_days in periods.items():
            perf = calculate_performance(ticker, period_days)
            perfs[period_name] = perf
            logger.debug(f"{ticker} {period_name}: {perf}")

        # Check if stock is "resilient" (always profitable)
        # Key insight from trader writer: A truly resilient stock must show
        # POSITIVE growth across ALL periods - this filters out volatile stocks
        # that may have had temporary gains
        is_resilient = all(
            p is not None and p > 0
            for p in perfs.values()
        )

        if is_resilient:
            logger.info(f"{ticker} is RESILIENT - positive across all periods")

        # Prepare chart data (weekly samples for 5 years)
        chart_data = hist['Close'].resample('W').last().dropna()
        chart = [
            {
                "date": d.strftime("%Y-%m-%d"),
                "price": round(float(p), 2)
            }
            for d, p in chart_data.items()
        ]

        # Get additional info
        name = info.get('shortName') or info.get('longName') or ticker
        currency = info.get('currency', 'USD')
        sector = info.get('sector', None)
        industry = info.get('industry', None)
        market_cap = info.get('marketCap', None)

        result = {
            "ticker": ticker,
            "name": name,
            "currency": currency,
            "sector": sector,
            "industry": industry,
            "market_cap": market_cap,
            "current_price": round(float(current_price), 2),
            "perf_3m": round(perfs['perf_3m'], 2) if perfs['perf_3m'] is not None else None,
            "perf_6m": round(perfs['perf_6m'], 2) if perfs['perf_6m'] is not None else None,
            "perf_1y": round(perfs['perf_1y'], 2) if perfs['perf_1y'] is not None else None,
            "perf_3y": round(perfs['perf_3y'], 2) if perfs['perf_3y'] is not None else None,
            "perf_5y": round(perfs['perf_5y'], 2) if perfs['perf_5y'] is not None else None,
            "volatility": round(float(volatility), 2),
            "dividend_yield": round(dividend_yield, 2) if dividend_yield else None,
            "is_resilient": is_resilient,
            "chart_data": chart[-260:],  # ~5 years of weekly data
            "last_updated": datetime.now().isoformat()
        }

        logger.info(f"Successfully analyzed {ticker}: resilient={is_resilient}")
        return result

    except Exception as e:
        logger.error(f"Error analyzing {ticker}: {str(e)}")
        return {"ticker": ticker, "error": str(e)}


def analyze_batch(tickers: list) -> list:
    """Analyze multiple stocks"""
    results = []
    for ticker in tickers:
        result = analyze_stock(ticker)
        results.append(result)
    return results


def get_always_profitable(stocks: list) -> list:
    """
    Filter stocks that are "always profitable" - positive on ALL periods.

    This is the key insight from the "trader writer" methodology:
    A stock that shows consistent growth across 3m, 6m, 1y, 3y, and 5y
    is more likely to continue performing well.
    """
    return [s for s in stocks if s.get('is_resilient', False)]


def export_to_csv(stocks: list, resilient_only: bool = False) -> str:
    """
    Convert stock results to CSV format.

    Args:
        stocks: List of stock analysis results
        resilient_only: If True, only export "always profitable" stocks
    """
    if not stocks:
        return ""

    # Filter out errors
    valid_stocks = [s for s in stocks if 'error' not in s]

    # Optionally filter to only resilient stocks
    if resilient_only:
        valid_stocks = get_always_profitable(valid_stocks)

    if not valid_stocks:
        if resilient_only:
            return "message\nNo stocks are always profitable across all periods"
        return "ticker,error\n" + "\n".join(
            f"{s['ticker']},{s.get('error', 'Unknown')}" for s in stocks
        )

    headers = [
        "ticker", "name", "currency", "current_price",
        "perf_3m", "perf_6m", "perf_1y", "perf_3y", "perf_5y",
        "volatility", "dividend_yield", "is_resilient", "sector", "market_cap"
    ]

    lines = [";".join(headers)]  # Using semicolon like trader writer script
    for stock in valid_stocks:
        row = [
            stock.get('ticker', ''),
            f'"{stock.get("name", "")}"',
            stock.get('currency', ''),
            str(stock.get('current_price', '')),
            str(stock.get('perf_3m', '')),
            str(stock.get('perf_6m', '')),
            str(stock.get('perf_1y', '')),
            str(stock.get('perf_3y', '')),
            str(stock.get('perf_5y', '')),
            str(stock.get('volatility', '')),
            str(stock.get('dividend_yield', '')),
            str(stock.get('is_resilient', '')),
            f'"{stock.get("sector", "")}"',
            str(stock.get('market_cap', ''))
        ]
        lines.append(";".join(row))

    return "\n".join(lines)
