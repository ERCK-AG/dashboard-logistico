"""
alerts.py — Sistema de alertas y detección de anomalías logísticas.
"""

from __future__ import annotations

import pandas as pd
from dataclasses import dataclass, field
from typing import Optional
from modules.cleaner import _normalize_str


@dataclass
class Alert:
    level: str          # "error", "warning", "info"
    title: str
    detail: str
    count: int = 0


def check_alerts(
    df: pd.DataFrame,
    col_map: dict,
    umbral_alerta_h: int = 24,
    umbral_critico_h: int = 72,
) -> list[Alert]:
    """
    Analiza el DataFrame y retorna una lista de alertas ordenadas por severidad.
    """
    alerts: list[Alert] = []

    col_estado = col_map.get("estado")
    col_inc    = col_map.get("incidencia")

    # 1a. Pedidos en zona crítica (> umbral_critico_h)
    if "_tiempo_gestion_horas" in df.columns:
        criticos = df[df["_tiempo_gestion_horas"] > umbral_critico_h]
        if not criticos.empty:
            n = len(criticos)
            pct = round(n / len(df) * 100, 1)
            alerts.append(Alert(
                level="error" if pct > 20 else "warning",
                title=f"Críticos: tiempo > {umbral_critico_h}h",
                detail=f"{n} pedidos ({pct}%) superan el límite crítico de {umbral_critico_h} horas.",
                count=n,
            ))

    # 1b. Pedidos en zona de alerta (umbral_alerta_h < t <= umbral_critico_h)
    if "_tiempo_gestion_horas" in df.columns:
        en_riesgo = df[
            (df["_tiempo_gestion_horas"] > umbral_alerta_h) &
            (df["_tiempo_gestion_horas"] <= umbral_critico_h)
        ]
        if not en_riesgo.empty:
            n = len(en_riesgo)
            pct = round(n / len(df) * 100, 1)
            alerts.append(Alert(
                level="warning",
                title=f"En riesgo: tiempo entre {umbral_alerta_h}h y {umbral_critico_h}h",
                detail=f"{n} pedidos ({pct}%) están dentro de la zona de alerta.",
                count=n,
            ))

    # 2. Incidencias abiertas
    if col_inc and col_inc in df.columns:
        mask_inc = df[col_inc].notna() & (df[col_inc].astype(str).str.strip() != "")
        n_inc = int(mask_inc.sum())
        if n_inc > 0:
            pct_inc = round(n_inc / len(df) * 100, 1)
            alerts.append(Alert(
                level="error" if pct_inc > 15 else "warning",
                title="Incidencias registradas",
                detail=f"{n_inc} pedidos ({pct_inc}%) tienen novedades o incidencias activas.",
                count=n_inc,
            ))

    # 3. Pedidos sin estado
    if col_estado and col_estado in df.columns:
        sin_estado = df[col_estado].isna() | (df[col_estado].astype(str).str.strip() == "")
        n_sin = int(sin_estado.sum())
        if n_sin > 0:
            alerts.append(Alert(
                level="warning",
                title="Pedidos sin estado registrado",
                detail=f"{n_sin} pedidos no tienen estado actualizado.",
                count=n_sin,
            ))

    # 4. Pedidos con tiempo negativo (inconsistencia de fechas)
    if "_dias_total" in df.columns:
        negativos = df[df["_dias_total"] < 0]
        if not negativos.empty:
            alerts.append(Alert(
                level="warning",
                title="Inconsistencia de fechas detectada",
                detail=f"{len(negativos)} pedidos tienen fechas incoherentes (entrega antes de creación).",
                count=len(negativos),
            ))

    # 5. Tasa de entrega baja
    if "_entregado" in df.columns:
        total = len(df)
        entregados = int(df["_entregado"].sum())
        pct_ent = round(entregados / total * 100, 1) if total > 0 else 0
        if pct_ent < 50 and total > 10:
            alerts.append(Alert(
                level="warning",
                title="Tasa de entrega baja",
                detail=f"Solo el {pct_ent}% de los pedidos están marcados como entregados.",
                count=total - entregados,
            ))

    # Ordenar: errores primero
    alerts.sort(key=lambda a: 0 if a.level == "error" else 1)
    return alerts


def render_alert_banner(alerts: list[Alert]) -> str:
    """Retorna HTML con las alertas formateadas."""
    if not alerts:
        return ""

    icons = {"error": "🔴", "warning": "🟡", "info": "🔵"}
    colors = {
        "error":   ("rgba(231,76,60,0.1)",   "#C0392B"),
        "warning": ("rgba(243,156,18,0.1)",   "#D68910"),
        "info":    ("rgba(52,152,219,0.1)",    "#1B6CA8"),
    }

    html_parts = ['<div class="alert-container">']
    for alert in alerts:
        icon = icons.get(alert.level, "ℹ️")
        bg, border = colors.get(alert.level, ("#fff", "#999"))
        html_parts.append(f"""
        <div class="alert-box" style="background:{bg}; border-left: 4px solid {border};">
            <strong>{icon} {alert.title}</strong>
            <span style="float:right; font-weight:bold; color:{border};">{alert.count}</span>
            <br><small>{alert.detail}</small>
        </div>""")
    html_parts.append("</div>")
    return "\n".join(html_parts)


def get_delayed_orders(
    df: pd.DataFrame,
    col_map: dict,
    umbral_critico_h: int = 72,
) -> pd.DataFrame:
    """Retorna DataFrame filtrado con pedidos que superan el umbral crítico."""
    time_col = "_tiempo_gestion_horas" if "_tiempo_gestion_horas" in df.columns else "_dias_total"
    if time_col not in df.columns:
        return pd.DataFrame()
    threshold = umbral_critico_h if time_col == "_tiempo_gestion_horas" else umbral_critico_h / 24
    retrasados = df[df[time_col] > threshold].copy()

    display_cols = []
    for key in ["guia", "provincia_destino", "estado", "fecha_creacion",
                "fecha_entrega", "responsable", "cliente"]:
        col = col_map.get(key)
        if col and col in retrasados.columns:
            display_cols.append(col)

    if "_dias_total" in retrasados.columns:
        display_cols.append("_dias_total")

    if not display_cols:
        return retrasados

    return retrasados[display_cols].sort_values(
        "_dias_total", ascending=False, errors="ignore"
    ).head(200)
