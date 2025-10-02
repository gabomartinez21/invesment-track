import os, smtplib, ssl
import pandas as pd
import yfinance as yf
from email.message import EmailMessage
from datetime import datetime

# -------- Config via environment (set as GitHub Actions secrets) --------
CSV_URL   = os.environ["SHEET_CSV_URL"]   # Google Sheet publicado como CSV
FROM_EMAIL= os.environ["FROM_EMAIL"]
TO_EMAIL  = os.environ["TO_EMAIL"]
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", FROM_EMAIL)
SMTP_PASS = os.environ["SMTP_PASS"]

def fmt(n):
    try:
        f = float(n)
        return f"{f:.2f}"
    except Exception:
        return "-"

def load_portfolio(url: str) -> pd.DataFrame:
    df = pd.read_csv(url)
    needed = ["Ticker","Qty","AvgCost","BuyBelow","SellAbove","Notes"]
    for col in needed:
        if col not in df.columns:
            raise ValueError(f"Falta columna: {col}")
    df["Ticker"] = df["Ticker"].astype(str).str.upper().str.strip()
    for c in ["Qty","AvgCost","BuyBelow","SellAbove"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    df["Notes"] = df.get("Notes","").fillna("")
    df = df[df["Ticker"]!=""]
    return df

def fetch_prices(tickers):
    tickers = list(sorted(set(tickers)))
    if not tickers:
        return {}
    data = yf.Tickers(" ".join(tickers))
    out = {}
    for t in tickers:
        try:
            info = data.tickers[t].info
        except Exception:
            info = {}
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        chg = info.get("regularMarketChangePercent")
        out[t] = {"price": float(price) if price else 0.0, "chg_pct": chg}
    return out

def evaluate(df: pd.DataFrame, prices: dict):
    rows, actions = [], []
    for _, r in df.iterrows():
        t = r["Ticker"]
        p = prices.get(t, {"price":0.0, "chg_pct":None})
        price = p["price"] or 0.0
        signal = "Mantener"
        if r["BuyBelow"] and price > 0 and price <= r["BuyBelow"]:
            signal = "Comprar"
        if r["SellAbove"] and price > 0 and price >= r["SellAbove"]:
            signal = "Vender"
        row = {
            "Ticker": t,
            "Qty": r["Qty"],
            "AvgCost": r["AvgCost"],
            "BuyBelow": r["BuyBelow"],
            "SellAbove": r["SellAbove"],
            "Notes": r["Notes"],
            "Price": price,
            "ChangePct": p["chg_pct"],
            "Signal": signal,
        }
        rows.append(row)
        if signal != "Mantener":
            actions.append(row)
    return rows, actions

def build_email(rows, actions):
    def line(e):
        extra = f" — {e['Notes']}" if e['Notes'] else ""
        return f"• {e['Ticker']}: ${fmt(e['Price'])} | Avg ${fmt(e['AvgCost'])} | Buy≤{fmt(e['BuyBelow'])} | Sell≥{fmt(e['SellAbove'])} → {e['Signal']}{extra}"
    summary = "\n".join(line(e) for e in rows)

    if actions:
        acts = []
        for a in actions:
            thr = f"≤{fmt(a['BuyBelow'])}" if a["Signal"]=="Comprar" else f"≥{fmt(a['SellAbove'])}"
            acts.append(f"- {a['Ticker']}: {a['Signal']} a ${fmt(a['Price'])} (umbral {thr})")
        actions_md = "\n".join(acts)
        conclusions = []
        buys = len([a for a in actions if a["Signal"]=="Comprar"])
        sells = len([a for a in actions if a["Signal"]=="Vender"])
        if buys: conclusions.append(f"{buys} activo(s) en zona de COMPRA")
        if sells: conclusions.append(f"{sells} activo(s) en zona de VENTA")
    else:
        actions_md = "- Ninguna por ahora"
        conclusions = ["Sin señales de compra/venta. Mantener y monitorear."]

    today = datetime.now().strftime("%d/%m/%Y")
    body = (
        f"**Resumen de Portafolio**\n\n{summary}\n\n"
        f"**Acciones sugeridas**\n{actions_md}\n\n"
        f"**Conclusiones**\n" + "\n".join(f"- {c}" for c in conclusions)
    )
    subject = f"Señales del portafolio – {today}"
    return subject, body

def send_email(subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = TO_EMAIL
    msg.set_content(body)  # texto plano

    ctx = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls(context=ctx)
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

def main():
    df = load_portfolio(CSV_URL)
    prices = fetch_prices(df["Ticker"].tolist())
    rows, actions = evaluate(df, prices)
    if not actions:
        print("Sin señales — no se envía email.")
        return
    subject, body = build_email(rows, actions)
    send_email(subject, body)
    print("Email enviado.")

if __name__ == "__main__":
    main()
