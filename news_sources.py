"""
Módulo para agregación de noticias de múltiples fuentes.
Mejora la confiabilidad combinando Google News, Yahoo Finance y otras fuentes.
"""

import requests
import feedparser
import html
import time
from typing import List, Dict
from datetime import datetime, timedelta


def google_news_feed(query: str, lang="es-419", gl="PE") -> str:
    """Genera URL de Google News RSS para una búsqueda."""
    q = requests.utils.quote(f"{query} when:1d")
    return f"https://news.google.com/rss/search?q={q}&hl={lang}&gl={gl}&ceid=PE:es-419"


def fetch_google_news(ticker: str, company: str, max_articles: int = 4) -> List[Dict]:
    """
    Obtiene noticias de Google News con filtros financieros.
    """
    positive_terms = [
        "stock",
        "acciones",
        "share",
        "shares",
        "earnings",
        "resultados",
        "guidance",
        "revenue",
        "ingresos",
        "EPS",
        "SEC",
        "NYSE",
        "NASDAQ",
        "dividend",
        "dividendo",
        "quarter",
        "Q1",
        "Q2",
        "Q3",
        "Q4",
        "rating",
        "downgrade",
        "upgrade",
    ]
    negative_terms = [
        '"SoFi Stadium"',
        "estadio SoFi",
        '"Alianza para el Progreso"',
        "APP Perú",
        "partido político",
        "fútbol",
        "Liga 1",
        "selección peruana",
    ]

    ticker_alias = {
        "APP": ["AppLovin"],
        "SOFI": ["SoFi Technologies"],
        "GE": ["General Electric"],
        "MSFT": ["Microsoft"],
        "AAPL": ["Apple"],
        "AMZN": ["Amazon"],
        "JNJ": ["Johnson & Johnson"],
        "MU": ["Micron Technology"],
        "GOOGL": ["Alphabet", "Google"],
        "SPYG": ["SPDR Portfolio S&P 500 Growth"],
        "VOO": ["Vanguard S&P 500 ETF"],
    }

    musts = [ticker, f'"{company}"'] + [f'"{a}"' for a in ticker_alias.get(ticker, [])]
    positives = " OR ".join(positive_terms)
    negatives = " ".join([f"-{t}" for t in negative_terms])
    composed = f"({' OR '.join(musts)}) ({positives}) {negatives}"

    url = google_news_feed(composed)

    try:
        feed = feedparser.parse(url)
        items = []

        for e in feed.entries[:max_articles]:
            title = html.unescape(getattr(e, "title", "")).strip()
            link = getattr(e, "link", "")
            source = (
                getattr(e, "source", {}).get("title")
                if hasattr(e, "source")
                else "Google News"
            )
            summary = html.unescape(getattr(e, "summary", "")).strip()
            published = getattr(e, "published", "")

            items.append(
                {
                    "title": title,
                    "link": link,
                    "source": source or "Google News",
                    "summary": summary,
                    "published": published,
                    "feed": "google_news",
                }
            )

        return items
    except Exception as e:
        print(f"Error fetching Google News for {ticker}: {e}")
        return []


def fetch_yahoo_finance_news(
    ticker: str, max_articles: int = 3, max_retries: int = 3
) -> List[Dict]:
    """
    Obtiene noticias directamente de Yahoo Finance para un ticker.
    """
    for attempt in range(max_retries):
        try:
            import yfinance as yf

            t = yf.Ticker(ticker)
            news = t.news or []

            items = []
            for article in news[:max_articles]:
                items.append(
                    {
                        "title": article.get("title", ""),
                        "link": article.get("link", ""),
                        "source": article.get("publisher", "Yahoo Finance"),
                        "summary": article.get("summary", ""),
                        "published": datetime.fromtimestamp(
                            article.get("providerPublishTime", 0)
                        ).isoformat()
                        if article.get("providerPublishTime")
                        else "",
                        "feed": "yahoo_finance",
                    }
                )

            return items
        except Exception as e:
            if "Too Many Requests" in str(e) or "Rate limit" in str(e):
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3
                    print(f"Rate limit para {ticker} (news), esperando {wait_time}s...")
                    time.sleep(wait_time)
                    continue
            print(f"Error fetching Yahoo Finance news for {ticker}: {e}")
            break

    return []


def fetch_marketaux_news(
    ticker: str, api_key: str = None, max_articles: int = 3
) -> List[Dict]:
    """
    Obtiene noticias de MarketAux (alternativa premium).
    Requiere API key (gratis limitado): https://www.marketaux.com/
    """
    if not api_key:
        return []

    try:
        url = "https://api.marketaux.com/v1/news/all"
        params = {
            "symbols": ticker,
            "filter_entities": "true",
            "language": "en",
            "api_token": api_key,
            "limit": max_articles,
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        items = []
        for article in data.get("data", [])[:max_articles]:
            items.append(
                {
                    "title": article.get("title", ""),
                    "link": article.get("url", ""),
                    "source": article.get("source", "MarketAux"),
                    "summary": article.get("description", ""),
                    "published": article.get("published_at", ""),
                    "sentiment": article.get("sentiment", "neutral"),
                    "feed": "marketaux",
                }
            )

        return items
    except Exception as e:
        print(f"Error fetching MarketAux news for {ticker}: {e}")
        return []


def filter_relevant_articles(
    articles: List[Dict], ticker: str, company: str
) -> List[Dict]:
    """
    Filtra artículos irrelevantes o spam.
    """
    BAD_TOKENS = (
        "patrocinado",
        "sponsored",
        "opinión",
        "opinion",
        "op-ed",
        "advertorial",
    )
    NOISE_TOKENS = (
        "SoFi Stadium",
        "estadio SoFi",
        "fútbol",
        "partido político",
        "celebridad",
    )
    FINANCE_HINTS = (
        "earnings",
        "resultados",
        "guidance",
        "ingresos",
        "revenue",
        "EPS",
        "dividend",
        "dividendo",
        "rating",
        "NASDAQ",
        "NYSE",
        "SEC",
        "acciones",
        "stock",
        "shares",
        "quarter",
        "Q1",
        "Q2",
        "Q3",
        "Q4",
    )

    out = []
    t_low = (ticker or "").lower()
    c_low = (company or "").lower()

    for a in articles:
        title = a.get("title") or ""
        summ = a.get("summary") or ""
        lt = title.lower()
        ls = summ.lower()

        # Filtrar patrocinados y ruido
        if any(tok in lt for tok in BAD_TOKENS):
            continue
        if any(tok.lower() in lt for tok in NOISE_TOKENS):
            continue

        # Verificar relevancia
        has_entity = (t_low in lt) or (c_low in lt) or (t_low in ls) or (c_low in ls)
        has_fin = any(h.lower() in lt or h.lower() in ls for h in FINANCE_HINTS)

        if has_entity or has_fin:
            out.append(a)

    return out


def aggregate_news_from_all_sources(
    ticker: str, company: str, max_per_source: int = 3, marketaux_api_key: str = None
) -> List[Dict]:
    """
    Agrega noticias de todas las fuentes disponibles y elimina duplicados.
    """
    all_articles = []

    # Google News
    google_articles = fetch_google_news(ticker, company, max_per_source)
    all_articles.extend(google_articles)

    # Yahoo Finance (deshabilitado para evitar rate limit)
    # yahoo_articles = fetch_yahoo_finance_news(ticker, max_per_source)
    # all_articles.extend(yahoo_articles)

    # MarketAux (si hay API key)
    if marketaux_api_key:
        marketaux_articles = fetch_marketaux_news(
            ticker, marketaux_api_key, max_per_source
        )
        all_articles.extend(marketaux_articles)

    # Filtrar relevantes
    filtered = filter_relevant_articles(all_articles, ticker, company)

    # Eliminar duplicados por título similar
    unique_articles = []
    seen_titles = set()

    for article in filtered:
        title_normalized = (
            article.get("title", "").lower().strip()[:50]
        )  # Primeros 50 chars
        if title_normalized and title_normalized not in seen_titles:
            seen_titles.add(title_normalized)
            unique_articles.append(article)

    # Ordenar por fecha (más reciente primero)
    unique_articles.sort(key=lambda x: x.get("published", ""), reverse=True)

    return unique_articles[: max_per_source * 2]  # Máximo total


def calculate_news_sentiment(articles: List[Dict]) -> Dict[str, any]:
    """
    Calcula el sentimiento general de las noticias (si están disponibles).
    """
    if not articles:
        return {"sentiment": "neutral", "confidence": 0.0}

    # Si algún artículo tiene sentimiento (ej. MarketAux)
    sentiments = [a.get("sentiment", "neutral") for a in articles if a.get("sentiment")]

    if not sentiments:
        return {"sentiment": "neutral", "confidence": 0.5}

    # Contar sentimientos
    positive = sentiments.count("positive")
    negative = sentiments.count("negative")
    neutral = sentiments.count("neutral")
    total = len(sentiments)

    # Determinar sentimiento predominante
    if positive > negative and positive > neutral:
        return {"sentiment": "positive", "confidence": positive / total}
    elif negative > positive and negative > neutral:
        return {"sentiment": "negative", "confidence": negative / total}
    else:
        return {"sentiment": "neutral", "confidence": neutral / total}
