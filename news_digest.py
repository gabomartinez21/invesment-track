import os, ssl, smtplib, html, requests, feedparser
import pandas as pd
import yfinance as yf
from email.message import EmailMessage
from datetime import datetime
from zoneinfo import ZoneInfo
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
SEND_LOCAL_TZ = os.environ.get("SEND_LOCAL_TZ", "America/Lima")
SEND_AT_HHMM  = os.environ.get("SEND_AT_HHMM", "08:45")  # formato 24h HH:MM

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

def fetch_price_yahoo_http(ticker: str) -> float:
    """
    Fallback por HTTP directo a Yahoo Finance quote API.
    """
    try:
        url = "https://query1.finance.yahoo.com/v7/finance/quote"
        resp = requests.get(url, params={"symbols": ticker}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        result = ((data or {}).get("quoteResponse") or {}).get("result") or []
        if result:
            q = result[0]
            for k in ("regularMarketPrice", "postMarketPrice", "preMarketPrice"):
                v = q.get(k)
                if v is not None:
                    return float(v)
    except Exception:
        pass
    return 0.0

def fetch_price(ticker: str) -> float:
    """
    Intenta obtener el precio actual del ticker con varios métodos,
    devolviendo 0.0 solo si todos fallan.
    """
    try:
        t = yf.Ticker(ticker)
        price = None

        # 1) fast_info
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

def google_news_feed(query: str, lang="es-419", gl="PE"):
    q = requests.utils.quote(f'{query} when:1d')  # últimas 24h
    return f"https://news.google.com/rss/search?q={q}&hl={lang}&gl={gl}&ceid=PE:es-419"

def fetch_headlines_for(ticker: str, company: str):
    # Desambiguación y sesgo financiero para evitar ruido (ej. APP en Perú, SoFi Stadium, etc.)
    positive_terms = [
        "stock", "acciones", "share", "shares", "earnings", "resultados", "guidance",
        "revenue", "ingresos", "EPS", "SEC", "NYSE", "NASDAQ", "dividend", "dividendo",
        "quarter", "Q1", "Q2", "Q3", "Q4", "rating", "downgrade", "upgrade"
    ]
    negative_terms = [
        '"SoFi Stadium"', "estadio SoFi", '"Alianza para el Progreso"', "APP Perú",
        "partido político", "fútbol", "Liga 1", "selección peruana"
    ]
    # Reglas específicas por ticker (desambiguación de nombre)
    ticker_alias = {
        "APP": ["AppLovin"],
        "SOFI": ["SoFi Technologies"],
        # "V": ["Visa Inc"],
        "GE": ["General Electric"],
        # "PG": ["Procter & Gamble"],
        "MSFT": ["Microsoft"],
        "AAPL": ["Apple"],
        "AMZN": ["Amazon"],
        "JNJ": ["Johnson & Johnson"],
        "MU": ["Micron Technology, Inc. - Common Stock"],
        "GOOGL": ["Alphabet", "Google"],
        "SPYG": ["SPDR Portfolio S&amp;P 500 Growth", "S&amp;P 500 Growth"],
        "VOO": ["Vanguard S&amp;P 500 ETF"]
    }
    musts = [ticker, f'"{company}"'] + [f'"{a}"' for a in ticker_alias.get(ticker, [])]
    positives = " OR ".join(positive_terms)
    negatives = " ".join([f'-{t}' for t in negative_terms])
    composed = f'({" OR ".join(musts)}) ({positives}) {negatives}'
    url = google_news_feed(composed)
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

def filter_articles(articles: list, ticker: str, company: str):
    """
    Filtra titulares irrelevantes/ruidosos:
    - Excluye patrocinados/opinión
    - Excluye deportes/entretenimiento/estadios
    - Requiere que el título o resumen mencione el ticker, la empresa o términos financieros clave
    """
    BAD_TOKENS = ("patrocinado", "sponsored", "opinión", "opinion", "op-ed", "advertorial")
    NOISE_TOKENS = ("SoFi Stadium", "estadio SoFi", "fútbol", "partido político", "celebridad")
    FINANCE_HINTS = ("earnings", "resultados", "guidance", "ingresos", "revenue", "EPS",
                     "dividend", "dividendo", "rating", "NASDAQ", "NYSE", "SEC", "acciones", "acciones de")
    out = []
    t_low = (ticker or "").lower()
    c_low = (company or "").lower()
    for a in articles:
        title = (a.get("title") or "")
        summ  = (a.get("summary") or "")
        lt = title.lower()
        ls = summ.lower()
        if any(tok in lt for tok in BAD_TOKENS):
            continue
        if any(tok.lower() in lt for tok in NOISE_TOKENS):
            continue
        has_entity = (t_low in lt) or (c_low in lt) or (t_low in ls) or (c_low in ls)
        has_fin = any(h in lt or h in ls for h in FINANCE_HINTS)
        if has_entity or has_fin:
            out.append(a)
    return out
def fetch_prev_close(ticker: str) -> float:
    """
    Obtiene el precio de cierre del día anterior. Intenta con yfinance (history) y
    si falla devuelve 0.0.
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
    return 0.0

def should_send_now(tz_name: str, hhmm: str) -> bool:
    """
    Solo envía si la hora local es igual o posterior a HH:MM en el día actual.
    """
    try:
        hh, mm = hhmm.split(":")
        target_h = int(hh); target_m = int(mm)
    except Exception:
        target_h, target_m = 8, 45
    now = datetime.now(ZoneInfo(tz_name))
    if now.hour > target_h:
        return True
    if now.hour == target_h and now.minute >= target_m:
        return True
    return False


def build_llm_digest(ticker: str, company: str, price: float, prev_close: float, articles: list):
    bullets = [f"- {a['title']} ({a['source']}) — {a['link']}" for a in articles] or ["- (Sin titulares relevantes en las últimas 24h)"]
    news_block = "\n".join(bullets)
    price_line = "N/D" if price <= 0 else f"${price:.2f}"
    prev_line  = "N/D" if prev_close <= 0 else f"${prev_close:.2f}"
    delta = ""
    if price > 0 and prev_close > 0:
        pct = ((price - prev_close) / prev_close) * 100.0
        delta = f"{pct:+.2f}% intradía"
    prompt = f"""
Eres un analista financiero. Resume en español, en tono ejecutivo y **NO inventes**.

Contexto:
- Ticker: {ticker}
- Empresa: {company}
- Precio actual: {price_line}
- Cierre previo: {prev_line}
- Variación: {delta or "N/D"}

Titulares (últimas 24h):
{news_block}

Instrucciones estrictas:
- Si no hay titulares relevantes, enfócate en la acción del precio (precio actual vs cierre previo).
- Si algún precio es N/D, dilo explícitamente y evita conclusiones basadas en datos faltantes.
- Sé conciso (140–170 palabras en total).
- No incluyas enlaces en el resumen, solo mención de la fuente entre paréntesis.

Entregables:
1) Resumen del día (1 párrafo).
2) Recomendación del día: Compra / Mantener / Vender (elige solo una) + razón breve.
3) Riesgos o catalizadores próximos (bullet corto si aplica).
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
    # Ventana de envío opcional (ej. 08:45 America/Lima)
    if not should_send_now(SEND_LOCAL_TZ, SEND_AT_HHMM):
        print(f"Fuera de ventana de envío. Se envía a partir de {SEND_AT_HHMM} {SEND_LOCAL_TZ}.")
        return
    df = load_portfolio(CSV_URL)
    tickers = df["Ticker"].unique().tolist()
    sections = []
    total_relevant_news = 0; any_price_available = False
    for t in tickers:
        company = get_company_name(t)
        price = fetch_price(t)
        any_price_available = any_price_available or (price > 0)
        prev_close = fetch_prev_close(t)
        news = fetch_headlines_for(t, company)
        news = filter_articles(news, t, company)
        total_relevant_news += len(news)
        digest = build_llm_digest(t, company, price, prev_close, news)
        price_str = "N/D" if price <= 0 else f"${price:.2f}"
        prev_str  = "N/D" if prev_close <= 0 else f"${prev_close:.2f}"
        delta_str = ""
        if price > 0 and prev_close > 0:
            pct = ((price - prev_close) / prev_close) * 100.0
            delta_str = f" | Prev: {prev_str} | Δ {pct:+.2f}%"
        section_title = f"### {t} — {company} (≈ {price_str}{delta_str})"
        sections.append(f"{section_title}\n{digest}")

    # Enviar si hubo noticias o si hubo al menos un precio disponible (para decisión de inversión)
    if total_relevant_news == 0 and not any_price_available:
        print("Sin titulares relevantes y sin precios disponibles — no se envía email.")
        return

    today = datetime.now(ZoneInfo(SEND_LOCAL_TZ)).strftime("%d/%m/%Y %H:%M")
    header = f"# Noticias y Recomendación del Día — {today}\n\n"
    body = header + "\n\n---\n\n".join(sections)
    send_email(f"Noticias y señal diaria — {today}", body)
    print("Email enviado.")

if __name__ == "__main__":
    main()