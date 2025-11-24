"""
Módulo de gestión de portfolio y rebalanceo.
Calcula cuánto comprar/vender para mantener proporciones objetivo.
"""
import pandas as pd
from typing import Dict, List, Tuple

def calculate_portfolio_values(holdings: pd.DataFrame, prices: Dict[str, float]) -> pd.DataFrame:
    """
    Calcula el valor actual de cada posición en el portfolio.

    Args:
        holdings: DataFrame con columnas Ticker, Qty, AvgCost, TargetWeight (%)
        prices: Dict con precios actuales {ticker: precio}

    Returns:
        DataFrame con columnas adicionales: CurrentPrice, CurrentValue, Weight
    """
    df = holdings.copy()
    df["CurrentPrice"] = df["Ticker"].map(prices).fillna(0.0)
    df["CurrentValue"] = df["Qty"] * df["CurrentPrice"]

    total_value = df["CurrentValue"].sum()
    df["CurrentWeight"] = (df["CurrentValue"] / total_value * 100) if total_value > 0 else 0.0

    return df

def calculate_rebalancing_actions(
    holdings: pd.DataFrame,
    prices: Dict[str, float],
    min_trade_value: float = 100.0,
    max_deviation: float = 5.0
) -> List[Dict]:
    """
    Calcula las acciones de rebalanceo necesarias para volver a las proporciones objetivo.

    Args:
        holdings: DataFrame con Ticker, Qty, AvgCost, TargetWeight
        prices: Dict con precios actuales
        min_trade_value: Valor mínimo de trade para evitar micro-transacciones
        max_deviation: Desviación máxima permitida (%) antes de rebalancear

    Returns:
        Lista de diccionarios con acciones: {ticker, action, qty, value, reason}
    """
    df = calculate_portfolio_values(holdings, prices)
    total_value = df["CurrentValue"].sum()

    if total_value == 0:
        return []

    actions = []

    for _, row in df.iterrows():
        ticker = row["Ticker"]
        current_weight = row["CurrentWeight"]
        target_weight = row.get("TargetWeight", 0.0)
        current_price = row["CurrentPrice"]

        if current_price <= 0:
            continue

        # Calcular desviación
        deviation = current_weight - target_weight

        # Solo actuar si la desviación excede el umbral
        if abs(deviation) < max_deviation:
            continue

        # Calcular valor y cantidad a ajustar
        target_value = (target_weight / 100) * total_value
        current_value = row["CurrentValue"]
        value_diff = target_value - current_value
        qty_diff = value_diff / current_price

        # Filtrar trades pequeños
        if abs(value_diff) < min_trade_value:
            continue

        if value_diff > 0:
            # Comprar
            actions.append({
                "ticker": ticker,
                "action": "COMPRAR",
                "qty": abs(qty_diff),
                "value": abs(value_diff),
                "current_weight": current_weight,
                "target_weight": target_weight,
                "deviation": deviation,
                "reason": f"Subponderado ({current_weight:.1f}% vs {target_weight:.1f}%)"
            })
        else:
            # Vender
            max_sellable = row["Qty"]
            qty_to_sell = min(abs(qty_diff), max_sellable)

            actions.append({
                "ticker": ticker,
                "action": "VENDER",
                "qty": qty_to_sell,
                "value": abs(value_diff),
                "current_weight": current_weight,
                "target_weight": target_weight,
                "deviation": deviation,
                "reason": f"Sobreponderado ({current_weight:.1f}% vs {target_weight:.1f}%)"
            })

    # Ordenar por desviación absoluta (mayor primero)
    actions.sort(key=lambda x: abs(x["deviation"]), reverse=True)

    return actions

def calculate_sell_percentage(
    ticker: str,
    current_qty: float,
    current_price: float,
    target_weight: float,
    total_portfolio_value: float,
    reason: str = "rebalance"
) -> Dict:
    """
    Calcula qué porcentaje de una posición vender según diferentes criterios.

    Args:
        ticker: Símbolo del ticker
        current_qty: Cantidad actual de acciones
        current_price: Precio actual
        target_weight: Peso objetivo en portfolio (%)
        total_portfolio_value: Valor total del portfolio
        reason: Razón de la venta (rebalance, take_profit, stop_loss, etc.)

    Returns:
        Dict con porcentaje a vender y cantidad
    """
    current_value = current_qty * current_price
    current_weight = (current_value / total_portfolio_value * 100) if total_portfolio_value > 0 else 0

    if reason == "rebalance":
        # Vender solo lo necesario para llegar al target weight
        target_value = (target_weight / 100) * total_portfolio_value
        value_to_sell = current_value - target_value
        qty_to_sell = value_to_sell / current_price if current_price > 0 else 0
        pct_to_sell = (qty_to_sell / current_qty * 100) if current_qty > 0 else 0

        return {
            "ticker": ticker,
            "sell_percentage": max(0, pct_to_sell),
            "sell_qty": max(0, qty_to_sell),
            "sell_value": max(0, value_to_sell),
            "reason": f"Rebalanceo a {target_weight:.1f}%"
        }

    elif reason == "take_profit":
        # Estrategia: vender 50% cuando hay ganancia significativa (>20%)
        return {
            "ticker": ticker,
            "sell_percentage": 50.0,
            "sell_qty": current_qty * 0.5,
            "sell_value": current_value * 0.5,
            "reason": "Toma de ganancias (vender 50%)"
        }

    elif reason == "stop_loss":
        # Estrategia: vender 100% cuando hay pérdida significativa
        return {
            "ticker": ticker,
            "sell_percentage": 100.0,
            "sell_qty": current_qty,
            "sell_value": current_value,
            "reason": "Stop loss (vender todo)"
        }

    elif reason == "reduce_risk":
        # Estrategia: reducir exposición en 25% si hay alta volatilidad
        return {
            "ticker": ticker,
            "sell_percentage": 25.0,
            "sell_qty": current_qty * 0.25,
            "sell_value": current_value * 0.25,
            "reason": "Reducción de riesgo (vender 25%)"
        }

    return {
        "ticker": ticker,
        "sell_percentage": 0.0,
        "sell_qty": 0.0,
        "sell_value": 0.0,
        "reason": "Sin acción"
    }

def generate_rebalancing_recommendation(
    holdings: pd.DataFrame,
    prices: Dict[str, float],
    technical_data: Dict[str, Dict] = None,
    fundamental_data: Dict[str, Dict] = None
) -> Tuple[List[Dict], str]:
    """
    Genera recomendaciones de rebalanceo considerando análisis técnico y fundamental.

    Returns:
        (lista de acciones, resumen en texto)
    """
    actions = calculate_rebalancing_actions(holdings, prices)

    if not actions:
        return [], "Portfolio balanceado. No se requieren acciones de rebalanceo."

    # Enriquecer acciones con contexto técnico/fundamental
    enhanced_actions = []
    for action in actions:
        ticker = action["ticker"]
        enhanced = action.copy()

        # Agregar contexto técnico
        if technical_data and ticker in technical_data:
            tech = technical_data[ticker]
            rsi = tech.get("rsi")
            if rsi:
                if action["action"] == "COMPRAR" and rsi > 70:
                    enhanced["warning"] = "RSI sobrecompra - considerar esperar"
                elif action["action"] == "VENDER" and rsi < 30:
                    enhanced["warning"] = "RSI sobreventa - podría rebotar"

        # Agregar contexto fundamental
        if fundamental_data and ticker in fundamental_data:
            fund = fundamental_data[ticker]
            recommendation = fund.get("recommendation")
            if recommendation:
                if action["action"] == "COMPRAR" and recommendation == "sell":
                    enhanced["warning"] = "Analistas recomiendan venta"
                elif action["action"] == "VENDER" and recommendation == "buy":
                    enhanced["warning"] = "Analistas recomiendan compra"

        enhanced_actions.append(enhanced)

    # Generar resumen
    buy_count = sum(1 for a in actions if a["action"] == "COMPRAR")
    sell_count = sum(1 for a in actions if a["action"] == "VENDER")
    total_buy_value = sum(a["value"] for a in actions if a["action"] == "COMPRAR")
    total_sell_value = sum(a["value"] for a in actions if a["action"] == "VENDER")

    summary_parts = []
    if buy_count > 0:
        summary_parts.append(f"Comprar {buy_count} posición(es) por ${total_buy_value:,.0f}")
    if sell_count > 0:
        summary_parts.append(f"Vender {sell_count} posición(es) por ${total_sell_value:,.0f}")

    summary = "Rebalanceo recomendado: " + ", ".join(summary_parts)

    return enhanced_actions, summary
