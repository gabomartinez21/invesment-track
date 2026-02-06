"""
Templates HTML profesionales para emails de portfolio.
"""
from datetime import datetime
from typing import List, Dict

def format_currency(value: float) -> str:
    """Formatea valor como moneda USD."""
    if value == 0 or value is None:
        return "N/D"
    return f"${value:,.2f}"

def format_percentage(value: float) -> str:
    """Formatea valor como porcentaje con color."""
    if value is None or value == 0:
        return "N/D"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"

def get_color_for_change(value: float) -> str:
    """Retorna color basado en cambio positivo/negativo."""
    if value is None or value == 0:
        return "#666666"
    return "#28a745" if value > 0 else "#dc3545"

def get_recommendation_badge(recommendation: str) -> str:
    """Retorna badge HTML para recomendación."""
    colors = {
        "COMPRAR": "#28a745",
        "VENDER": "#dc3545",
        "MANTENER": "#ffc107"
    }
    rec_upper = recommendation.upper()
    color = colors.get(rec_upper, "#6c757d")
    return f'<span style="background-color: {color}; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold;">{recommendation}</span>'

def generate_stock_table_html(stocks_data: List[Dict]) -> str:
    """
    Genera tabla HTML con información de cada acción.

    stocks_data debe contener:
    - ticker, company, price, prev_close, change_pct
    - quantity, avg_cost, position_value, pnl, pnl_pct
    - current_weight, target_weight
    - recommendation, news_summary, technical_summary, fundamental_summary, risks
    """
    rows_html = []

    for stock in stocks_data:
        ticker = stock.get("ticker", "N/D")
        company = stock.get("company", "N/D")
        price = stock.get("price", 0)
        prev_close = stock.get("prev_close", 0)
        change_pct = stock.get("change_pct", 0)
        recommendation = stock.get("recommendation", "MANTENER")
        news_summary = stock.get("news_summary", "Sin noticias relevantes")
        technical = stock.get("technical_summary", "")
        fundamental = stock.get("fundamental_summary", "")
        risks = stock.get("risks", "")
        rebalance_action = stock.get("rebalance_action", "")

        # Datos de portfolio
        quantity = stock.get("quantity", 0)
        avg_cost = stock.get("avg_cost", 0)
        position_value = stock.get("position_value", 0)
        pnl = stock.get("pnl", 0)
        pnl_pct = stock.get("pnl_pct", 0)
        current_weight = stock.get("current_weight", 0)
        target_weight = stock.get("target_weight", 0)

        price_str = format_currency(price)
        prev_str = format_currency(prev_close)
        change_str = format_percentage(change_pct)
        change_color = get_color_for_change(change_pct)
        rec_badge = get_recommendation_badge(recommendation)

        # Formateo de datos de portfolio
        qty_str = f"{quantity:.2f}" if quantity else "0"
        avg_cost_str = format_currency(avg_cost)
        value_str = format_currency(position_value)
        pnl_str = format_currency(pnl)
        pnl_pct_str = format_percentage(pnl_pct)
        pnl_color = get_color_for_change(pnl_pct)
        weight_str = f"{current_weight:.1f}%" if current_weight else "0%"
        target_str = f"{target_weight:.1f}%" if target_weight else "0%"

        # Indicador de peso vs objetivo
        weight_status = ""
        if current_weight and target_weight:
            diff = current_weight - target_weight
            if abs(diff) > 2:  # Diferencia significativa (>2%)
                if diff > 0:
                    weight_status = f'<span style="color: #ff6600; font-size: 11px;">↑ Sobreponderado</span>'
                else:
                    weight_status = f'<span style="color: #0066cc; font-size: 11px;">↓ Subponderado</span>'

        row = f"""
        <tr>
            <td style="padding: 16px; border-bottom: 1px solid #dee2e6; font-weight: bold; color: #0066cc; vertical-align: top;">
                {ticker}
            </td>
            <td style="padding: 16px; border-bottom: 1px solid #dee2e6;">
                <strong>{company}</strong><br>
                <small style="color: #666;">Precio: {price_str} | Ayer: {prev_str}</small><br>
                <span style="color: {change_color}; font-weight: bold;">{change_str}</span>
            </td>
            <td style="padding: 16px; border-bottom: 1px solid #dee2e6; background-color: #f8f9fa;">
                <div style="font-size: 13px; line-height: 1.6;">
                    <div><strong>Acciones:</strong> {qty_str}</div>
                    <div><strong>Costo prom:</strong> {avg_cost_str}</div>
                    <div><strong>Valor:</strong> {value_str}</div>
                    <div style="color: {pnl_color};"><strong>P&L:</strong> {pnl_str} ({pnl_pct_str})</div>
                    <div><strong>Peso:</strong> {weight_str} / {target_str} {weight_status}</div>
                </div>
            </td>
            <td style="padding: 16px; border-bottom: 1px solid #dee2e6; text-align: center; vertical-align: top;">
                {rec_badge}
                {f'<br><small style="color: #666; margin-top: 4px; display: block;">{rebalance_action}</small>' if rebalance_action else ''}
            </td>
        </tr>
        <tr>
            <td colspan="4" style="padding: 16px; border-bottom: 2px solid #dee2e6; background-color: #fafafa;">
                <div style="margin-bottom: 12px;">
                    <strong style="color: #333;">Resumen:</strong>
                    <p style="margin: 8px 0; color: #555;">{news_summary}</p>
                </div>
                {f'''<div style="margin-bottom: 12px;">
                    <strong style="color: #333;">Análisis Técnico:</strong>
                    <p style="margin: 8px 0; color: #555; font-size: 13px;">{technical}</p>
                </div>''' if technical else ''}
                {f'''<div style="margin-bottom: 12px;">
                    <strong style="color: #333;">Análisis Fundamental:</strong>
                    <p style="margin: 8px 0; color: #555; font-size: 13px;">{fundamental}</p>
                </div>''' if fundamental else ''}
                {f'''<div style="margin-bottom: 12px;">
                    <strong style="color: #dc3545;">Riesgos:</strong>
                    <p style="margin: 8px 0; color: #555; font-size: 13px;">{risks}</p>
                </div>''' if risks else ''}
            </td>
        </tr>
        """
        rows_html.append(row)

    return "\n".join(rows_html)

def generate_rebalancing_section_html(actions: List[Dict]) -> str:
    """
    Genera sección HTML con recomendaciones de rebalanceo.
    """
    if not actions:
        return ""

    rows = []
    for action in actions:
        ticker = action.get("ticker", "N/D")
        action_type = action.get("action", "N/D")
        qty = action.get("qty", 0)
        value = action.get("value", 0)
        reason = action.get("reason", "")
        warning = action.get("warning", "")

        color = "#28a745" if action_type == "COMPRAR" else "#dc3545"
        warning_html = f'<br><small style="color: #ff6600;">⚠ {warning}</small>' if warning else ''

        row = f"""
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #dee2e6;">
                <strong>{ticker}</strong>
            </td>
            <td style="padding: 12px; border-bottom: 1px solid #dee2e6; color: {color}; font-weight: bold;">
                {action_type}
            </td>
            <td style="padding: 12px; border-bottom: 1px solid #dee2e6;">
                {qty:.2f} acciones
            </td>
            <td style="padding: 12px; border-bottom: 1px solid #dee2e6;">
                {format_currency(value)}
            </td>
            <td style="padding: 12px; border-bottom: 1px solid #dee2e6; font-size: 13px; color: #666;">
                {reason}{warning_html}
            </td>
        </tr>
        """
        rows.append(row)

    return f"""
    <div style="margin-top: 32px; padding: 20px; background-color: #fff3cd; border-left: 4px solid #ffc107; border-radius: 4px;">
        <h3 style="color: #856404; margin-top: 0;">Recomendaciones de Rebalanceo</h3>
        <table style="width: 100%; border-collapse: collapse; background-color: white; margin-top: 16px;">
            <thead>
                <tr style="background-color: #f8f9fa;">
                    <th style="padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6;">Ticker</th>
                    <th style="padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6;">Acción</th>
                    <th style="padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6;">Cantidad</th>
                    <th style="padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6;">Valor</th>
                    <th style="padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6;">Razón</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    </div>
    """

def generate_email_html(
    stocks_data: List[Dict],
    rebalancing_actions: List[Dict] = None,
    portfolio_summary: Dict = None,
    timestamp: str = None
) -> str:
    """
    Genera el HTML completo del email.

    Args:
        stocks_data: Lista de diccionarios con datos de cada acción
        rebalancing_actions: Lista de acciones de rebalanceo (opcional)
        portfolio_summary: Resumen del portfolio (valor total, cambio, etc.)
        timestamp: Timestamp para el header
    """
    if timestamp is None:
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")

    stock_table = generate_stock_table_html(stocks_data)
    rebalancing_section = generate_rebalancing_section_html(rebalancing_actions or [])

    # Portfolio summary
    summary_html = ""
    if portfolio_summary:
        total_value = portfolio_summary.get("total_value", 0)
        cash_available = portfolio_summary.get("cash_available", 0)
        net_worth = portfolio_summary.get("net_worth", total_value + cash_available)
        day_change = portfolio_summary.get("day_change", 0)
        day_change_pct = portfolio_summary.get("day_change_pct", 0)

        change_color = get_color_for_change(day_change_pct)
        # Color del texto del cambio ajustado para mejor contraste sobre fondo oscuro
        change_text_color = "#90EE90" if day_change_pct >= 0 else "#FFB6C1"

        summary_html = f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 24px; border-radius: 8px; margin-bottom: 24px;">
            <div style="display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-start;">
                <div style="flex: 1; min-width: 200px;">
                    <h2 style="margin: 0 0 8px 0; font-size: 16px; opacity: 0.9;">Valor en Acciones</h2>
                    <div style="font-size: 32px; font-weight: bold; margin: 8px 0;">
                        {format_currency(total_value)}
                    </div>
                    <div style="font-size: 18px; color: {change_text_color};">
                        {format_percentage(day_change_pct)} ({format_currency(day_change)}) hoy
                    </div>
                </div>
                <div style="flex: 0 0 auto; text-align: right; padding-left: 24px;">
                    <div style="margin-bottom: 12px;">
                        <div style="font-size: 12px; opacity: 0.8;">Cash Disponible</div>
                        <div style="font-size: 20px; font-weight: bold;">{format_currency(cash_available)}</div>
                    </div>
                    <div style="border-top: 1px solid rgba(255,255,255,0.3); padding-top: 12px;">
                        <div style="font-size: 12px; opacity: 0.8;">Patrimonio Total</div>
                        <div style="font-size: 24px; font-weight: bold;">{format_currency(net_worth)}</div>
                    </div>
                </div>
            </div>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Reporte de Portfolio</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 0 auto; padding: 20px; background-color: #f5f5f5;">
        <div style="background-color: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow: hidden;">
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); color: white; padding: 24px; text-align: center;">
                <h1 style="margin: 0; font-size: 28px;">Reporte Diario de Portfolio</h1>
                <p style="margin: 8px 0 0 0; opacity: 0.9;">{timestamp}</p>
            </div>

            <!-- Content -->
            <div style="padding: 24px;">
                {summary_html}

                <!-- Stocks Table -->
                <table style="width: 100%; border-collapse: collapse; background-color: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden;">
                    <thead>
                        <tr style="background-color: #f8f9fa;">
                            <th style="padding: 16px; text-align: left; border-bottom: 2px solid #dee2e6; font-weight: 600; width: 80px;">Ticker</th>
                            <th style="padding: 16px; text-align: left; border-bottom: 2px solid #dee2e6; font-weight: 600;">Precio</th>
                            <th style="padding: 16px; text-align: left; border-bottom: 2px solid #dee2e6; font-weight: 600;">Mi Posición</th>
                            <th style="padding: 16px; text-align: center; border-bottom: 2px solid #dee2e6; font-weight: 600; width: 120px;">Acción</th>
                        </tr>
                    </thead>
                    <tbody>
                        {stock_table}
                    </tbody>
                </table>

                {rebalancing_section}

                <!-- Footer -->
                <div style="margin-top: 32px; padding: 16px; background-color: #f8f9fa; border-radius: 4px; text-align: center; color: #666; font-size: 13px;">
                    <p style="margin: 0;">Este reporte es generado automáticamente. La información no constituye asesoría financiera.</p>
                    <p style="margin: 8px 0 0 0;">Datos obtenidos de: Yahoo Finance, Google News, OpenAI</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    return html
