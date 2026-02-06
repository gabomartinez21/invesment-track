"""
Módulo centralizado para obtención de precios de acciones.
Consolida toda la lógica de fetching con múltiples fallbacks.
"""

import requests
import yfinance as yf
from typing import Dict, List, Optional


def fetch_quote_yahoo_http(ticker: str) -> Dict[str, Optional[float]]:
    """Obtiene precio y cierre previo vía Yahoo Finance HTTP quote API."""
    try:
        url = "https://query1.finance.yahoo.com/v7/finance/quote"
        resp = requests.get(url, params={"symbols": ticker}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        result = ((data or {}).get("quoteResponse") or {}).get("result") or []
        if result:
            q = result[0]
            price = None
            for k in ("regularMarketPrice", "postMarketPrice", "preMarketPrice"):
                v = q.get(k)
                if v is not None:
                    price = float(v)
                    break
            prev_close = q.get("regularMarketPreviousClose")
            return {
                "price": price if price is not None else None,
                "prev_close": float(prev_close) if prev_close is not None else None,
            }
    except Exception:
        pass
    return {"price": None, "prev_close": None}


def fetch_price_yahoo_http(ticker: str) -> float:
    """Fallback por HTTP directo a Yahoo Finance quote API."""
    quote = fetch_quote_yahoo_http(ticker)
    return float(quote["price"]) if quote.get("price") is not None else 0.0


def fetch_price(ticker: str) -> float:
    """
    Obtiene el precio actual del ticker con 5 métodos de fallback.

    Orden de intentos:
    1. fast_info (más rápido)
    2. info dict
    3. history diario (5 días)
    4. history intraday (5 min)
    5. HTTP directo a Yahoo Finance API

    Returns:
        float: Precio actual o 0.0 si falla todo
    """
    try:
        t = yf.Ticker(ticker)
        price = None

        # 1) fast_info (más rápido)
        try:
            fi = getattr(t, "fast_info", None) or {}
            price = fi.get("last_price") or fi.get("last_price_raw")
        except Exception:
            price = None

        # 2) info fallback
        if not price:
            try:
                info = t.info or {}
                price = info.get("currentPrice") or info.get("regularMarketPrice")
            except Exception:
                price = None

        # 3) history (daily)
        if not price:
            try:
                hist = t.history(period="5d", interval="1d")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
            except Exception:
                price = None

        # 4) history (intraday)
        if not price:
            try:
                hist = t.history(period="1d", interval="5m")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
            except Exception:
                price = None

        # 5) HTTP fallback Yahoo
        if not price:
            price = fetch_price_yahoo_http(ticker)

        return float(price) if price else 0.0
    except Exception as e:
        print(f"Error obteniendo precio para {ticker}: {e}")
        return 0.0


def fetch_prev_close(ticker: str) -> float:
    """
    Obtiene el precio de cierre del día anterior.

    Returns:
        float: Precio de cierre anterior o 0.0 si falla
    """
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="10d", interval="1d")
        if not hist.empty:
            if len(hist["Close"]) >= 2:
                return float(hist["Close"].iloc[-2])
            else:
                return float(hist["Close"].iloc[-1])
    except Exception:
        pass

    quote = fetch_quote_yahoo_http(ticker)
    if quote.get("prev_close") is not None:
        return float(quote["prev_close"])

    return 0.0


def fetch_quotes_batch(tickers: List[str]) -> Dict[str, Dict[str, Optional[float]]]:
    """
    Obtiene precios y cierres previos para múltiples tickers en un solo request.

    Returns:
        Dict con estructura {ticker: {"price": Optional[float], "prev_close": Optional[float]}}
    """
    if not tickers:
        return {}

    symbols = ",".join(tickers)
    try:
        url = "https://query1.finance.yahoo.com/v7/finance/quote"
        resp = requests.get(url, params={"symbols": symbols}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        result = ((data or {}).get("quoteResponse") or {}).get("result") or []

        out = {ticker: {"price": None, "prev_close": None} for ticker in tickers}
        for q in result:
            symbol = q.get("symbol")
            if not symbol or symbol not in out:
                continue
            price = None
            for k in ("regularMarketPrice", "postMarketPrice", "preMarketPrice"):
                v = q.get(k)
                if v is not None:
                    price = float(v)
                    break
            prev_close = q.get("regularMarketPreviousClose")
            out[symbol] = {
                "price": price,
                "prev_close": float(prev_close) if prev_close is not None else None,
            }
        return out
    except Exception:
        return {ticker: {"price": None, "prev_close": None} for ticker in tickers}


def fetch_prices_batch(
    tickers: List[str], include_prev_close: bool = False
) -> Dict[str, Dict]:
    """
    Obtiene precios para múltiples tickers.

    Args:
        tickers: Lista de símbolos
        include_prev_close: Si True, también obtiene cierre anterior

    Returns:
        Dict con estructura {ticker: {"price": float, "prev_close": float}}
    """
    results = {}
    for ticker in tickers:
        results[ticker] = {
            "price": fetch_price(ticker),
        }
        if include_prev_close:
            results[ticker]["prev_close"] = fetch_prev_close(ticker)
    return results


def get_company_name(ticker: str) -> str:
    """
    Obtiene el nombre de la empresa.

    Returns:
        str: Nombre de la empresa o ticker si falla
    """
    try:
        info = yf.Ticker(ticker).info or {}
        return info.get("shortName") or info.get("longName") or ticker
    except Exception:
        return ticker
