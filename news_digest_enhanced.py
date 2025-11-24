"""
Sistema mejorado de alertas de portfolio con:
- Análisis técnico y fundamental
- Múltiples fuentes de noticias
- Portfolio rebalancing
- Email HTML profesional
- Prompts mejorados de OpenAI
"""
import os
import ssl
import smtplib
import pandas as pd
from email.message import EmailMessage
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, List

# Importar módulos creados
from analysis import get_technical_analysis, get_fundamental_data, interpret_technical_signals, interpret_fundamental_signals
from portfolio import calculate_portfolio_values, generate_rebalancing_recommendation
from news_sources import aggregate_news_from_all_sources, calculate_news_sentiment
from ai_analysis import get_ai_analysis
from email_template import generate_email_html
from news_digest import fetch_price, fetch_prev_close, load_portfolio, should_send_now

# Configuración
CSV_URL = os.environ["SHEET_CSV_URL"]
FROM_EMAIL = os.environ["FROM_EMAIL"]
TO_EMAIL = os.environ["TO_EMAIL"]
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587") or "587")
SMTP_USER = os.environ.get("SMTP_USER", FROM_EMAIL)
SMTP_PASS = os.environ["SMTP_PASS"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-mini")
SEND_LOCAL_TZ = os.environ.get("SEND_LOCAL_TZ", "America/Lima")
SEND_AT_HHMM = os.environ.get("SEND_AT_HHMM", "08:45")
MAX_ARTICLES_PER_SOURCE = int(os.environ.get("MAX_ARTICLES_PER_SOURCE", "3"))
MARKETAUX_API_KEY = os.environ.get("MARKETAUX_API_KEY", None)  # Opcional

# Portfolio rebalancing
ENABLE_REBALANCING = os.environ.get("ENABLE_REBALANCING", "true").lower() == "true"
MIN_TRADE_VALUE = float(os.environ.get("MIN_TRADE_VALUE", "100"))
MAX_DEVIATION = float(os.environ.get("MAX_DEVIATION", "5"))

def get_company_name(ticker: str) -> str:
    """Obtiene el nombre de la empresa."""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        return info.get("shortName") or info.get("longName") or ticker
    except Exception:
        return ticker

def process_stock_data(
    ticker: str,
    row: pd.Series,
    prices: Dict[str, float],
    portfolio_df: pd.DataFrame
) -> Dict:
    """
    Procesa toda la información de una acción: precio, noticias, análisis técnico/fundamental.
    """
    print(f"Procesando {ticker}...")

    # Información básica
    company = get_company_name(ticker)
    price = prices.get(ticker, 0.0)
    prev_close = fetch_prev_close(ticker)

    # Cambio porcentual
    change_pct = 0.0
    if price > 0 and prev_close > 0:
        change_pct = ((price - prev_close) / prev_close) * 100.0

    # Análisis técnico
    technical_data = get_technical_analysis(ticker)
    tech_signals = interpret_technical_signals(technical_data, price)

    # Análisis fundamental
    fundamental_data = get_fundamental_data(ticker)
    fund_signals = interpret_fundamental_signals(fundamental_data, price)

    # Noticias de múltiples fuentes
    articles = aggregate_news_from_all_sources(
        ticker, company,
        max_per_source=MAX_ARTICLES_PER_SOURCE,
        marketaux_api_key=MARKETAUX_API_KEY
    )
    news_sentiment = calculate_news_sentiment(articles)

    # Contexto de portfolio (para rebalancing)
    portfolio_context = None
    if "TargetWeight" in row.index and row.get("TargetWeight"):
        total_value = sum(prices.get(t, 0) * portfolio_df[portfolio_df["Ticker"] == t]["Qty"].iloc[0]
                         for t in portfolio_df["Ticker"] if t in prices)
        current_value = price * row.get("Qty", 0)
        current_weight = (current_value / total_value * 100) if total_value > 0 else 0

        portfolio_context = {
            "current_weight": current_weight,
            "target_weight": row.get("TargetWeight", 0),
            "quantity": row.get("Qty", 0)
        }

    # Análisis con OpenAI (mejorado)
    ai_result = get_ai_analysis(
        ticker=ticker,
        company=company,
        price=price,
        prev_close=prev_close,
        articles=articles,
        technical_data=technical_data,
        fundamental_data=fundamental_data,
        portfolio_context=portfolio_context,
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY
    )

    return {
        "ticker": ticker,
        "company": company,
        "price": price,
        "prev_close": prev_close,
        "change_pct": change_pct,
        "recommendation": ai_result.get("recommendation", "MANTENER"),
        "news_summary": ai_result.get("full_text", "Sin análisis disponible"),
        "technical_summary": tech_signals.get("summary", ""),
        "fundamental_summary": fund_signals.get("summary", ""),
        "risks": ai_result.get("risks", ""),
        "articles": articles,
        "news_sentiment": news_sentiment,
        "technical_data": technical_data,
        "fundamental_data": fundamental_data,
        "rebalance_action": ""  # Se llenará después
    }

def send_email_html(subject: str, html_body: str):
    """Envía email con formato HTML."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = TO_EMAIL
    msg.set_content("Por favor usa un cliente de email que soporte HTML.")
    msg.add_alternative(html_body, subtype="html")

    ctx = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls(context=ctx)
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

def main():
    print(f"Iniciando análisis de portfolio mejorado...")

    # Verificar ventana de envío
    if not should_send_now(SEND_LOCAL_TZ, SEND_AT_HHMM):
        print(f"Fuera de ventana de envío. Se envía a partir de {SEND_AT_HHMM} {SEND_LOCAL_TZ}.")
        return

    # Cargar portfolio
    portfolio_df = load_portfolio(CSV_URL)

    # Asegurarse de que exista la columna TargetWeight
    if "TargetWeight" not in portfolio_df.columns:
        # Si no existe, distribuir equitativamente
        portfolio_df["TargetWeight"] = 100.0 / len(portfolio_df)
        print("Nota: No se encontró columna 'TargetWeight', usando distribución equitativa.")

    tickers = portfolio_df["Ticker"].unique().tolist()

    # Obtener precios
    print("Obteniendo precios...")
    prices = {ticker: fetch_price(ticker) for ticker in tickers}

    # Procesar cada acción
    print("Analizando cada acción...")
    stocks_data = []

    for ticker in tickers:
        row = portfolio_df[portfolio_df["Ticker"] == ticker].iloc[0]
        stock_data = process_stock_data(ticker, row, prices, portfolio_df)
        stocks_data.append(stock_data)

    # Rebalancing (si está habilitado)
    rebalancing_actions = []
    if ENABLE_REBALANCING:
        print("Calculando recomendaciones de rebalanceo...")

        # Preparar datos técnicos y fundamentales
        tech_data_map = {s["ticker"]: s["technical_data"] for s in stocks_data}
        fund_data_map = {s["ticker"]: s["fundamental_data"] for s in stocks_data}

        rebalancing_actions, rebal_summary = generate_rebalancing_recommendation(
            holdings=portfolio_df,
            prices=prices,
            technical_data=tech_data_map,
            fundamental_data=fund_data_map
        )

        # Agregar acciones de rebalanceo a cada stock
        for action in rebalancing_actions:
            ticker = action["ticker"]
            for stock in stocks_data:
                if stock["ticker"] == ticker:
                    stock["rebalance_action"] = f"{action['action']} {action['qty']:.2f} acciones ({action['reason']})"
                    break

        print(f"Rebalanceo: {rebal_summary}")

    # Calcular resumen del portfolio
    total_value = sum(s["price"] * portfolio_df[portfolio_df["Ticker"] == s["ticker"]]["Qty"].iloc[0]
                     for s in stocks_data if s["price"] > 0)

    total_prev_value = sum(s["prev_close"] * portfolio_df[portfolio_df["Ticker"] == s["ticker"]]["Qty"].iloc[0]
                           for s in stocks_data if s["prev_close"] > 0)

    day_change = total_value - total_prev_value
    day_change_pct = (day_change / total_prev_value * 100) if total_prev_value > 0 else 0

    portfolio_summary = {
        "total_value": total_value,
        "day_change": day_change,
        "day_change_pct": day_change_pct
    }

    # Verificar si hay información para enviar
    total_news = sum(len(s["articles"]) for s in stocks_data)
    if total_news == 0 and not any(s["price"] > 0 for s in stocks_data):
        print("Sin noticias ni precios disponibles — no se envía email.")
        return

    # Generar HTML del email
    print("Generando email HTML...")
    timestamp = datetime.now(ZoneInfo(SEND_LOCAL_TZ)).strftime("%d/%m/%Y %H:%M")

    html_body = generate_email_html(
        stocks_data=stocks_data,
        rebalancing_actions=rebalancing_actions if ENABLE_REBALANCING else None,
        portfolio_summary=portfolio_summary,
        timestamp=timestamp
    )

    # Enviar email
    subject = f"Reporte de Portfolio — {timestamp}"
    send_email_html(subject, html_body)

    print(f"✓ Email enviado exitosamente a {TO_EMAIL}")
    print(f"  - {len(stocks_data)} acciones analizadas")
    print(f"  - {total_news} noticias procesadas")
    print(f"  - Portfolio: ${total_value:,.2f} ({day_change_pct:+.2f}%)")

if __name__ == "__main__":
    main()
