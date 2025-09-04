# Portfolio Alerts (GitHub Actions + Python)

Envía un **email semanal** con señales de compra/venta en base a tu Google Sheet.
Anti-spam: **solo envía si hay señales**.

## 1) Google Sheet
Crea una hoja con columnas exactas:

| Ticker | Qty | AvgCost | BuyBelow | SellAbove | Notes |
|-------|-----|---------|----------|-----------|-------|
| SPYG  | 2.5 | 77.20   | 75       | 90        | Base estable |
| AAPL  | 1   | 228.10  | 225      | 245       | — |

En Google Sheets → **Archivo > Compartir > Publicar en la web** → *Hoja actual* → **CSV**.
Copia la URL que termina en `.../pub?output=csv` y úsala en el secret `SHEET_CSV_URL`.

> Privacidad: si prefieres no publicar, adapta `main.py` para usar la API de Google (puedo darte la versión).

## 2) Secrets (GitHub → Repo → Settings → Secrets and variables → Actions)
Crea estos **Secrets**:

- `SHEET_CSV_URL` → URL pública CSV de tu hoja.
- `FROM_EMAIL`     → tu correo remitente.
- `TO_EMAIL`       → destino de alertas.
- `SMTP_HOST`      → p. ej. `smtp.gmail.com`
- `SMTP_PORT`      → `587`
- `SMTP_USER`      → tu correo (o usuario SMTP).
- `SMTP_PASS`      → **App Password** (Gmail: activar 2FA y crear “Contraseña de aplicación”).

## 3) Frecuencia
Por defecto: **lunes 08:30 (Lima)** → `cron: 30 13 * * 1` (UTC).  
Para agregar chequeos diarios **anti-spam** (solo avisa con señales), duplica el bloque `on.schedule`:

```yaml
on:
  schedule:
    - cron: "30 13 * * 1"  # Lunes 08:30 Lima
    - cron: "0 15 * * 1-5" # 10:00 Lima (L-V)
    - cron: "30 19 * * 1-5"# 14:30 Lima (L-V)
  workflow_dispatch: {}
```

## 4) Prueba manual
Ve a **Actions > Portfolio Alerts > Run workflow** para dispararlo ahora.

## 5) Dependencias locales
```bash
pip install -r requirements.txt
export SHEET_CSV_URL='https://.../pub?output=csv'
export FROM_EMAIL='tu@gmail.com'
export TO_EMAIL='tu@destino.com'
export SMTP_PASS='tu-app-pass'
python main.py
```

---

> Soporte: si quieres que adapte las reglas (RSI, medias móviles, % drawdown, etc.) o leer directo de Google API, dilo y te paso la versión avanzada.
