"""
kpis.py — Cálculo de todos los KPIs del dashboard logístico.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Optional

from modules.cleaner import DELIVERED_STATES, _normalize_str


def _col(col_map: dict, key: str) -> Optional[str]:
    return col_map.get(key)


# ---------------------------------------------------------------------------
# KPIs principales
# ---------------------------------------------------------------------------

def kpi_total_pedidos(df: pd.DataFrame) -> int:
    return len(df)


def kpi_entregados(df: pd.DataFrame) -> int:
    if "_entregado" in df.columns:
        return int(df["_entregado"].sum())
    return 0


def kpi_pendientes(df: pd.DataFrame) -> int:
    total = kpi_total_pedidos(df)
    entregados = kpi_entregados(df)
    return total - entregados


def kpi_con_incidencia(df: pd.DataFrame, col_map: dict) -> int:
    """Cuenta pedidos con incidencia de entrega (no se pudo entregar en primera visita)."""
    # Columna pre-calculada por cleaner.py (basada en palabras clave en estado/detalle)
    if "_incidencia" in df.columns:
        return int(df["_incidencia"].sum())
    # Fallback: columna de incidencia explícita del Excel
    col = _col(col_map, "incidencia")
    if col and col in df.columns:
        mask = df[col].notna() & (df[col].astype(str).str.strip() != "")
        return int(mask.sum())
    return 0


def kpi_tiempo_promedio_entrega(df: pd.DataFrame) -> Optional[float]:
    if "_dias_total" in df.columns:
        vals = df["_dias_total"].dropna()
        if not vals.empty:
            return round(float(vals.mean()), 1)
    return None


def kpi_cumplimiento_pct(df: pd.DataFrame, umbral_critico_h: int = 72) -> Optional[float]:
    """% de pedidos entregados dentro del umbral crítico (en horas)."""
    col = "_tiempo_gestion_horas" if "_tiempo_gestion_horas" in df.columns else None
    if col is None:
        return None
    entregados = df[df.get("_entregado", pd.Series(False, index=df.index)) == True]
    if entregados.empty:
        return None
    dentro = (entregados[col].dropna() <= umbral_critico_h).sum()
    return round(float(dentro / len(entregados) * 100), 1)


def kpi_provincia_mas_incidencias(df: pd.DataFrame, col_map: dict) -> Optional[str]:
    col_inc = _col(col_map, "incidencia")
    col_dest = _col(col_map, "provincia_destino")
    if not col_inc or not col_dest:
        return None
    if col_inc not in df.columns or col_dest not in df.columns:
        return None
    mask = df[col_inc].notna() & (df[col_inc].astype(str).str.strip() != "")
    series = df.loc[mask, col_dest]
    if series.empty:
        return None
    return str(series.value_counts().idxmax())


def kpi_provincia_mayor_retraso(
    df: pd.DataFrame, col_map: dict, umbral_critico_h: int = 72
) -> Optional[str]:
    col_dest = _col(col_map, "provincia_destino")
    if not col_dest or col_dest not in df.columns:
        return None
    time_col = "_tiempo_gestion_horas" if "_tiempo_gestion_horas" in df.columns else "_dias_total"
    if time_col not in df.columns:
        return None
    threshold = umbral_critico_h if time_col == "_tiempo_gestion_horas" else umbral_critico_h / 24
    retrasos = df[df[time_col] > threshold]
    if retrasos.empty:
        return None
    return str(retrasos.groupby(col_dest)[time_col].mean().idxmax())


def kpi_tiempo_por_estado(df: pd.DataFrame, col_map: dict) -> Optional[pd.Series]:
    col_est = _col(col_map, "estado")
    if not col_est or col_est not in df.columns:
        return None
    # Prioridad: _tiempo_gestion_horas (convertido a días) → _dias_total
    if "_tiempo_gestion_horas" in df.columns:
        return (
            df.groupby(col_est)["_tiempo_gestion_horas"]
            .mean()
            .div(24)
            .round(1)
            .sort_values(ascending=False)
        )
    if "_dias_total" in df.columns:
        return (
            df.groupby(col_est)["_dias_total"]
            .mean()
            .round(1)
            .sort_values(ascending=False)
        )
    return None


def kpi_tiempo_entre_provincias(
    df: pd.DataFrame, col_map: dict
) -> Optional[pd.DataFrame]:
    col_orig = _col(col_map, "provincia_origen")
    col_dest = _col(col_map, "provincia_destino")
    if not col_orig or not col_dest:
        return None
    if "_dias_total" not in df.columns:
        return None
    return (
        df.groupby([col_orig, col_dest])["_dias_total"]
        .agg(["mean", "count"])
        .rename(columns={"mean": "Días Promedio", "count": "Pedidos"})
        .round(1)
        .reset_index()
        .sort_values("Días Promedio", ascending=False)
    )


# ---------------------------------------------------------------------------
# Objeto consolidado de KPIs
# ---------------------------------------------------------------------------

def calculate_kpis(
    df: pd.DataFrame,
    col_map: dict,
    umbral_alerta_h: int = 24,
    umbral_critico_h: int = 72,
) -> dict:
    """Calcula y retorna todos los KPIs en un diccionario."""
    total = kpi_total_pedidos(df)
    entregados = kpi_entregados(df)
    pendientes = kpi_pendientes(df)
    incidencias = kpi_con_incidencia(df, col_map)
    t_promedio = kpi_tiempo_promedio_entrega(df)
    cumplimiento = kpi_cumplimiento_pct(df, umbral_critico_h)
    prov_incidencias = kpi_provincia_mas_incidencias(df, col_map)
    prov_retraso = kpi_provincia_mayor_retraso(df, col_map, umbral_critico_h)
    t_estados = kpi_tiempo_por_estado(df, col_map)
    t_provincias = kpi_tiempo_entre_provincias(df, col_map)

    return {
        "total": total,
        "entregados": entregados,
        "pendientes": pendientes,
        "incidencias": incidencias,
        "pct_entregados": round(entregados / total * 100, 1) if total else 0,
        "pct_incidencias": round(incidencias / total * 100, 1) if total else 0,
        "tiempo_promedio_dias": t_promedio,
        "cumplimiento_pct": cumplimiento,
        "umbral_alerta_h": umbral_alerta_h,
        "umbral_critico_h": umbral_critico_h,
        "provincia_mas_incidencias": prov_incidencias,
        "provincia_mayor_retraso": prov_retraso,
        "tiempo_por_estado": t_estados,
        "tiempo_entre_provincias": t_provincias,
    }
