# Portfolio Alerts Enhanced

Sistema avanzado de alertas y análisis de inversiones con:
- Análisis técnico (RSI, MACD, medias móviles, volatilidad)
- Análisis fundamental (P/E, dividendos, recomendaciones de analistas)
- Múltiples fuentes de noticias (Google News, Yahoo Finance, MarketAux opcional)
- Portfolio rebalancing automático con recomendaciones de compra/venta
- Email HTML profesional con tablas visuales
- Análisis mejorado con OpenAI GPT-4

## Nuevas Funcionalidades

### 1. Análisis Técnico Completo
- **RSI (Relative Strength Index)**: Identifica sobreventa (<30) y sobrecompra (>70)
- **MACD**: Detecta momentum alcista o bajista
- **Medias Móviles**: SMA 20, 50, 200 días para tendencias
- **Volatilidad**: Cálculo anualizado para gestión de riesgo

### 2. Análisis Fundamental
- **P/E Ratio**: Valoración vs mercado
- **Dividend Yield**: Rendimiento por dividendos
- **Recomendaciones de analistas**: Buy, Hold, Sell
- **Precio objetivo**: Upside potencial
- **Beta**: Volatilidad vs mercado

### 3. Portfolio Rebalancing
- Calcula automáticamente cuánto comprar/vender para mantener proporciones objetivo
- Evita micro-transacciones con valor mínimo configurable
- Considera análisis técnico/fundamental para alertas (ej. "comprar pero RSI en sobrecompra")

### 4. Email HTML Profesional
- Tabla visual con cada acción
- Precio actual vs anterior con cambio porcentual
- Recomendación destacada (COMPRAR/VENDER/MANTENER)
- Análisis técnico y fundamental resumido
- Riesgos y catalizadores
- Sección de rebalancing si aplica

### 5. Múltiples Fuentes de Noticias
- Google News con filtros financieros mejorados
- Yahoo Finance noticias directas
- MarketAux (opcional con API key) para sentimiento

## Configuración

### 1. Google Sheet

Crea una hoja con estas columnas **exactas**:

| Ticker | Qty | AvgCost | BuyBelow | SellAbove | TargetWeight | Notes |
|--------|-----|---------|----------|-----------|--------------|-------|
| SPYG   | 2.5 | 77.20   | 75       | 90        | 40           | Base estable ETF |
| AAPL   | 1   | 228.10  | 225      | 245       | 25           | Tech growth |
| GOOGL  | 0.8 | 207.00  | 205      | 235       | 20           | Tech diversification |

**Nueva columna importante:**
- `TargetWeight`: Porcentaje objetivo en tu portfolio (debe sumar 100%)

En Google Sheets:
1. **Archivo > Compartir > Publicar en la web**
2. Selecciona "Hoja actual"
3. Formato: **CSV**
4. Copia la URL que termina en `.../pub?output=csv`

### 2. Secrets de GitHub Actions

Ve a **Settings > Secrets and variables > Actions** y crea estos secrets:

#### Obligatorios:
- `SHEET_CSV_URL` → URL pública CSV de tu Google Sheet
- `FROM_EMAIL` → Tu correo Gmail
- `TO_EMAIL` → Destinatario de alertas
- `SMTP_HOST` → `smtp.gmail.com`
- `SMTP_PORT` → `587`
- `SMTP_USER` → Tu correo (mismo que FROM_EMAIL)
- `SMTP_PASS` → [App Password de Gmail](https://support.google.com/accounts/answer/185833)
- `OPENAI_API_KEY` → Tu API key de OpenAI

#### Opcionales:
- `OPENAI_MODEL` → Modelo a usar (default: `gpt-5-mini`)
- `SEND_LOCAL_TZ` → Zona horaria (default: `America/Lima`)
- `SEND_AT_HHMM` → Hora de envío (default: `08:45`)
- `MAX_ARTICLES_PER_SOURCE` → Artículos por fuente (default: `3`)
- `MARKETAUX_API_KEY` → API key de MarketAux (opcional, mejora noticias)
- `ENABLE_REBALANCING` → `true` o `false` (default: `true`)
- `MIN_TRADE_VALUE` → Valor mínimo de trade en USD (default: `100`)
- `MAX_DEVIATION` → Desviación máxima % antes de rebalancear (default: `5`)

### 3. GitHub Actions Workflow

Crea `.github/workflows/portfolio-alerts.yml`:

```yaml
name: Portfolio Alerts Enhanced

on:
  schedule:
    - cron: "45 13 * * 1-5"  # Lunes a Viernes 08:45 Lima (UTC-5)
  workflow_dispatch: {}

jobs:
  alerts:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run enhanced alerts
        env:
          SHEET_CSV_URL: ${{ secrets.SHEET_CSV_URL }}
          FROM_EMAIL: ${{ secrets.FROM_EMAIL }}
          TO_EMAIL: ${{ secrets.TO_EMAIL }}
          SMTP_HOST: ${{ secrets.SMTP_HOST }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}
          SMTP_USER: ${{ secrets.SMTP_USER }}
          SMTP_PASS: ${{ secrets.SMTP_PASS }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          OPENAI_MODEL: ${{ secrets.OPENAI_MODEL }}
          SEND_LOCAL_TZ: ${{ secrets.SEND_LOCAL_TZ }}
          SEND_AT_HHMM: ${{ secrets.SEND_AT_HHMM }}
          MAX_ARTICLES_PER_SOURCE: ${{ secrets.MAX_ARTICLES_PER_SOURCE }}
          MARKETAUX_API_KEY: ${{ secrets.MARKETAUX_API_KEY }}
          ENABLE_REBALANCING: ${{ secrets.ENABLE_REBALANCING }}
          MIN_TRADE_VALUE: ${{ secrets.MIN_TRADE_VALUE }}
          MAX_DEVIATION: ${{ secrets.MAX_DEVIATION }}
        run: python news_digest_enhanced.py
```

## Uso Local

```bash
# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
export SHEET_CSV_URL='https://docs.google.com/.../pub?output=csv'
export FROM_EMAIL='tu@gmail.com'
export TO_EMAIL='destino@gmail.com'
export SMTP_PASS='tu-app-password'
export OPENAI_API_KEY='sk-...'

# Ejecutar versión mejorada
python news_digest_enhanced.py

# Ejecutar versión original (simple)
python news_digest.py
```

## Estructura del Proyecto

```
portfolio-alerts-starter/
├── analysis.py                  # Análisis técnico y fundamental
├── portfolio.py                 # Sistema de rebalancing
├── news_sources.py             # Agregación de noticias (múltiples fuentes)
├── ai_analysis.py              # Prompts mejorados de OpenAI
├── email_template.py           # Templates HTML para emails
├── news_digest_enhanced.py     # Script principal mejorado
├── news_digest.py              # Script original (simple)
├── main.py                     # Alertas simples de compra/venta
├── requirements.txt
├── sample_portfolio.csv
└── README.md
```

## Comparación: Original vs Enhanced

| Característica | Original | Enhanced |
|---------------|----------|----------|
| Email formato | Texto plano | HTML profesional |
| Análisis técnico | No | Sí (RSI, MACD, SMA) |
| Análisis fundamental | No | Sí (P/E, dividendos, beta) |
| Fuentes de noticias | Google News | Google News + Yahoo Finance + MarketAux |
| Portfolio rebalancing | No | Sí (cantidades exactas) |
| Prompts OpenAI | Básicos | Mejorados con contexto técnico/fundamental |
| Gestión de riesgo | Solo umbrales | Volatilidad, RSI, sentimiento |

## Cómo Interpreta las Recomendaciones

### COMPRAR
- RSI < 30 (sobreventa)
- Precio bajo SMA20/50 pero sobre SMA200 (dip en bull market)
- P/E bajo vs sector
- Noticias positivas (earnings beat, nuevos productos)
- Target price con >10% upside
- Portfolio subponderado según TargetWeight

### VENDER
- RSI > 70 (sobrecompra)
- MACD negativo con momentum bajista
- P/E muy alto (sobrevaloración)
- Noticias negativas (warnings, demandas)
- Precio cerca de 52w high sin catalizadores
- Portfolio sobreponderado según TargetWeight

### MANTENER
- Señales mixtas
- RSI neutral (30-70)
- P/E razonable
- Sin noticias significativas
- Portfolio balanceado

## Rebalancing: Ejemplo

Supongamos tu portfolio actual:

| Ticker | Qty | Precio | Valor | Peso Actual | Peso Objetivo |
|--------|-----|--------|-------|-------------|---------------|
| SPYG   | 2.5 | $80    | $200  | 45%         | 40%           |
| AAPL   | 1   | $230   | $230  | 52%         | 25%           |
| GOOGL  | 0.8 | $140   | $112  | 25%         | 20%           |
| V      | 0.3 | $280   | $84   | 19%         | 15%           |

**Total portfolio:** $626

El sistema recomendaría:
- **VENDER 0.5 AAPL** ($115) - Sobreponderado (52% vs 25%)
- **COMPRAR 0.3 GOOGL** ($42) - Subponderado (25% vs 35%)
- **MANTENER SPYG y V** - Cerca del objetivo

## Costos y APIs

### OpenAI
- **Requerido**: Sí
- **Modelo recomendado**: `gpt-5-mini` (mejor lógica)
- **Costo estimado**: ~$0.50-1.00/mes para 4-5 acciones diarias
- **Alternativas**: `gpt-4o-mini` o `gpt-3.5-turbo` (más económicos)

### MarketAux (Opcional)
- **Requerido**: No
- **Plan gratuito**: 100 requests/mes
- **Mejora**: Sentimiento de noticias más preciso
- **Registro**: https://www.marketaux.com/

## Troubleshooting

### Email no se envía
1. Verifica que `SMTP_PASS` sea un **App Password**, no tu contraseña normal
2. Activa 2FA en Gmail: https://myaccount.google.com/security
3. Crea App Password: https://myaccount.google.com/apppasswords

### Precios no se obtienen
- yfinance a veces falla. El sistema tiene 5 métodos de fallback.
- Si persiste, verifica que el ticker sea correcto (ej. `AAPL` no `APPLE`)

### OpenAI da error
- Verifica que tu API key sea válida: https://platform.openai.com/api-keys
- Revisa que tengas créditos disponibles
- Cambia `OPENAI_MODEL` a `gpt-4o-mini` o `gpt-3.5-turbo` si `gpt-5-mini` no está disponible

### Análisis técnico/fundamental vacío
- Algunos tickers (ETFs, acciones nuevas) tienen datos limitados
- Es normal, el sistema lo detecta y muestra "No disponible"

## Roadmap

Próximas mejoras planeadas:
- [ ] Soporte para criptomonedas (Bitcoin, Ethereum)
- [ ] Alertas de stop-loss automáticas
- [ ] Dashboard web con Streamlit
- [ ] Backtesting de estrategias
- [ ] Integración con Telegram/WhatsApp
- [ ] Soporte para múltiples portfolios

## Contribuciones

Pull requests son bienvenidos. Para cambios mayores, abre un issue primero para discutir.

## Licencia

MIT

## Disclaimer

Esta herramienta es para uso educativo e informativo. No constituye asesoría financiera.
Siempre haz tu propia investigación antes de tomar decisiones de inversión.

---

**Creado con:**
- Python 3.11+
- yfinance (datos de mercado)
- OpenAI GPT-4 (análisis)
- GitHub Actions (automatización)
- Gmail SMTP (notificaciones)
