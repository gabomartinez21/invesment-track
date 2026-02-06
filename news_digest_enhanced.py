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
import time
import pandas as pd
from email.message import EmailMessage
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, List

from dotenv import load_dotenv

# Importar módulos creados
from analysis import (
    get_technical_analysis,
    get_fundamental_data,
    interpret_technical_signals,
    interpret_fundamental_signals,
)
from portfolio import calculate_portfolio_values, generate_rebalancing_recommendation
from news_sources import aggregate_news_from_all_sources, calculate_news_sentiment
from ai_analysis import get_ai_analysis
from email_template import generate_email_html
from prices import fetch_prev_close, fetch_quotes_batch, get_company_name

# Configuración
load_dotenv()

REQUIRED_ENV_VARS = [
    "SHEET_CSV_URL",
    "FROM_EMAIL",
    "TO_EMAIL",
    "SMTP_PASS",
    "OPENAI_API_KEY",
]
missing_vars = [var for var in REQUIRED_ENV_VARS if not os.environ.get(var)]
if missing_vars:
    missing_list = ", ".join(missing_vars)
    raise RuntimeError(
        "Faltan variables de entorno requeridas. "
        f"Configura estas claves en tu .env: {missing_list}"
    )

CSV_URL = os.environ["SHEET_CSV_URL"]
FROM_EMAIL = os.environ["FROM_EMAIL"]
TO_EMAIL = os.environ["TO_EMAIL"]
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587") or "587")
SMTP_USER = os.environ.get("SMTP_USER", FROM_EMAIL)
SMTP_PASS = os.environ["SMTP_PASS"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
SEND_LOCAL_TZ = os.environ.get("SEND_LOCAL_TZ", "America/Lima")
SEND_AT_HHMM = os.environ.get("SEND_AT_HHMM", "08:45")
MAX_ARTICLES_PER_SOURCE = int(os.environ.get("MAX_ARTICLES_PER_SOURCE", "3"))
MARKETAUX_API_KEY = os.environ.get("MARKETAUX_API_KEY", None)  # Opcional

# Portfolio rebalancing
ENABLE_REBALANCING = os.environ.get("ENABLE_REBALANCING", "true").lower() == "true"
MIN_TRADE_VALUE = float(os.environ.get("MIN_TRADE_VALUE", "100"))
MAX_DEVIATION = float(os.environ.get("MAX_DEVIATION", "5"))


def load_portfolio(url: str) -> pd.DataFrame:
    """Carga el portfolio desde CSV (Google Sheet publicado).

    Columnas soportadas (recomendadas):
    - Ticker (requerida)
    - Shares o Qty (cantidad)
    - AvgCost (costo promedio por acción, opcional)
    - TargetWeight (peso objetivo %, opcional)
    - Cash (monto de caja si Ticker=CASH/CASH_USD)
    - Active (TRUE/FALSE para incluir)
    - Notes (comentarios)

    Nota: Internamente normalizamos a columna `Qty`.
    """
    df = pd.read_csv(url, sep=None, engine="python")
    if "Ticker" not in df.columns:
        raise ValueError("Falta columna: Ticker")

    df = df.copy()
    df["Ticker"] = df["Ticker"].astype(str).str.upper().str.strip()
    df = df[df["Ticker"] != ""]

    # Active
    if "Active" not in df.columns:
        df["Active"] = True
    else:
        df["Active"] = (
            df["Active"]
            .astype(str)
            .str.strip()
            .str.lower()
            .isin(["true", "1", "yes", "y", "si", "sí"])
        )

    # Notes
    if "Notes" not in df.columns:
        df["Notes"] = ""
    df["Notes"] = df["Notes"].astype(str)

    # Cash
    if "Cash" not in df.columns:
        df["Cash"] = 0.0
    df["Cash"] = pd.to_numeric(df["Cash"], errors="coerce").fillna(0.0)

    # Qty/Shares
    if "Qty" not in df.columns:
        if "Shares" in df.columns:
            df["Qty"] = df["Shares"]
        else:
            df["Qty"] = 0.0
    df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce").fillna(0.0)

    # AvgCost
    if "AvgCost" not in df.columns:
        df["AvgCost"] = 0.0
    df["AvgCost"] = pd.to_numeric(df["AvgCost"], errors="coerce").fillna(0.0)

    # TargetWeight
    if "TargetWeight" in df.columns:
        df["TargetWeight"] = pd.to_numeric(df["TargetWeight"], errors="coerce").fillna(
            0.0
        )

    return df[df["Active"] == True]


def should_send_now(tz_name: str, hhmm: str) -> bool:
    """Solo envía si la hora local es igual o posterior a HH:MM."""
    try:
        hh, mm = hhmm.split(":")
        target_h = int(hh)
        target_m = int(mm)
    except Exception:
        target_h, target_m = 8, 45
    now = datetime.now(ZoneInfo(tz_name))
    if now.hour > target_h:
        return True
    if now.hour == target_h and now.minute >= target_m:
        return True
    return False


def extract_cash(df: pd.DataFrame) -> float:
    """Extrae caja desde filas especiales (Ticker=CASH/CASH_USD) usando columna Cash."""
    try:
        cash_rows = df[df["Ticker"].isin(["CASH", "CASH_USD"])]
        return float(cash_rows["Cash"].sum()) if not cash_rows.empty else 0.0
    except Exception:
        return 0.0


def compute_position_metrics(
    qty: float, avg_cost: float, price: float
) -> Dict[str, float]:
    qty = float(qty or 0.0)
    avg_cost = float(avg_cost or 0.0)
    price = float(price or 0.0)
    value = qty * price if qty > 0 and price > 0 else 0.0
    cost = qty * avg_cost if qty > 0 and avg_cost > 0 else 0.0
    pnl = (value - cost) if (value > 0 and cost > 0) else 0.0
    pnl_pct = (pnl / cost * 100.0) if cost > 0 else 0.0
    return {
        "qty": qty,
        "avg_cost": avg_cost,
        "value": value,
        "cost": cost,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
    }


def process_stock_data(
    ticker: str,
    row: pd.Series,
    prices: Dict[str, float],
    prev_closes: Dict[str, float],
    portfolio_df: pd.DataFrame,
    cash_available: float,
    total_portfolio_value: float,
) -> Dict:
    """
    Procesa toda la información de una acción: precio, noticias, análisis técnico/fundamental.
    """
    print(f"Procesando {ticker}...")

    # Información básica
    company = get_company_name(ticker)
    price = prices.get(ticker, 0.0)
    prev_close = prev_closes.get(ticker)
    if prev_close is None:
        prev_close = fetch_prev_close(ticker)

    # Cambio porcentual
    change_pct = 0.0
    if price > 0 and prev_close > 0:
        change_pct = ((price - prev_close) / prev_close) * 100.0

    # Contexto de portfolio (para personalizar análisis + rebalancing)
    qty = float(row.get("Qty", 0) or 0.0)
    avg_cost = float(row.get("AvgCost", 0) or 0.0)
    pos = compute_position_metrics(qty, avg_cost, price)

    current_weight = (
        (pos["value"] / total_portfolio_value * 100.0)
        if total_portfolio_value > 0
        else 0.0
    )
    target_weight = (
        float(row.get("TargetWeight", 0) or 0.0) if "TargetWeight" in row.index else 0.0
    )

    portfolio_context = {
        "quantity": pos["qty"],
        "avg_cost": pos["avg_cost"],
        "position_value": pos["value"],
        "position_cost": pos["cost"],
        "pnl": pos["pnl"],
        "pnl_pct": pos["pnl_pct"],
        "current_weight": current_weight,
        "target_weight": target_weight,
        "cash_available": float(cash_available or 0.0),
        "notes": str(row.get("Notes", "") or ""),
    }

    # Análisis técnico
    technical_data = get_technical_analysis(ticker)
    tech_signals = interpret_technical_signals(technical_data, price)

    # Análisis fundamental
    fundamental_data = get_fundamental_data(ticker)
    fund_signals = interpret_fundamental_signals(fundamental_data, price)

    # Noticias de múltiples fuentes
    articles = aggregate_news_from_all_sources(
        ticker,
        company,
        max_per_source=MAX_ARTICLES_PER_SOURCE,
        marketaux_api_key=MARKETAUX_API_KEY,
    )
    news_sentiment = calculate_news_sentiment(articles)

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
        api_key=OPENAI_API_KEY,
    )

    return {
        "ticker": ticker,
        "company": company,
        "price": price,
        "prev_close": prev_close,
        "change_pct": change_pct,
        "quantity": pos.get("qty", 0.0),
        "avg_cost": pos.get("avg_cost", 0.0),
        "position_value": pos.get("value", 0.0),
        "pnl": pos.get("pnl", 0.0),
        "pnl_pct": pos.get("pnl_pct", 0.0),
        "current_weight": portfolio_context.get("current_weight", 0.0)
        if portfolio_context
        else 0.0,
        "target_weight": portfolio_context.get("target_weight", 0.0)
        if portfolio_context
        else 0.0,
        "recommendation": ai_result.get("recommendation", "MANTENER"),
        "news_summary": ai_result.get("full_text", "Sin análisis disponible"),
        "technical_summary": tech_signals.get("summary", ""),
        "fundamental_summary": fund_signals.get("summary", ""),
        "risks": ai_result.get("risks", ""),
        "articles": articles,
        "news_sentiment": news_sentiment,
        "technical_data": technical_data,
        "fundamental_data": fundamental_data,
        "rebalance_action": "",  # Se llenará después
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

    # Verificar ventana de envío (comentado para testing)
    # if not should_send_now(SEND_LOCAL_TZ, SEND_AT_HHMM):
    #     print(f"Fuera de ventana de envío. Se envía a partir de {SEND_AT_HHMM} {SEND_LOCAL_TZ}.")
    #     return

    # Cargar portfolio
    portfolio_df = load_portfolio(CSV_URL)

    cash_available = extract_cash(portfolio_df)

    # Excluir filas de caja del análisis de tickers
    positions_df = portfolio_df[
        ~portfolio_df["Ticker"].isin(["CASH", "CASH_USD"])
    ].copy()

    if "Qty" not in positions_df.columns:
        positions_df["Qty"] = 0.0

    # Asegurarse de que exista la columna TargetWeight
    if "TargetWeight" not in positions_df.columns:
        # Si no existe, distribuir equitativamente SOLO entre posiciones
        positions_df["TargetWeight"] = 100.0 / max(len(positions_df), 1)
        print(
            "Nota: No se encontró columna 'TargetWeight', usando distribución equitativa."
        )

    tickers = positions_df["Ticker"].unique().tolist()

    # Obtener precios
    print("Obteniendo precios...")
    quotes = fetch_quotes_batch(tickers)
    prices = {
        ticker: (quotes.get(ticker, {}).get("price") or 0.0) for ticker in tickers
    }
    prev_closes = {
        ticker: quotes.get(ticker, {}).get("prev_close") for ticker in tickers
    }

    total_portfolio_value = sum(
        (prices.get(t, 0.0) or 0.0)
        * float(positions_df[positions_df["Ticker"] == t]["Qty"].iloc[0] or 0.0)
        for t in tickers
        if (prices.get(t, 0.0) or 0.0) > 0
    )

    # Procesar cada acción
    print("Analizando cada acción...")
    stocks_data = []

    for idx, ticker in enumerate(tickers):
        row = positions_df[positions_df["Ticker"] == ticker].iloc[0]
        stock_data = process_stock_data(
            ticker,
            row,
            prices,
            prev_closes,
            positions_df,
            cash_available,
            total_portfolio_value,
        )
        stocks_data.append(stock_data)

        # Delay para evitar rate limit de Yahoo Finance (excepto en la última)
        if idx < len(tickers) - 1:
            time.sleep(8)  # 8 segundos entre requests

    # Rebalancing (si está habilitado)
    rebalancing_actions = []
    if ENABLE_REBALANCING:
        print("Calculando recomendaciones de rebalanceo...")

        # Preparar datos técnicos y fundamentales
        tech_data_map = {s["ticker"]: s["technical_data"] for s in stocks_data}
        fund_data_map = {s["ticker"]: s["fundamental_data"] for s in stocks_data}

        rebalancing_actions, rebal_summary = generate_rebalancing_recommendation(
            holdings=positions_df,
            prices=prices,
            technical_data=tech_data_map,
            fundamental_data=fund_data_map,
        )

        # Agregar acciones de rebalanceo a cada stock
        for action in rebalancing_actions:
            ticker = action["ticker"]
            for stock in stocks_data:
                if stock["ticker"] == ticker:
                    stock["rebalance_action"] = (
                        f"{action['action']} {action['qty']:.2f} acciones ({action['reason']})"
                    )
                    break

        print(f"Rebalanceo: {rebal_summary}")

    # Calcular resumen del portfolio
    total_value = sum(
        s["price"]
        * float(
            positions_df[positions_df["Ticker"] == s["ticker"]]["Qty"].iloc[0] or 0.0
        )
        for s in stocks_data
        if s["price"] > 0
    )

    total_prev_value = sum(
        s["prev_close"]
        * float(
            positions_df[positions_df["Ticker"] == s["ticker"]]["Qty"].iloc[0] or 0.0
        )
        for s in stocks_data
        if s["prev_close"] > 0
    )

    day_change = total_value - total_prev_value
    day_change_pct = (
        (day_change / total_prev_value * 100) if total_prev_value > 0 else 0
    )

    portfolio_summary = {
        "total_value": total_value,
        "cash_available": float(cash_available or 0.0),
        "net_worth": float(total_value + (cash_available or 0.0)),
        "day_change": day_change,
        "day_change_pct": day_change_pct,
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
        timestamp=timestamp,
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
