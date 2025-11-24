"""
Módulo para análisis avanzado con OpenAI.
Mejora los prompts con contexto técnico, fundamental y de múltiples fuentes.
"""
from typing import List, Dict
from openai import OpenAI
import os

def build_enhanced_analysis_prompt(
    ticker: str,
    company: str,
    price: float,
    prev_close: float,
    articles: List[Dict],
    technical_data: Dict = None,
    fundamental_data: Dict = None,
    portfolio_context: Dict = None
) -> str:
    """
    Construye un prompt mejorado con todo el contexto disponible.
    """
    # Precios
    price_line = "N/D" if price <= 0 else f"${price:.2f}"
    prev_line = "N/D" if prev_close <= 0 else f"${prev_close:.2f}"
    delta = ""
    if price > 0 and prev_close > 0:
        pct = ((price - prev_close) / prev_close) * 100.0
        delta = f"{pct:+.2f}%"

    # Noticias
    if articles:
        news_block = "\n".join([
            f"- [{a.get('source', 'N/D')}] {a.get('title', '')} — {a.get('link', '')}"
            for a in articles
        ])
    else:
        news_block = "- Sin titulares relevantes en las últimas 24h"

    # Análisis técnico
    tech_block = ""
    if technical_data:
        rsi = technical_data.get("rsi")
        macd = technical_data.get("macd")
        sma_20 = technical_data.get("sma_20")
        sma_50 = technical_data.get("sma_50")
        sma_200 = technical_data.get("sma_200")
        volatility = technical_data.get("volatility")

        tech_parts = []
        if rsi:
            tech_parts.append(f"- RSI: {rsi:.1f}")
            if rsi < 30:
                tech_parts.append("  (sobreventa - potencial rebote)")
            elif rsi > 70:
                tech_parts.append("  (sobrecompra - posible corrección)")

        if macd is not None:
            tech_parts.append(f"- MACD: {macd:.3f} (momentum {'positivo' if macd > 0 else 'negativo'})")

        if sma_20 and sma_50 and price > 0:
            if price > sma_20 > sma_50:
                tech_parts.append(f"- Precio (${price:.2f}) > SMA20 (${sma_20:.2f}) > SMA50 (${sma_50:.2f}) - tendencia alcista")
            elif price < sma_20 < sma_50:
                tech_parts.append(f"- Precio (${price:.2f}) < SMA20 (${sma_20:.2f}) < SMA50 (${sma_50:.2f}) - tendencia bajista")

        if sma_200 and price > 0:
            if price > sma_200:
                tech_parts.append(f"- Precio sobre SMA200 (${sma_200:.2f}) - bull market")
            else:
                tech_parts.append(f"- Precio bajo SMA200 (${sma_200:.2f}) - bear market")

        if volatility:
            tech_parts.append(f"- Volatilidad anualizada: {volatility:.1%}")

        tech_block = "\n".join(tech_parts) if tech_parts else "No disponible"

    # Análisis fundamental
    fund_block = ""
    if fundamental_data:
        pe_ratio = fundamental_data.get("pe_ratio")
        forward_pe = fundamental_data.get("forward_pe")
        dividend_yield = fundamental_data.get("dividend_yield")
        market_cap = fundamental_data.get("market_cap")
        recommendation = fundamental_data.get("recommendation")
        target_price = fundamental_data.get("target_price")
        beta = fundamental_data.get("beta")

        fund_parts = []
        if pe_ratio:
            fund_parts.append(f"- P/E Ratio: {pe_ratio:.2f}")
            if pe_ratio < 15:
                fund_parts.append("  (potencial infravalorado)")
            elif pe_ratio > 30:
                fund_parts.append("  (potencial sobrevalorado)")

        if forward_pe:
            fund_parts.append(f"- Forward P/E: {forward_pe:.2f}")

        if dividend_yield and dividend_yield > 0:
            fund_parts.append(f"- Dividend Yield: {dividend_yield:.2%}")

        if market_cap:
            fund_parts.append(f"- Market Cap: ${market_cap:,.0f}")

        if beta:
            fund_parts.append(f"- Beta: {beta:.2f} ({'volátil' if beta > 1.2 else 'estable'})")

        if recommendation:
            rec_map = {"buy": "Compra", "hold": "Mantener", "sell": "Venta", "strong_buy": "Compra Fuerte"}
            fund_parts.append(f"- Recomendación analistas: {rec_map.get(recommendation, recommendation)}")

        if target_price and price > 0:
            upside = ((target_price - price) / price) * 100
            fund_parts.append(f"- Precio objetivo: ${target_price:.2f} ({upside:+.1f}% upside)")

        fund_block = "\n".join(fund_parts) if fund_parts else "No disponible"

    # Contexto de portfolio
    portfolio_block = ""
    if portfolio_context:
        current_weight = portfolio_context.get("current_weight")
        target_weight = portfolio_context.get("target_weight")
        if current_weight and target_weight:
            portfolio_block = f"""
Contexto del Portfolio:
- Peso actual en portfolio: {current_weight:.1f}%
- Peso objetivo: {target_weight:.1f}%
- Estado: {'Sobreponderado' if current_weight > target_weight else 'Subponderado' if current_weight < target_weight else 'Balanceado'}
"""

    prompt = f"""
Eres un analista financiero senior con experiencia en análisis técnico y fundamental.
Tu objetivo es proporcionar un resumen ejecutivo, objetivo y accionable basado ÚNICAMENTE en los datos proporcionados.

DATOS DISPONIBLES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Ticker: {ticker}
Empresa: {company}
Precio actual: {price_line}
Cierre previo: {prev_line}
Cambio intradía: {delta or "N/D"}

NOTICIAS (últimas 24h):
{news_block}

ANÁLISIS TÉCNICO:
{tech_block}

ANÁLISIS FUNDAMENTAL:
{fund_block}

{portfolio_block}

INSTRUCCIONES ESTRICTAS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. **No inventes información**. Si un dato es N/D, dilo explícitamente y evita hacer conclusiones sobre él.

2. **Sintetiza las noticias**: Resume las noticias en 2-3 oraciones, identificando los temas principales (earnings, nuevos productos, regulación, etc.). No copies titulares completos.

3. **Interpreta indicadores técnicos y fundamentales**: Explica qué significan los valores de RSI, MACD, P/E ratio, etc., y cómo impactan la decisión de inversión.

4. **Recomendación clara**: Basándote en TODOS los datos (noticias, técnico, fundamental), proporciona una recomendación:
   - **COMPRAR**: si los indicadores son mayormente positivos y hay catalizadores alcistas
   - **VENDER**: si hay señales de debilidad, sobrevaluación o riesgos inminentes
   - **MANTENER**: si las señales son mixtas o neutrales

5. **Riesgos y catalizadores**: Menciona 2-3 riesgos concretos (volatilidad, valoración, eventos próximos) y posibles catalizadores (earnings, lanzamientos, etc.).

6. **Longitud**: 200-250 palabras en total.

FORMATO DE RESPUESTA:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Resumen del Día:**
[1-2 párrafos resumiendo noticias y movimiento de precio]

**Análisis Técnico y Fundamental:**
[1 párrafo integrando señales técnicas y fundamentales]

**Recomendación:**
[COMPRAR / VENDER / MANTENER] - [Justificación en 2-3 líneas]

**Riesgos y Catalizadores:**
- [Riesgo/catalizador 1]
- [Riesgo/catalizador 2]
- [Riesgo/catalizador 3]
"""

    return prompt

def get_ai_analysis(
    ticker: str,
    company: str,
    price: float,
    prev_close: float,
    articles: List[Dict],
    technical_data: Dict = None,
    fundamental_data: Dict = None,
    portfolio_context: Dict = None,
    model: str = "gpt-4o-mini",
    api_key: str = None
) -> Dict[str, str]:
    """
    Obtiene análisis mejorado de OpenAI con contexto completo.

    Returns:
        Dict con keys: summary, recommendation, risks, full_text
    """
    if api_key is None:
        api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        return {
            "summary": "Error: No se proporcionó API key de OpenAI",
            "recommendation": "MANTENER",
            "risks": "No disponible",
            "full_text": "Error de configuración"
        }

    try:
        client = OpenAI(api_key=api_key)

        prompt = build_enhanced_analysis_prompt(
            ticker, company, price, prev_close, articles,
            technical_data, fundamental_data, portfolio_context
        )

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,  # Más determinístico
            max_tokens=600
        )

        full_text = response.choices[0].message.content.strip()

        # Parsear respuesta
        recommendation = "MANTENER"
        if "**Recomendación:**" in full_text:
            rec_section = full_text.split("**Recomendación:**")[1].split("**")[0].strip()
            if "COMPRAR" in rec_section.upper():
                recommendation = "COMPRAR"
            elif "VENDER" in rec_section.upper():
                recommendation = "VENDER"

        # Extraer resumen
        summary = ""
        if "**Resumen del Día:**" in full_text:
            summary = full_text.split("**Resumen del Día:**")[1].split("**")[0].strip()

        # Extraer riesgos
        risks = ""
        if "**Riesgos y Catalizadores:**" in full_text:
            risks = full_text.split("**Riesgos y Catalizadores:**")[1].strip()

        return {
            "summary": summary or full_text[:200],
            "recommendation": recommendation,
            "risks": risks or "Ver análisis completo",
            "full_text": full_text
        }

    except Exception as e:
        print(f"Error en análisis AI para {ticker}: {e}")
        return {
            "summary": f"Error al obtener análisis: {str(e)}",
            "recommendation": "MANTENER",
            "risks": "No disponible",
            "full_text": f"Error: {str(e)}"
        }
