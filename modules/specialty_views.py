"""
specialty_views.py — Lógica de visualización para hojas de especialidad.

Tipos de hoja reconocidos:
  "logistica"  → ENVIOS CENTRO DE DISTRIBUCION / ENVIOS ENTRE PROVINCIAS
                 (columnas: FECHA, PROVINCIA ORIGEN, PROVINCIA DESTINO,
                  CANTIDAD, PESO, PEDIDO, DETALLE, GUIA 1, GUIA 2 …)

  "telefonia"  → ENVIOS TELEFONIA MOVIL
                 (columnas: Fecha documento, Material, Texto breve,
                  Cantidad de pedido, Por entregar, Centro, Nombre 1,
                  GUIA 1, GUIA 2 …)
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional

from modules.charts import COLORS, _base_layout, _no_data_fig, format_horas


# ---------------------------------------------------------------------------
# Helpers de columnas — tolerantes a encoding (U+FFFD) y mayúsculas
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    """Normaliza para comparación: lower + sin tildes + sin U+FFFD."""
    return (
        str(s).lower()
        .replace("�", "")
        .replace("ó", "o").replace("é", "e").replace("á", "a")
        .replace("í", "i").replace("ú", "u").replace("ñ", "n")
        .strip()
    )


def find_col(df: pd.DataFrame, *candidates: str) -> Optional[str]:
    """
    Retorna el nombre REAL de la primera columna que coincida con algún
    candidato (comparación normalizada). Soporta partial-match como último recurso.
    """
    mapping = {_norm(c): c for c in df.columns}

    # 1) Coincidencia exacta normalizada
    for cand in candidates:
        n = _norm(cand)
        if n in mapping:
            return mapping[n]

    # 2) Partial match: la columna contiene todas las palabras del candidato
    for cand in candidates:
        words = _norm(cand).split()
        for col_n, col_real in mapping.items():
            if all(w in col_n for w in words):
                return col_real

    return None


def _fix_col_name(col: str) -> str:
    """Arregla columnas con caracteres de reemplazo para mostrar en UI."""
    return (
        col.replace("DIRECCI�N", "DIRECCIÓN")
           .replace("TELEF�NO", "TELÉFONO")
           .replace("Almac�", "Almacén")
           .replace("�", "?")
    )


def clean_display_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Renombra columnas para mostrar en st.dataframe sin caracteres extraños."""
    rename = {c: _fix_col_name(c) for c in df.columns if "�" in c}
    if rename:
        return df.rename(columns=rename)
    return df


# ---------------------------------------------------------------------------
# Detección de tipo de hoja
# ---------------------------------------------------------------------------

def detect_type(df: pd.DataFrame, sheet_name: str) -> str:
    """
    Retorna: "logistica" | "telefonia" | "unknown"
    Usa el nombre de la hoja y las columnas disponibles.
    """
    nm = _norm(sheet_name)

    # Por nombre
    if "telefon" in nm or "movil" in nm:
        return "telefonia"
    if any(k in nm for k in ("centro", "distribucion", "provincias", "envio")):
        return "logistica"

    # Por columnas
    has_texto_breve = find_col(df, "Texto breve", "texto breve") is not None
    has_fecha_doc   = find_col(df, "Fecha documento", "fecha documento") is not None
    has_prov_dest   = find_col(df, "PROVINCIA DESTINO", "provincia destino") is not None
    has_pedido      = find_col(df, "PEDIDO", "pedido") is not None

    if has_texto_breve or has_fecha_doc:
        return "telefonia"
    if has_prov_dest or has_pedido:
        return "logistica"

    return "unknown"


# ===========================================================================
# TIPO A — Logística (ENVIOS CENTRO DE DISTRIBUCION / ENTRE PROVINCIAS)
# ===========================================================================

def kpis_logistica(df: pd.DataFrame) -> dict:
    col_fecha = find_col(df, "FECHA", "fecha")
    col_ped   = find_col(df, "PEDIDO", "pedido")
    col_dest  = find_col(df, "PROVINCIA DESTINO", "provincia destino")
    col_orig  = find_col(df, "PROVINCIA ORIGEN", "provincia origen")
    col_g1    = find_col(df, "GUIA 1", "guia 1", "guia1")

    total          = len(df)
    pedidos_unicos = int(df[col_ped].nunique())  if col_ped  else total
    destinos       = int(df[col_dest].nunique()) if col_dest else 0
    origenes       = int(df[col_orig].nunique()) if col_orig else 0

    guias = 0
    if col_g1 and col_g1 in df.columns:
        guias = int(df[col_g1].notna().sum())

    # Fecha más reciente
    fecha_max = "—"
    if col_fecha and col_fecha in df.columns:
        try:
            dates = pd.to_datetime(df[col_fecha], errors="coerce").dropna()
            if not dates.empty:
                fecha_max = dates.max().strftime("%d/%m/%Y")
        except Exception:
            pass

    return {
        "total":          total,
        "pedidos_unicos": pedidos_unicos,
        "destinos":       destinos,
        "origenes":       origenes,
        "guias":          guias,
        "fecha_max":      fecha_max,
    }


def chart_log_por_provincia(
    df: pd.DataFrame, col_name: str, title: str, top_n: int = 15
) -> go.Figure:
    col = find_col(df, col_name)
    if not col or col not in df.columns:
        return _no_data_fig(f"Sin columna '{col_name}'")

    counts = df[col].value_counts().head(top_n).reset_index()
    counts.columns = ["Provincia", "Envíos"]

    fig = px.bar(
        counts, x="Envíos", y="Provincia", orientation="h",
        color="Envíos",
        color_continuous_scale=["#C8E8F8", "#5DCFEF", "#00AEEF", "#0090CC", "#005F8E"],
        text="Envíos",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        **_base_layout(title, max(360, min(top_n, len(counts)) * 34 + 100)),
        coloraxis_showscale=False,
        xaxis_title="", yaxis_title="",
        yaxis=dict(autorange="reversed"),
    )
    return fig


def chart_log_tendencia(df: pd.DataFrame) -> go.Figure:
    col_fecha = find_col(df, "FECHA", "fecha")
    if not col_fecha:
        return _no_data_fig("Sin columna de fecha")
    try:
        df2 = df.copy()
        df2["_dt"] = pd.to_datetime(df2[col_fecha], errors="coerce")
        df2 = df2.dropna(subset=["_dt"])
        if df2.empty:
            return _no_data_fig("Sin fechas válidas")
        counts = (
            df2.set_index("_dt").resample("D").size()
            .reset_index(name="Envíos")
        )
        counts.columns = ["Fecha", "Envíos"]
        fig = go.Figure(go.Scatter(
            x=counts["Fecha"], y=counts["Envíos"],
            line=dict(color="#00AEEF", width=2.5),
            fill="tozeroy", fillcolor="rgba(0,174,239,0.12)",
            mode="lines+markers",
            marker=dict(size=7, color="#0077B6"),
            name="Envíos",
        ))
        fig.update_layout(
            **_base_layout("Envíos por Fecha", 320),
            xaxis_title="", yaxis_title="N° Envíos",
        )
        return fig
    except Exception as e:
        return _no_data_fig(f"Error en tendencia: {e}")


def chart_log_guias_donut(df: pd.DataFrame) -> go.Figure:
    """Donut: con guía asignada / sin guía."""
    col_g1 = find_col(df, "GUIA 1", "guia 1")
    if not col_g1 or col_g1 not in df.columns:
        return _no_data_fig("Sin columna de guía")

    con_guia = int(df[col_g1].notna().sum())
    sin_guia = len(df) - con_guia
    if con_guia + sin_guia == 0:
        return _no_data_fig("Sin datos")

    fig = go.Figure(go.Pie(
        labels=["Con Guía ✅", "Sin Guía ⏳"],
        values=[con_guia, sin_guia],
        hole=0.52,
        marker=dict(
            colors=["#00AEEF", "#E74C3C"],
            line=dict(color="white", width=2),
        ),
        textinfo="label+percent",
        textfont=dict(size=12),
        hovertemplate="<b>%{label}</b><br>%{value} envíos (%{percent})<extra></extra>",
        sort=False,
    ))
    fig.add_annotation(
        text=f"<b>{len(df)}</b><br><span style='font-size:11px'>envíos</span>",
        x=0.5, y=0.5, xref="paper", yref="paper",
        showarrow=False,
        font=dict(size=16, color="#1C2A1E"),
    )
    fig.update_layout(
        **_base_layout("Estado de Asignación de Guías", 300),
        showlegend=False,
    )
    fig.update_layout(margin=dict(t=45, b=10, l=10, r=10))
    return fig


# ===========================================================================
# TIPO B — Telefonía Móvil (ENVIOS TELEFONIA MOVIL)
# ===========================================================================

def kpis_telefonia(df: pd.DataFrame) -> dict:
    col_cant   = find_col(df, "Cantidad de pedido", "cantidad de pedido", "cantidad pedido")
    col_pend   = find_col(df, "Por entregar (cantidad)", "por entregar (cantidad)", "por entregar")
    col_g1     = find_col(df, "GUIA 1", "guia 1")
    col_centro = find_col(df, "Nombre 1", "nombre 1", "Centro", "centro")

    total = len(df)

    cant_total = 0
    if col_cant and col_cant in df.columns:
        cant_total = int(
            pd.to_numeric(df[col_cant], errors="coerce").fillna(0).sum()
        )

    cant_pendiente   = 0
    lineas_pendientes = 0
    # Prioridad: _pendiente_real (cross-reference con Estado de Gestión)
    if "_pendiente_real" in df.columns:
        pend_num = pd.to_numeric(df["_pendiente_real"], errors="coerce").fillna(0)
        cant_pendiente    = int(pend_num.sum())
        lineas_pendientes = int((pend_num > 0).sum())
    elif col_pend and col_pend in df.columns:
        pend_num = pd.to_numeric(df[col_pend], errors="coerce").fillna(0)
        cant_pendiente   = int(pend_num.sum())
        lineas_pendientes = int((pend_num > 0).sum())

    guias = 0
    if col_g1 and col_g1 in df.columns:
        guias = int(df[col_g1].notna().sum())

    centros = 0
    if col_centro and col_centro in df.columns:
        centros = int(df[col_centro].nunique())

    return {
        "total":              total,
        "lineas_pendientes":  lineas_pendientes,
        "cant_total":         cant_total,
        "cant_pendiente":     cant_pendiente,
        "guias":              guias,
        "centros":            centros,
    }


def chart_tel_top_materiales(df: pd.DataFrame, top_n: int = 15) -> go.Figure:
    col_mat  = find_col(df, "Texto breve", "texto breve", "Material", "material")
    col_cant = find_col(df, "Cantidad de pedido", "cantidad de pedido")

    if not col_mat or col_mat not in df.columns:
        return _no_data_fig("Sin columna de Material / Descripción")

    if col_cant and col_cant in df.columns:
        grp = (
            df.groupby(col_mat)[col_cant]
            .apply(lambda x: pd.to_numeric(x, errors="coerce").sum())
            .reset_index()
        )
        grp.columns = ["Material", "Unidades"]
    else:
        grp = df[col_mat].value_counts().reset_index()
        grp.columns = ["Material", "Unidades"]

    grp = grp.sort_values("Unidades", ascending=False).head(top_n)
    grp["Mat_short"] = grp["Material"].astype(str).str[:45]
    grp = grp.sort_values("Unidades", ascending=True)

    fig = px.bar(
        grp, x="Unidades", y="Mat_short", orientation="h",
        color="Unidades",
        color_continuous_scale=["#C8E8F8", "#00AEEF", "#005F8E"],
        text="Unidades",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        **_base_layout(f"Top {top_n} Materiales por Unidades Pedidas",
                       max(380, len(grp) * 36 + 100)),
        coloraxis_showscale=False,
        xaxis_title="Unidades", yaxis_title="",
    )
    return fig


def chart_tel_pendientes_por_centro(df: pd.DataFrame, top_n: int = 15) -> go.Figure:
    """
    Kilos pendientes por centro.
    kg_pendiente = PESO × (pendiente / Cantidad de pedido)

    PESO en este Excel es el peso TOTAL de la línea (no unitario), por lo que
    para obtener los kg pendientes se prorratea por la fracción aún por entregar.
    """
    col_centro = find_col(df, "Nombre 1", "nombre 1", "Centro", "centro")
    col_pend   = find_col(df, "Por entregar (cantidad)", "por entregar (cantidad)", "por entregar")
    col_cant   = find_col(df, "Cantidad de pedido", "cantidad de pedido")
    col_peso   = find_col(df, "PESO", "peso", "Peso")

    if not col_centro or col_centro not in df.columns:
        return _no_data_fig("Sin columna de Centro / Destino")
    if not col_peso or col_peso not in df.columns:
        return _no_data_fig("Sin columna PESO")
    if not col_cant or col_cant not in df.columns:
        return _no_data_fig("Sin columna 'Cantidad de pedido'")

    # Prioridad: _pendiente_real (cross-reference) → fallback Por entregar
    if "_pendiente_real" in df.columns:
        pend_source = "_pendiente_real"
    elif col_pend and col_pend in df.columns:
        pend_source = col_pend
    else:
        return _no_data_fig("Sin columna 'Por entregar (cantidad)'")

    df2 = df.copy()
    _pend_n = pd.to_numeric(df2[pend_source], errors="coerce").fillna(0)
    _cant_n = pd.to_numeric(df2[col_cant],    errors="coerce").fillna(0)
    _peso_n = pd.to_numeric(df2[col_peso],    errors="coerce").fillna(0)
    # Fracción aún por entregar (0 si cantidad = 0 para evitar dividir por cero)
    _frac   = (_pend_n / _cant_n.where(_cant_n > 0, 1)).clip(lower=0, upper=1)
    df2["_kg_pend"] = _peso_n * _frac

    grp = (
        df2[df2["_kg_pend"] > 0]
        .groupby(col_centro)["_kg_pend"]
        .sum()
        .reset_index()
        .rename(columns={col_centro: "Centro", "_kg_pend": "Kg Pendientes"})
        .sort_values("Kg Pendientes", ascending=True)
        .tail(top_n)
    )
    if grp.empty:
        return _no_data_fig("Sin kilos pendientes")

    grp["Kg Pendientes"] = grp["Kg Pendientes"].round(1)

    fig = px.bar(
        grp, x="Kg Pendientes", y="Centro", orientation="h",
        color="Kg Pendientes",
        color_continuous_scale=["#C8E8F8", "#5DCFEF", "#00AEEF", "#0077B6", "#005F8E"],
        text=grp["Kg Pendientes"].apply(lambda v: f"{v:,.1f} kg"),
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        **_base_layout("Kilos Pendientes por Centro",
                       max(360, len(grp) * 36 + 100)),
        coloraxis_showscale=False,
        xaxis_title="Kg pendientes", yaxis_title="",
    )
    return fig


def chart_tel_por_centro_total(df: pd.DataFrame, top_n: int = 15) -> go.Figure:
    """Barras: cantidad total pedida por centro (Nombre 1)."""
    col_centro = find_col(df, "Nombre 1", "nombre 1", "Centro", "centro")
    col_cant   = find_col(df, "Cantidad de pedido", "cantidad de pedido")

    if not col_centro or col_centro not in df.columns:
        return _no_data_fig("Sin columna de Centro")

    if col_cant and col_cant in df.columns:
        grp = (
            df.groupby(col_centro)[col_cant]
            .apply(lambda x: pd.to_numeric(x, errors="coerce").sum())
            .reset_index()
        )
        grp.columns = ["Centro", "Unidades"]
    else:
        grp = df[col_centro].value_counts().reset_index()
        grp.columns = ["Centro", "Unidades"]

    grp = (grp.sort_values("Unidades", ascending=True).tail(top_n))

    fig = px.bar(
        grp, x="Unidades", y="Centro", orientation="h",
        color="Unidades",
        color_continuous_scale=["#C8E8F8", "#5DCFEF", "#00AEEF", "#0090CC", "#005F8E"],
        text="Unidades",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        **_base_layout("Unidades Pedidas por Centro", max(360, len(grp) * 36 + 100)),
        coloraxis_showscale=False,
        xaxis_title="Unidades", yaxis_title="",
    )
    return fig


def chart_tel_tendencia(df: pd.DataFrame) -> go.Figure:
    col_fecha = find_col(df, "Fecha documento", "fecha documento", "FECHA", "fecha")
    col_cant  = find_col(df, "Cantidad de pedido", "cantidad de pedido")

    if not col_fecha or col_fecha not in df.columns:
        return _no_data_fig("Sin columna de fecha")
    try:
        df2 = df.copy()
        df2["_dt"] = pd.to_datetime(df2[col_fecha], errors="coerce")
        df2 = df2.dropna(subset=["_dt"])
        if df2.empty:
            return _no_data_fig("Sin fechas válidas")

        if col_cant and col_cant in df2.columns:
            df2[col_cant] = pd.to_numeric(df2[col_cant], errors="coerce").fillna(0)
            counts = (
                df2.set_index("_dt")[col_cant]
                .resample("D").sum()
                .reset_index()
            )
            counts.columns = ["Fecha", "Valor"]
            y_label = "Unidades pedidas"
        else:
            counts = (
                df2.set_index("_dt").resample("D").size()
                .reset_index(name="Valor")
            )
            counts.columns = ["Fecha", "Valor"]
            y_label = "N° Líneas"

        fig = go.Figure(go.Bar(
            x=counts["Fecha"], y=counts["Valor"],
            marker_color="#00AEEF", opacity=0.87, name=y_label,
        ))
        fig.update_layout(
            **_base_layout(f"{y_label} por Fecha de Documento", 340),
            xaxis_title="", yaxis_title=y_label,
        )
        return fig
    except Exception as e:
        return _no_data_fig(f"Error: {e}")


def chart_tel_pedido_vs_pendiente(df: pd.DataFrame) -> go.Figure:
    """Donut: entregado vs pendiente (usa _pendiente_real si disponible)."""
    col_cant = find_col(df, "Cantidad de pedido", "cantidad de pedido")
    col_pend = find_col(df, "Por entregar (cantidad)", "por entregar (cantidad)", "por entregar")

    if not col_cant:
        return _no_data_fig("Sin columnas de cantidad")

    total = pd.to_numeric(df[col_cant], errors="coerce").fillna(0).sum()

    # Prioridad: _pendiente_real (cross-reference) → fallback Por entregar
    if "_pendiente_real" in df.columns:
        pend = pd.to_numeric(df["_pendiente_real"], errors="coerce").fillna(0).sum()
    elif col_pend and col_pend in df.columns:
        pend = pd.to_numeric(df[col_pend], errors="coerce").fillna(0).sum()
    else:
        return _no_data_fig("Sin columnas de cantidad")

    entr = max(total - pend, 0)

    if total == 0:
        return _no_data_fig("Sin datos de cantidad")

    fig = go.Figure(go.Pie(
        labels=["Entregado ✅", "Pendiente ⏳"],
        values=[entr, pend],
        hole=0.52,
        marker=dict(
            colors=["#005F8E", "#5DCFEF"],   # azul oscuro / celeste claro
            line=dict(color="white", width=2),
        ),
        textinfo="label+percent",
        textfont=dict(size=12),
        hovertemplate="<b>%{label}</b><br>%{value:,.0f} unidades (%{percent})<extra></extra>",
        sort=False,
    ))
    fig.add_annotation(
        text=f"<b>{int(total):,}</b><br><span style='font-size:10px'>unidades</span>",
        x=0.5, y=0.5, xref="paper", yref="paper",
        showarrow=False, font=dict(size=16, color="#1C2A1E"),
    )
    fig.update_layout(
        **_base_layout("Estado de Entrega — Unidades", 300),
        showlegend=False,
    )
    fig.update_layout(margin=dict(t=45, b=10, l=10, r=10))
    return fig


# ---------------------------------------------------------------------------
# Tabla para mostrar en Streamlit
# ---------------------------------------------------------------------------

def build_display_table(df: pd.DataFrame, max_rows: int = 2000) -> pd.DataFrame:
    """
    Prepara DataFrame limpio para st.dataframe.
    • Arregla encoding U+FFFD en nombres de columna
    • Inserta columna "Estado Guía 1" (✅ Con Guía / ⏳ Sin Guía) tras GUIA 1
    • Formatea columnas de fecha: muestra solo DD/MM/YYYY, sin hora
    • Índice empieza en 1
    """
    df2 = clean_display_cols(df.copy()).head(max_rows)

    # ── Estado Guía 1 ─────────────────────────────────────────────────────
    col_g1 = find_col(df2, "GUIA 1", "guia 1", "GUIA1", "guia1")
    if col_g1 and col_g1 in df2.columns:
        guia_pos = list(df2.columns).index(col_g1)
        if "Estado Guía 1" in df2.columns:
            # Ya fue enriquecido por el caller con el estado real → solo reposicionar
            _val = df2.pop("Estado Guía 1")
            df2.insert(guia_pos + 1, "Estado Guía 1", _val)
        else:
            # Fallback: indica solo si tiene guía asignada o no
            _estado_g1 = df2[col_g1].apply(
                lambda x: "✅ Con Guía"
                if pd.notna(x) and str(x).strip() not in ("", "nan", "None")
                else "⏳ Sin Guía"
            )
            df2.insert(guia_pos + 1, "Estado Guía 1", _estado_g1)

    # ── Formato fecha: solo DD/MM/YYYY, sin hora ──────────────────────────
    for col in df2.columns:
        if pd.api.types.is_datetime64_any_dtype(df2[col]):
            # Columna ya es datetime → formatear directamente
            df2[col] = df2[col].dt.strftime("%d/%m/%Y").where(df2[col].notna(), other="")
        elif "fecha" in _norm(col) or _norm(col).startswith("date"):
            # Columna tipo object que puede contener fechas con hora
            try:
                parsed = pd.to_datetime(df2[col], errors="coerce")
                if parsed.notna().sum() > 0:
                    df2[col] = parsed.dt.strftime("%d/%m/%Y").where(
                        parsed.notna(), other=df2[col].astype(str)
                    )
            except Exception:
                pass

    # ── Todo en MAYÚSCULAS ────────────────────────────────────────────────
    from modules.charts import uppercase_table
    df2 = uppercase_table(df2)

    # ── Índice desde 1 ────────────────────────────────────────────────────
    df2.index = range(1, len(df2) + 1)
    return df2
