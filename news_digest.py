import os, ssl, smtplib, html, requests, feedparser
import pandas as pd
import yfinance as yf
from email.message import EmailMessage
from datetime import datetime
from openai import OpenAI

# Secrets / env
CSV_URL    = os.environ["SHEET_CSV_URL"]   # misma hoja de acciones
FROM_EMAIL = os.environ["FROM_EMAIL"]
TO_EMAIL   = os.environ["TO_EMAIL"]
SMTP_HOST  = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT  = int(os.environ.get("SMTP_PORT", "587") or "587")
SMTP_USER  = os.environ.get("SMTP_USER", FROM_EMAIL)
SMTP_PASS  = os.environ["SMTP_PASS"]
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
MAX_ARTICLES_PER_TICKER = int(os.environ.get("MAX_ARTICLES_PER_TICKER", "4"))

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def load_portfolio(url: str) -> pd.DataFrame:
    df = pd.read_csv(url, sep=None, engine="python")
    if "Ticker" not in df.columns:
        raise ValueError("Falta columna: Ticker")
    df["Ticker"] = df["Ticker"].astype(str).str.upper().str.strip()
    return df[df["Ticker"]!=""]

def get_company_name(ticker: str) -> str:
    try:
        info = yf.Ticker(ticker).info or {}
        return info.get("shortName") or info.get("longName") or ticker
    except Exception:
        return ticker

def fetch_price(ticker: str) -> float:
    try:
        t = yf.Ticker(ticker)
        price = None
        fi = getattr(t, "fast_info", None) or {}
        price = fi.get("last_price") or fi.get("last_price_raw")
        if not price:
            info = t.info or {}
            price = info.get("regularMarketPrice") or info.get("currentPrice")
        if not price:
            hist = t.history(period="1d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
        return float(price or 0.0)
    except Exception:
        return 0.0

def google_news_feed(query: str, lang="es-419", gl="PE"):
    q = requests.utils.quote(f'{query} when:1d')  # últimas 24h
    return f"https://news.google.com/rss/search?q={q}&hl={lang}&gl={gl}&ceid=PE:es-419"

def fetch_headlines_for(ticker: str, company: str):
    url = google_news_feed(f'{ticker} OR "{company}"')
    feed = feedparser.parse(url)
    items = []
    for e in feed.entries[:MAX_ARTICLES_PER_TICKER]:
        title = html.unescape(getattr(e, "title", "")).strip()
        link  = getattr(e, "link", "")
        source= getattr(e, "source", {}).get("title") if hasattr(e, "source") else None
        summary = html.unescape(getattr(e, "summary", "")).strip()
        published = getattr(e, "published", "")
        items.append({"title": title, "link": link, "source": source or "", "summary": summary, "published": published})
    return items

def filter_articles(articles: list):
    """
    Filtra titulares irrelevantes/ruidosos (p. ej., patrocinados u opinión).
    Mantiene el mismo formato de diccionarios de fetch_headlines_for.
    """
    BAD_TOKENS = ("patrocinado", "sponsored", "opinión", "opinion", "op-ed", "advertorial")
    out = []
    for a in articles:
        title = (a.get("title") or "").lower()
        if any(tok in title for tok in BAD_TOKENS):
            continue
        out.append(a)
    return out


def build_llm_digest(ticker: str, company: str, price: float, articles: list):
    bullets = [f"- {a['title']} ({a['source']}) — {a['link']}" for a in articles] or ["- (Sin titulares relevantes en las últimas 24h)"]
    news_block = "\n".join(bullets)
    prompt = f"""
Eres un analista financiero. Resume en español, en tono ejecutivo:

Contexto:
- Ticker: {ticker}
- Empresa: {company}
- Precio aprox actual: ${price:.2f}

Titulares (últimas 24h):
{news_block}

Entregables (máximo 140-170 palabras):
1) Resumen del día (1 párrafo).
2) Recomendación del día: Compra / Mantener / Vender (elige solo una) + razón breve.
3) Riesgos o catalizadores próximos (bullet corto si aplica).

Responde en Markdown y menciona la fuente entre paréntesis.
"""
    r = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role":"user","content":prompt}],
        temperature=0.5,
    )
    return r.choices[0].message.content.strip()

def send_email(subject: str, body: str):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = TO_EMAIL
    msg.set_content(body)
    ctx = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls(context=ctx)
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

def main():
    df = load_portfolio(CSV_URL)
    tickers = df["Ticker"].unique().tolist()
    sections = []
    total_relevant_news = 0
    for t in tickers:
        company = get_company_name(t)
        price = fetch_price(t)
        news = filter_articles(news)
        total_relevant_news += len(news)
        digest = build_llm_digest(t, company, price, news)
        sections.append(f"### {t} — {company} (≈ ${price:.2f})\n{digest}")

    # Anti-spam: sólo enviar si hubo al menos 1 titular relevante
    if total_relevant_news == 0:
        print("Sin titulares relevantes en las últimas 24h — no se envía email.")
        return

    today = datetime.now().strftime("%d/%m/%Y")
    header = f"# Noticias y Recomendación del Día — {today}\n\n"
    body = header + "\n\n---\n\n".join(sections)
    send_email(f"Noticias y señal diaria — {today}", body)
    print("Email enviado.")

if __name__ == "__main__":
    main()