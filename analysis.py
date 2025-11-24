"""
Módulo de análisis técnico y fundamental para mejorar las decisiones de trading.
Provee indicadores técnicos (RSI, MACD, medias móviles) y métricas fundamentales.
"""
import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Optional

def calculate_rsi(prices: pd.Series, period: int = 14) -> Optional[float]:
    """Calcula el RSI (Relative Strength Index) para una serie de precios."""
    if len(prices) < period + 1:
        return None

    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None

def calculate_macd(prices: pd.Series) -> Dict[str, Optional[float]]:
    """Calcula MACD (Moving Average Convergence Divergence)."""
    if len(prices) < 26:
        return {"macd": None, "signal": None, "histogram": None}

    exp1 = prices.ewm(span=12, adjust=False).mean()
    exp2 = prices.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    histogram = macd - signal

    return {
        "macd": float(macd.iloc[-1]) if not pd.isna(macd.iloc[-1]) else None,
        "signal": float(signal.iloc[-1]) if not pd.isna(signal.iloc[-1]) else None,
        "histogram": float(histogram.iloc[-1]) if not pd.isna(histogram.iloc[-1]) else None
    }

def calculate_moving_averages(prices: pd.Series) -> Dict[str, Optional[float]]:
    """Calcula medias móviles (SMA 20, 50, 200 días)."""
    result = {}
    for period in [20, 50, 200]:
        if len(prices) >= period:
            sma = prices.rolling(window=period).mean()
            result[f"sma_{period}"] = float(sma.iloc[-1]) if not pd.isna(sma.iloc[-1]) else None
        else:
            result[f"sma_{period}"] = None
    return result

def calculate_volatility(prices: pd.Series, period: int = 20) -> Optional[float]:
    """Calcula la volatilidad (desviación estándar) anualizada."""
    if len(prices) < period:
        return None
    returns = prices.pct_change().dropna()
    volatility = returns.rolling(window=period).std().iloc[-1] * np.sqrt(252)  # Anualizada
    return float(volatility) if not pd.isna(volatility) else None

def get_technical_analysis(ticker: str) -> Dict:
    """
    Obtiene análisis técnico completo para un ticker.
    Retorna diccionario con RSI, MACD, medias móviles, y volatilidad.
    """
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="1y", interval="1d")

        if hist.empty:
            return {
                "rsi": None, "macd": None, "signal": None, "histogram": None,
                "sma_20": None, "sma_50": None, "sma_200": None,
                "volatility": None, "volume_avg": None
            }

        closes = hist["Close"]
        volumes = hist["Volume"]

        # Indicadores técnicos
        rsi = calculate_rsi(closes)
        macd_data = calculate_macd(closes)
        mas = calculate_moving_averages(closes)
        vol = calculate_volatility(closes)

        # Volumen promedio (últimos 20 días)
        avg_vol = float(volumes.tail(20).mean()) if len(volumes) >= 20 else None

        return {
            "rsi": rsi,
            "macd": macd_data.get("macd"),
            "signal": macd_data.get("signal"),
            "histogram": macd_data.get("histogram"),
            "sma_20": mas.get("sma_20"),
            "sma_50": mas.get("sma_50"),
            "sma_200": mas.get("sma_200"),
            "volatility": vol,
            "volume_avg": avg_vol
        }
    except Exception as e:
        print(f"Error en análisis técnico para {ticker}: {e}")
        return {
            "rsi": None, "macd": None, "signal": None, "histogram": None,
            "sma_20": None, "sma_50": None, "sma_200": None,
            "volatility": None, "volume_avg": None
        }

def get_fundamental_data(ticker: str) -> Dict:
    """
    Obtiene datos fundamentales para un ticker.
    Retorna P/E ratio, dividendo, market cap, etc.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        return {
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "market_cap": info.get("marketCap"),
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "avg_volume": info.get("averageVolume"),
            "profit_margin": info.get("profitMargins"),
            "revenue_growth": info.get("revenueGrowth"),
            "eps": info.get("trailingEps"),
            "target_price": info.get("targetMeanPrice"),
            "recommendation": info.get("recommendationKey"),  # buy, hold, sell
        }
    except Exception as e:
        print(f"Error en análisis fundamental para {ticker}: {e}")
        return {
            "pe_ratio": None, "forward_pe": None, "market_cap": None,
            "dividend_yield": None, "beta": None, "52w_high": None,
            "52w_low": None, "avg_volume": None, "profit_margin": None,
            "revenue_growth": None, "eps": None, "target_price": None,
            "recommendation": None
        }

def interpret_technical_signals(tech: Dict, price: float) -> Dict[str, str]:
    """
    Interpreta los indicadores técnicos y genera señales legibles.
    """
    signals = []
    strength = "neutral"  # neutral, bullish, bearish

    # RSI
    rsi = tech.get("rsi")
    if rsi:
        if rsi < 30:
            signals.append("RSI sobreventa (potencial rebote)")
            strength = "bullish"
        elif rsi > 70:
            signals.append("RSI sobrecompra (posible corrección)")
            strength = "bearish"
        else:
            signals.append(f"RSI neutral ({rsi:.1f})")

    # MACD
    histogram = tech.get("histogram")
    if histogram:
        if histogram > 0:
            signals.append("MACD positivo (momentum alcista)")
            if strength != "bearish":
                strength = "bullish"
        else:
            signals.append("MACD negativo (momentum bajista)")
            if strength != "bullish":
                strength = "bearish"

    # Medias móviles
    sma_20 = tech.get("sma_20")
    sma_50 = tech.get("sma_50")
    sma_200 = tech.get("sma_200")

    if sma_20 and sma_50 and price > 0:
        if price > sma_20 > sma_50:
            signals.append("Precio sobre SMA20 y SMA50 (tendencia alcista)")
            if strength != "bearish":
                strength = "bullish"
        elif price < sma_20 < sma_50:
            signals.append("Precio bajo SMA20 y SMA50 (tendencia bajista)")
            if strength != "bullish":
                strength = "bearish"

    if sma_200 and price > 0:
        if price > sma_200:
            signals.append(f"Precio sobre SMA200 (bull market)")
        else:
            signals.append(f"Precio bajo SMA200 (bear market)")

    # Volatilidad
    vol = tech.get("volatility")
    if vol:
        if vol > 0.40:
            signals.append(f"Alta volatilidad ({vol:.1%}) - alto riesgo")
        elif vol < 0.20:
            signals.append(f"Baja volatilidad ({vol:.1%}) - estable")

    return {
        "signals": signals,
        "strength": strength,
        "summary": " | ".join(signals) if signals else "Sin señales técnicas"
    }

def interpret_fundamental_signals(fund: Dict, price: float) -> Dict[str, str]:
    """
    Interpreta datos fundamentales y genera evaluación.
    """
    signals = []
    valuation = "neutral"  # undervalued, overvalued, neutral

    # P/E Ratio
    pe = fund.get("pe_ratio")
    if pe:
        if pe < 15:
            signals.append(f"P/E bajo ({pe:.1f}) - potencial infravalorado")
            valuation = "undervalued"
        elif pe > 30:
            signals.append(f"P/E alto ({pe:.1f}) - potencial sobrevalorado")
            valuation = "overvalued"
        else:
            signals.append(f"P/E moderado ({pe:.1f})")

    # Dividend yield
    div_yield = fund.get("dividend_yield")
    if div_yield and div_yield > 0.02:
        signals.append(f"Dividendo {div_yield:.2%}")

    # Recomendación de analistas
    rec = fund.get("recommendation")
    if rec:
        rec_map = {"buy": "Analistas: Compra", "hold": "Analistas: Mantener", "sell": "Analistas: Venta"}
        signals.append(rec_map.get(rec, f"Analistas: {rec}"))

    # Target price
    target = fund.get("target_price")
    if target and price > 0:
        upside = ((target - price) / price) * 100
        if upside > 10:
            signals.append(f"Precio objetivo ${target:.2f} (+{upside:.1f}%)")
            if valuation != "overvalued":
                valuation = "undervalued"
        elif upside < -10:
            signals.append(f"Precio objetivo ${target:.2f} ({upside:.1f}%)")
            if valuation != "undervalued":
                valuation = "overvalued"

    # Beta (riesgo sistemático)
    beta = fund.get("beta")
    if beta:
        if beta > 1.5:
            signals.append(f"Beta alto ({beta:.2f}) - muy volátil")
        elif beta < 0.5:
            signals.append(f"Beta bajo ({beta:.2f}) - defensivo")

    return {
        "signals": signals,
        "valuation": valuation,
        "summary": " | ".join(signals) if signals else "Sin datos fundamentales"
    }
