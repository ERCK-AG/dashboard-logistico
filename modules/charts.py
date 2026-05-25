"""
charts.py — Todas las visualizaciones Plotly del dashboard.
v3 — fallback _tiempo_gestion_horas/24 en todos los charts de tiempo; fecha_ss en tendencia
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Optional
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from modules.cleaner import PROVINCE_COORDS, _normalize_str

# ---------------------------------------------------------------------------
# Paleta corporativa — Verde Logiktel
# ---------------------------------------------------------------------------
COLORS = {
    "primary":   "#1A7A3C",   # verde Logiktel
    "secondary": "#25A85A",   # verde claro
    "accent":    "#E5A817",   # dorado/ámbar — complementario del verde
    "success":   "#27AE60",   # verde éxito
    "warning":   "#E67E22",   # naranja
    "danger":    "#C0392B",   # rojo
    "light":     "#EAF5EE",   # verde muy claro (fondos)
    "dark":      "#1C2A1E",   # verde oscuro casi negro
    "muted":     "#6C8C74",   # verde grisáceo
}

# Escala secuencial verde
SEQUENTIAL = ["#C8E6D0", "#7DC898", "#3BAD6A", "#1A7A3C", "#0D4020"]
# Escala divergente verde → rojo
DIVERGING  = ["#C0392B", "#E67E22", "#F1C40F", "#27AE60", "#1A7A3C"]

PLOTLY_TEMPLATE = "plotly_white"


def _base_layout(title: str = "", height: int = 400) -> dict:
    return dict(
        template=PLOTLY_TEMPLATE,
        height=height,
        title=dict(text=title, font=dict(size=15, color=COLORS["dark"]), x=0.02),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Segoe UI, Arial", size=12, color=COLORS["dark"]),
        margin=dict(t=55, b=40, l=40, r=20),
    )


def _no_data_fig(message: str = "Sin datos suficientes") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=14, color=COLORS["muted"]),
    )
    fig.update_layout(**_base_layout())
    return fig


# ---------------------------------------------------------------------------
# 1. KPI Cards — retorna HTML string renderizado con st.markdown
# ---------------------------------------------------------------------------

def build_kpi_html(kpis: dict) -> str:
    def card(icon, label, value, sub="", color=COLORS["primary"]):
        return f"""
        <div class="kpi-card" style="border-top: 4px solid {color};">
            <div class="kpi-icon">{icon}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-label">{label}</div>
            {"<div class='kpi-sub'>" + sub + "</div>" if sub else ""}
        </div>"""

    t_prom = (
        f"{kpis['tiempo_promedio_dias']} días"
        if kpis.get("tiempo_promedio_dias") is not None
        else "—"
    )
    cumpl = (
        f"{kpis['cumplimiento_pct']}%"
        if kpis.get("cumplimiento_pct") is not None
        else "—"
    )

    cards = [
        card("📦", "Total Pedidos",   kpis["total"],           color=COLORS["primary"]),
        card("✅", "Entregados",      kpis["entregados"],       f"{kpis['pct_entregados']}%", COLORS["success"]),
        card("🕐", "Pendientes",      kpis["pendientes"],       color=COLORS["warning"]),
        card("⚠️", "Con Incidencia",  kpis["incidencias"],      f"{kpis['pct_incidencias']}%", COLORS["danger"]),
        card("⏱️", "T. Prom. Entrega", t_prom,                  color=COLORS["secondary"]),
        card("🎯", "Cumplimiento SLA", cumpl,
             f"Umbral = {kpis.get('umbral_critico_h', 72)}h", COLORS["accent"]),
    ]

    return '<div class="kpi-row">' + "".join(cards) + "</div>"


# ---------------------------------------------------------------------------
# 2. Entregas por Provincia
# ---------------------------------------------------------------------------

def chart_entregas_por_provincia(
    df: pd.DataFrame,
    col_map: dict,
    top_n: int = 15,
) -> go.Figure:
    col = col_map.get("provincia_destino")
    if not col or col not in df.columns:
        return _no_data_fig("Sin columna de Provincia Destino")

    counts = df[col].value_counts().head(top_n).reset_index()
    counts.columns = ["Provincia", "Pedidos"]

    fig = px.bar(
        counts,
        x="Pedidos",
        y="Provincia",
        orientation="h",
        color="Pedidos",
        color_continuous_scale=["#C8E8F8", "#5DCFEF", "#00AEEF", "#0090CC", "#005F8E"],
        text="Pedidos",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        **_base_layout("Pedidos por Provincia Destino", 420),
        coloraxis_showscale=False,
        xaxis_title="",
        yaxis_title="",
        yaxis=dict(autorange="reversed"),
    )
    return fig


# ---------------------------------------------------------------------------
# 3. Heatmap de Incidencias por Provincia
# ---------------------------------------------------------------------------

def chart_heatmap_incidencias(df: pd.DataFrame, col_map: dict) -> go.Figure:
    col_inc = col_map.get("incidencia")
    col_dest = col_map.get("provincia_destino")

    if not col_inc or not col_dest:
        return _no_data_fig("Sin columnas de Incidencia o Provincia")
    if col_inc not in df.columns or col_dest not in df.columns:
        return _no_data_fig("Columnas no disponibles en datos")

    mask = df[col_inc].notna() & (df[col_inc].astype(str).str.strip() != "")
    df_inc = df[mask].copy()
    if df_inc.empty:
        return _no_data_fig("No hay incidencias registradas")

    pivot = (
        df_inc.groupby([col_dest, col_inc])
        .size()
        .reset_index(name="count")
        .pivot(index=col_dest, columns=col_inc, values="count")
        .fillna(0)
    )

    # Limitar para legibilidad
    pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).head(12).index]
    pivot = pivot[pivot.sum().sort_values(ascending=False).head(10).index]

    fig = px.imshow(
        pivot,
        color_continuous_scale="YlOrRd",
        aspect="auto",
        text_auto=True,
    )
    fig.update_layout(
        **_base_layout("Heatmap de Incidencias por Provincia", 480),
        xaxis_title="Tipo Incidencia",
        yaxis_title="Provincia",
    )
    return fig


# ---------------------------------------------------------------------------
# 4. Tendencia Diaria / Semanal
# ---------------------------------------------------------------------------

def chart_tendencia(df: pd.DataFrame, col_map: dict, freq: str = "D") -> go.Figure:
    # Prioridad: fecha_creacion → fecha_ss (FECHA SS) → fecha_entrega → fecha_estado
    col_fecha = (
        col_map.get("fecha_creacion")
        or col_map.get("fecha_ss")
        or col_map.get("fecha_entrega")
        or col_map.get("fecha_estado")
    )
    if not col_fecha or col_fecha not in df.columns:
        return _no_data_fig("Sin columna de fecha para tendencia")

    series = df[col_fecha].dropna()
    if series.empty:
        return _no_data_fig("Sin fechas disponibles")

    label = "Diaria" if freq == "D" else "Semanal"
    counts = (
        df.set_index(col_fecha)
        .resample(freq)
        .size()
        .reset_index(name="Pedidos")
    )
    counts.columns = ["Fecha", "Pedidos"]

    # Línea de entregados
    if "_entregado" in df.columns:
        entregados_ts = (
            df[df["_entregado"]]
            .set_index(col_fecha)
            .resample(freq)
            .size()
            .reset_index(name="Entregados")
        )
        entregados_ts.columns = ["Fecha", "Entregados"]
        counts = counts.merge(entregados_ts, on="Fecha", how="left").fillna(0)
    else:
        counts["Entregados"] = 0

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=counts["Fecha"], y=counts["Pedidos"],
        name="Total Pedidos",
        line=dict(color="#00AEEF", width=2.5),
        fill="tozeroy", fillcolor="rgba(0,174,239,0.12)",
    ))
    fig.add_trace(go.Scatter(
        x=counts["Fecha"], y=counts["Entregados"],
        name="Entregados",
        line=dict(color="#005F8E", width=2, dash="dot"),
    ))
    fig.update_layout(
        **_base_layout(f"Tendencia {label} de Pedidos", 380),
        xaxis_title="",
        yaxis_title="Cantidad",
        legend=dict(orientation="h", y=1.1, x=0),
    )
    return fig


# ---------------------------------------------------------------------------
# 5. Distribución por Estado
# ---------------------------------------------------------------------------

def chart_estado_distribucion(df: pd.DataFrame, col_map: dict) -> go.Figure:
    col = col_map.get("estado")
    if not col or col not in df.columns:
        return _no_data_fig("Sin columna de Estado")

    counts = df[col].value_counts().reset_index()
    counts.columns = ["Estado", "Cantidad"]

    fig = px.pie(
        counts,
        names="Estado",
        values="Cantidad",
        color_discrete_sequence=[
            "#00AEEF", "#005F8E", "#5DCFEF", "#0077B6",
            "#90E0EF", "#0090CC", "#ADE8F4", "#03045E",
            "#48CAE4", "#023E8A",
        ],
        hole=0.45,
    )
    fig.update_traces(textposition="outside", textinfo="label+percent")
    fig.update_layout(
        **_base_layout("Distribución por Estado Logístico", 400),
        showlegend=False,
    )
    return fig


# ---------------------------------------------------------------------------
# 6. Top Provincias con Retrasos
# ---------------------------------------------------------------------------

def chart_top_retrasos(
    df: pd.DataFrame, col_map: dict, sla_dias: int = 3, top_n: int = 10
) -> go.Figure:
    col_dest = col_map.get("provincia_destino")
    if not col_dest or col_dest not in df.columns:
        return _no_data_fig("Sin columna de Provincia Destino")

    # Columna de tiempo: _dias_total → fallback _tiempo_gestion_horas/24
    if "_dias_total" in df.columns:
        t_col = "_dias_total"
    elif "_tiempo_gestion_horas" in df.columns:
        df = df.copy()
        df["_t_dias"] = df["_tiempo_gestion_horas"] / 24
        t_col = "_t_dias"
    else:
        return _no_data_fig("Sin información de tiempos")

    retrasos = df[df[t_col] > sla_dias].copy()
    if retrasos.empty:
        return _no_data_fig("Sin retrasos detectados")

    grouped = (
        retrasos.groupby(col_dest)
        .agg(
            promedio=(t_col, "mean"),
            cantidad=(t_col, "count"),
        )
        .reset_index()
        .sort_values("promedio", ascending=False)
        .head(top_n)
    )
    grouped.columns = ["Provincia", "Días Promedio", "Pedidos Retrasados"]
    grouped["Días Promedio"] = grouped["Días Promedio"].round(1)

    fig = px.bar(
        grouped,
        x="Provincia",
        y="Días Promedio",
        color="Pedidos Retrasados",
        color_continuous_scale="Reds",
        text="Días Promedio",
    )
    fig.add_hline(y=sla_dias, line_dash="dash", line_color=COLORS["danger"],
                  annotation_text=f"SLA {sla_dias}d")
    fig.update_traces(textposition="outside")
    fig.update_layout(
        **_base_layout(f"Top Provincias con Mayor Retraso (SLA = {sla_dias} días)", 420),
        xaxis_title="",
        yaxis_title="Días Promedio",
        coloraxis_showscale=False,
    )
    return fig


# ---------------------------------------------------------------------------
# 7. Embudo Logístico
# ---------------------------------------------------------------------------

def chart_embudo_logistico(df: pd.DataFrame, col_map: dict) -> go.Figure:
    stages = []
    n = len(df)
    stages.append(("Pedidos Recibidos", n))

    col_despacho = col_map.get("fecha_despacho")
    col_entrega  = col_map.get("fecha_entrega")
    col_inc      = col_map.get("incidencia")

    if col_despacho and col_despacho in df.columns:
        n_desp = int(df[col_despacho].notna().sum())
        stages.append(("Despachados", n_desp))

    if col_entrega and col_entrega in df.columns:
        n_entr = int(df[col_entrega].notna().sum())
        stages.append(("En Tránsito / Entregados", n_entr))

    entregados = int(df.get("_entregado", pd.Series(False)).sum())
    stages.append(("Entregados", entregados))

    if col_inc and col_inc in df.columns:
        n_inc = int(df[col_inc].notna().sum())
        stages.append(("Con Incidencia", n_inc))

    labels = [s[0] for s in stages]
    values = [s[1] for s in stages]

    fig = go.Figure(go.Funnel(
        y=labels,
        x=values,
        textinfo="value+percent initial",
        marker=dict(color=[
            COLORS["primary"], COLORS["secondary"], COLORS["accent"],
            COLORS["success"], COLORS["danger"],
        ][:len(stages)]),
    ))
    fig.update_layout(**_base_layout("Embudo Logístico", 380))
    return fig


# ---------------------------------------------------------------------------
# 8. Ranking de Tiempos de Entrega
# ---------------------------------------------------------------------------

def chart_ranking_tiempos(df: pd.DataFrame, col_map: dict, top_n: int = 10) -> go.Figure:
    col_dest = col_map.get("provincia_destino")
    if not col_dest or col_dest not in df.columns:
        return _no_data_fig("Sin columna de Provincia Destino")

    t_col = "_dias_total" if "_dias_total" in df.columns else (
        "_tiempo_gestion_horas" if "_tiempo_gestion_horas" in df.columns else None)
    if t_col is None:
        return _no_data_fig("Sin información de tiempos")

    df = df.copy()
    if t_col == "_tiempo_gestion_horas":
        df["_t_dias"] = df["_tiempo_gestion_horas"] / 24
    else:
        df["_t_dias"] = df["_dias_total"]

    ranking = (
        df.groupby(col_dest)["_t_dias"]
        .agg(["mean", "min", "max", "count"])
        .reset_index()
        .rename(columns={
            col_dest: "Provincia",
            "mean": "Promedio",
            "min": "Mínimo",
            "max": "Máximo",
            "count": "Pedidos",
        })
        .sort_values("Promedio")
        .head(top_n)
    )
    ranking = ranking.round(1)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Mínimo",
        x=ranking["Provincia"],
        y=ranking["Mínimo"],
        marker_color=COLORS["success"],
    ))
    fig.add_trace(go.Bar(
        name="Promedio",
        x=ranking["Provincia"],
        y=ranking["Promedio"],
        marker_color=COLORS["secondary"],
    ))
    fig.add_trace(go.Bar(
        name="Máximo",
        x=ranking["Provincia"],
        y=ranking["Máximo"],
        marker_color=COLORS["danger"],
    ))
    fig.update_layout(
        **_base_layout("Ranking de Tiempos de Entrega por Provincia (días)", 420),
        barmode="group",
        xaxis_title="",
        yaxis_title="Días",
        legend=dict(orientation="h", y=1.1),
    )
    return fig


# ---------------------------------------------------------------------------
# 9. Mapa Geográfico Ecuador
# ---------------------------------------------------------------------------

def chart_mapa_ecuador(df: pd.DataFrame, col_map: dict, metric: str = "volumen") -> go.Figure:
    col_dest = col_map.get("provincia_destino")
    col_inc  = col_map.get("incidencia")

    if not col_dest or col_dest not in df.columns:
        return _no_data_fig("Sin columna de Provincia para el mapa")

    # ── Métrica y paleta según selección ───────────────────────────────────
    if metric == "incidencias" and col_inc and col_inc in df.columns:
        mask   = df[col_inc].notna() & (df[col_inc].astype(str).str.strip() != "")
        counts = df[mask].groupby(col_dest).size().reset_index(name="valor")
        title       = "Incidencias por Provincia"
        color_label = "Incidencias"
        cscale      = [[0, "#FFF3CD"], [0.5, "#FF8C00"], [1, "#C0392B"]]
        fmt         = lambda v: f"{int(v)}"

    elif metric == "retrasos":
        # Prioridad: _dias_total → días de gestión (horas/24) → volumen
        if "_dias_total" in df.columns and df["_dias_total"].notna().any():
            counts = (df.groupby(col_dest)["_dias_total"]
                      .mean().round(1).reset_index(name="valor"))
            title = "Días Promedio Creación → Entrega"
        elif "_tiempo_gestion_horas" in df.columns and df["_tiempo_gestion_horas"].notna().any():
            counts = (df.groupby(col_dest)["_tiempo_gestion_horas"]
                      .mean().reset_index(name="valor"))
            counts["valor"] = (counts["valor"] / 24).round(1)
            title = "Días Promedio de Gestión"
        else:
            counts = df.groupby(col_dest).size().reset_index(name="valor")
            title  = "Volumen de Pedidos"
        color_label = "Días"
        cscale      = [[0, "#FFD700"], [0.5, "#FF8C00"], [1, "#C0392B"]]
        fmt         = lambda v: f"{v:.1f} d"

    else:  # volumen
        counts      = df.groupby(col_dest).size().reset_index(name="valor")
        title       = "Volumen de Pedidos por Provincia"
        color_label = "Pedidos"
        cscale      = [[0, "#D6E4F0"], [0.5, "#2D7DD2"], [1, "#0D2B4E"]]
        fmt         = lambda v: f"{int(v)}"

    counts.columns = ["Provincia", "valor"]

    # ── Coordenadas ────────────────────────────────────────────────────────
    rows = []
    for _, r in counts.iterrows():
        key   = str(r["Provincia"]).upper().strip()
        coord = PROVINCE_COORDS.get(key)
        if coord:
            rows.append({
                "provincia": r["Provincia"],
                "capital"  : coord["capital"],
                "lat"      : coord["lat"],
                "lon"      : coord["lon"],
                "valor"    : r["valor"],
            })
    if not rows:
        return _no_data_fig("No se pudieron mapear provincias a coordenadas")

    mdf  = pd.DataFrame(rows)
    vmin = mdf["valor"].min()
    vmax = mdf["valor"].max()
    rng  = max(vmax - vmin, 1e-9)

    # Tamaño proporcional: entre 18 px (mínimo) y 56 px (máximo)
    mdf["size_px"] = mdf["valor"].apply(
        lambda v: 18 + 38 * (v - vmin) / rng
    )
    mdf["label"]   = mdf.apply(
        lambda r: f"{r['capital']}\n{fmt(r['valor'])}", axis=1
    )

    # ── Figura Mapbox (carto-positron — sin token) ─────────────────────────
    fig = go.Figure()

    fig.add_trace(go.Scattermapbox(
        lat=mdf["lat"],
        lon=mdf["lon"],
        mode="markers+text",
        marker=go.scattermapbox.Marker(
            size=mdf["size_px"],
            color=mdf["valor"],
            colorscale=cscale,
            showscale=True,
            colorbar=dict(
                title=dict(text=color_label, font=dict(size=12, color=COLORS["dark"])),
                thickness=14,
                len=0.55,
                x=1.01,
                tickfont=dict(size=11),
            ),
            opacity=0.88,
            sizemode="diameter",
        ),
        text=mdf["capital"],
        textposition="top center",
        textfont=dict(size=10, color="#1A2744", family="Segoe UI, Arial"),
        customdata=np.stack([mdf["provincia"], mdf["valor"]], axis=-1),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            f"{color_label}: %{{customdata[1]}}<br>"
            "<extra></extra>"
        ),
        name="",
    ))

    fig.update_layout(
        mapbox=dict(
            style="carto-positron",
            center=dict(lat=-1.8, lon=-78.2),
            zoom=5.2,
        ),
        height=600,
        title=dict(
            text=f"<b>{title}</b>",
            font=dict(size=15, color=COLORS["dark"]),
            x=0.02, y=0.98,
        ),
        paper_bgcolor="white",
        margin=dict(t=50, b=0, l=0, r=0),
        showlegend=False,
        font=dict(family="Segoe UI, Arial"),
    )
    return fig


# ---------------------------------------------------------------------------
# 9b. Mapa de Rutas Pendientes (flechas origen → destino)
# ---------------------------------------------------------------------------

def chart_mapa_rutas_pendientes(
    df: pd.DataFrame,
    col_map: dict,
    min_horas: float = 0,
    color_by: str = "origen",   # "origen" | "urgencia"
    estados_sel: list | None = None,
    gestionista_sel: str | None = None,
) -> go.Figure:
    """
    Mapa de flujo mejorado: líneas curvas origen → destino para pedidos pendientes.
    Soporta filtros por tiempo, estado, gestionista y dos modos de color.
    """
    col_orig = col_map.get("provincia_origen")
    col_dest = col_map.get("provincia_destino")
    col_est  = col_map.get("estado")
    col_resp = col_map.get("responsable")

    if not col_orig or not col_dest:
        return _no_data_fig("Sin columnas de Provincia Origen/Destino")
    if col_orig not in df.columns or col_dest not in df.columns:
        return _no_data_fig("Columnas de provincia no disponibles")

    # ── 1. Filtrar pendientes ──────────────────────────────────────────────
    if "_entregado" in df.columns:
        df_pend = df[~df["_entregado"]].copy()
    else:
        df_pend = df.copy()

    # Filtro por tiempo mínimo pendiente
    if min_horas > 0 and "_tiempo_gestion_horas" in df_pend.columns:
        df_pend = df_pend[df_pend["_tiempo_gestion_horas"] >= min_horas]

    # Filtro por estado
    if estados_sel and col_est and col_est in df_pend.columns:
        df_pend = df_pend[df_pend[col_est].isin(estados_sel)]

    # Filtro por gestionista
    if gestionista_sel and col_resp and col_resp in df_pend.columns:
        df_pend = df_pend[df_pend[col_resp].astype(str) == gestionista_sel]

    if df_pend.empty:
        return _no_data_fig("Sin pedidos con los filtros seleccionados")

    # ── 2. Agrupar por ruta ────────────────────────────────────────────────
    agg_cols = [col_orig, col_dest]
    routes = (
        df_pend.dropna(subset=agg_cols)
        .groupby(agg_cols)
        .agg(
            count=("_entregado", "count"),
            horas_prom=("_tiempo_gestion_horas", "mean") if "_tiempo_gestion_horas" in df_pend.columns else ("_entregado", "count"),
        )
        .reset_index()
        .sort_values("count", ascending=False)
    )

    if routes.empty:
        return _no_data_fig("Sin rutas detectadas")

    max_c    = max(routes["count"].max(), 1)
    max_h    = routes["horas_prom"].max() if "horas_prom" in routes.columns and routes["horas_prom"].notna().any() else 1

    # ── 3. Paletas de color ────────────────────────────────────────────────
    PALETTE_ORIGEN = [
        "#E74C3C", "#2ECC71", "#3498DB", "#F39C12", "#9B59B6",
        "#1ABC9C", "#E67E22", "#2980B9", "#27AE60", "#8E44AD",
        "#D35400", "#16A085", "#C0392B", "#2471A3", "#117A65",
        "#F1C40F", "#884EA0", "#1F618D", "#196F3D", "#7D6608",
    ]
    orig_provinces = sorted(routes[col_orig].str.upper().str.strip().unique())
    orig_color_map = {p: PALETTE_ORIGEN[i % len(PALETTE_ORIGEN)]
                      for i, p in enumerate(orig_provinces)}

    def _urgency_color(h) -> str:
        """Escala celeste CNT por horas de gestión."""
        if pd.isna(h) or h < 24:  return "#5DCFEF"   # celeste claro  < 1 día
        if h < 48:                 return "#00AEEF"   # celeste CNT    1–2 días
        if h < 72:                 return "#0090CC"   # celeste medio  2–3 días
        return "#005F8E"                              # azul oscuro    > 3 días

    fig = go.Figure()
    legend_added: set[str] = set()

    # ── 4. Dibujar rutas ──────────────────────────────────────────────────
    for _, row in routes.iterrows():
        orig_key = str(row[col_orig]).upper().strip()
        dest_key = str(row[col_dest]).upper().strip()
        count    = int(row["count"])
        h_prom   = row.get("horas_prom", np.nan)

        co = PROVINCE_COORDS.get(orig_key)
        cd = PROVINCE_COORDS.get(dest_key)
        if not co or not cd:
            continue

        lat_o, lon_o = co["lat"], co["lon"]
        lat_d, lon_d = cd["lat"], cd["lon"]

        # Curva Bezier cuadrática
        mid_lat = (lat_o + lat_d) / 2 + (lon_d - lon_o) * 0.14
        mid_lon = (lon_o + lon_d) / 2 - (lat_d - lat_o) * 0.14
        n  = 35
        ts = [i / n for i in range(n + 1)]
        lats_b = [(1-t)**2*lat_o + 2*(1-t)*t*mid_lat + t**2*lat_d for t in ts]
        lons_b = [(1-t)**2*lon_o + 2*(1-t)*t*mid_lon + t**2*lon_d for t in ts]

        ratio = count / max_c
        lw    = 2.0 + 7.0 * ratio
        alpha = float(np.clip(0.55 + 0.40 * ratio, 0, 1))

        # Color según modo
        if color_by == "urgencia":
            base_hex  = _urgency_color(h_prom)
            leg_name  = ("< 1 día" if (pd.isna(h_prom) or h_prom < 24) else
                         "1–2 días" if h_prom < 48 else
                         "2–3 días" if h_prom < 72 else "> 3 días")
            leg_key   = leg_name
        else:
            base_hex = orig_color_map[orig_key]
            leg_name = co["capital"]
            leg_key  = orig_key

        r_c = int(base_hex[1:3], 16)
        g_c = int(base_hex[3:5], 16)
        b_c = int(base_hex[5:7], 16)
        col_rgba = f"rgba({r_c},{g_c},{b_c},{alpha:.2f})"

        show_leg = leg_key not in legend_added
        if show_leg:
            legend_added.add(leg_key)

        tiempo_txt = format_horas(h_prom) if not pd.isna(h_prom) else "—"
        hover_txt  = (f"<b>{co['capital']} → {cd['capital']}</b><br>"
                      f"Pedidos pendientes: <b>{count}</b><br>"
                      f"T. prom. gestión: <b>{tiempo_txt}</b>")

        fig.add_trace(go.Scattermapbox(
            lat=lats_b + [None], lon=lons_b + [None],
            mode="lines",
            line=dict(width=lw, color=col_rgba),
            name=leg_name, legendgroup=leg_key,
            showlegend=show_leg,
            hoverinfo="none",
        ))

        # Punto destino con etiqueta de cantidad
        fig.add_trace(go.Scattermapbox(
            lat=[lat_d], lon=[lon_d],
            mode="markers+text",
            marker=dict(size=18 + 6 * ratio, color=base_hex,
                        opacity=min(1.0, alpha + 0.15)),
            text=[f"  {count}"],
            textfont=dict(size=9, color="white", family="Segoe UI Bold"),
            textposition="middle right",
            customdata=[[hover_txt]],
            hovertemplate="%{customdata[0]}<extra></extra>",
            legendgroup=leg_key, showlegend=False,
        ))

    # ── 5. Marcadores origen ───────────────────────────────────────────────
    for orig_key in orig_provinces:
        if orig_key not in PROVINCE_COORDS:
            continue
        c     = PROVINCE_COORDS[orig_key]
        hex_c = orig_color_map[orig_key] if color_by == "origen" else "#1A2744"
        n_pend = int(df_pend[col_orig].str.upper().str.strip().eq(orig_key).sum())
        fig.add_trace(go.Scattermapbox(
            lat=[c["lat"]], lon=[c["lon"]],
            mode="markers+text",
            marker=dict(size=16, color=hex_c, opacity=0.95),
            text=[c["capital"]],
            textposition="top center",
            textfont=dict(size=9, color="#1A2744"),
            hovertemplate=(f"<b>{c['capital']}</b><br>"
                           f"Pedidos saliendo: {n_pend}<extra></extra>"),
            showlegend=False,
        ))

    # ── 6. Leyenda urgencia ordenada ───────────────────────────────────────
    if color_by == "urgencia":
        for lab, col_h in [("< 1 día", "#5DCFEF"), ("1–2 días", "#00AEEF"),
                            ("2–3 días", "#0090CC"), ("> 3 días", "#005F8E")]:
            if lab not in legend_added:
                continue
            fig.add_trace(go.Scattermapbox(
                lat=[None], lon=[None], mode="markers",
                marker=dict(size=10, color=col_h),
                name=lab, showlegend=True,
            ))

    total_pend = int(routes["count"].sum())
    n_rutas    = len(routes)
    color_label = "Urgencia (tiempo gestión)" if color_by == "urgencia" else "Provincia Origen"

    fig.update_layout(
        mapbox=dict(style="carto-positron", center=dict(lat=-1.8, lon=-78.2), zoom=5.5),
        height=640,
        title=dict(
            text=(f"<b>Pendientes de Retirar</b> — {total_pend} pedidos · "
                  f"{n_rutas} rutas"
                  + (f" · > {int(min_horas)}h" if min_horas > 0 else "")),
            font=dict(size=14, color=COLORS["dark"]), x=0.02, y=0.98,
        ),
        legend=dict(
            title=dict(text=color_label, font=dict(size=11)),
            bgcolor="rgba(255,255,255,0.88)", bordercolor="#CCCCCC",
            borderwidth=1, font=dict(size=10),
            x=0.01, y=0.01, xanchor="left", yanchor="bottom",
        ),
        paper_bgcolor="white",
        margin=dict(t=50, b=0, l=0, r=0),
        showlegend=True,
        font=dict(family="Segoe UI, Arial"),
    )
    return fig


# ---------------------------------------------------------------------------
# 10. Tabla Interactiva
# ---------------------------------------------------------------------------

def build_table_df(
    df: pd.DataFrame,
    col_map: dict,
    search_guia: str = "",
) -> pd.DataFrame:
    """
    Construye un DataFrame para mostrar en st.dataframe con columnas relevantes.
    """
    display_keys = [
        "guia", "estado", "provincia_origen", "provincia_destino",
        "fecha_creacion", "fecha_despacho", "fecha_entrega",
        "incidencia", "cliente", "transportista", "responsable", "observaciones",
    ]
    cols_to_show = []
    for key in display_keys:
        col = col_map.get(key)
        if col and col in df.columns:
            cols_to_show.append(col)

    if not cols_to_show:
        return df.head(500)

    # Agregar columnas calculadas si existen
    for calc_col in ["_dias_total", "_dias_transito", "_entregado"]:
        if calc_col in df.columns:
            cols_to_show.append(calc_col)

    table = df[cols_to_show].copy()

    # Renombrar columnas internas
    rename = {
        "_dias_total":   "Días Total",
        "_dias_transito": "Días Tránsito",
        "_entregado":    "Entregado",
    }
    table.rename(columns=rename, inplace=True)

    # Filtro de búsqueda: busca en Guía Y en Pedido (OR), sin regex
    q = search_guia.strip()
    if q:
        mask = pd.Series(False, index=table.index)
        for _sc in [col_map.get("guia"), col_map.get("pedido")]:
            if _sc and _sc in table.columns:
                mask = mask | table[_sc].astype(str).str.contains(
                    q, case=False, na=False, regex=False
                )
        table = table[mask]

    result = table.head(2000)
    result.index = range(1, len(result) + 1)
    return result


# ---------------------------------------------------------------------------
# 11. Tiempo Promedio por Estado (gauge-like bar)
# ---------------------------------------------------------------------------

def chart_tiempo_por_estado(kpis: dict) -> go.Figure:
    t_estados: Optional[pd.Series] = kpis.get("tiempo_por_estado")
    if t_estados is None or t_estados.empty:
        return _no_data_fig("Sin datos de tiempo por estado")

    fig = px.bar(
        x=t_estados.values,
        y=t_estados.index,
        orientation="h",
        color=t_estados.values,
        color_continuous_scale="Blues",
        text=[f"{v:.1f}d" for v in t_estados.values],
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        **_base_layout("Días Promedio por Estado Logístico", 380),
        xaxis_title="Días promedio",
        yaxis_title="",
        coloraxis_showscale=False,
        yaxis=dict(autorange="reversed"),
    )
    return fig


# ---------------------------------------------------------------------------
# 12. Indicador SLA (gauge)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 13. Tiempo promedio de entrega por Provincia ORIGEN  (nuevo)
# ---------------------------------------------------------------------------

def chart_tiempo_por_origen(
    df: pd.DataFrame, col_map: dict, sla_dias: int = 3
) -> go.Figure:
    """
    Barras horizontales: cuántos días promedio tarda un paquete en ser
    entregado según la provincia de ORIGEN.
    Verde = dentro del SLA | Naranja = cerca | Rojo = fuera.
    """
    col_orig = col_map.get("provincia_origen")
    if not col_orig or col_orig not in df.columns:
        return _no_data_fig("Sin columna de Provincia Origen")

    # Columna de tiempo: _dias_total → fallback _tiempo_gestion_horas/24
    if "_dias_total" in df.columns:
        t_col = "_dias_total"
    elif "_tiempo_gestion_horas" in df.columns:
        df = df.copy()
        df["_t_dias"] = df["_tiempo_gestion_horas"] / 24
        t_col = "_t_dias"
    else:
        return _no_data_fig("Sin información de tiempos de entrega")

    g = (
        df.dropna(subset=[t_col])
        .groupby(col_orig)[t_col]
        .agg(Promedio="mean", Mínimo="min", Máximo="max", Pedidos="count")
        .reset_index()
        .rename(columns={col_orig: "Origen"})
        .sort_values("Promedio", ascending=True)
        .round(1)
    )
    if g.empty:
        return _no_data_fig("Sin datos suficientes")

    def _color(v):
        if v <= sla_dias:
            return COLORS["success"]
        elif v <= sla_dias * 1.5:
            return COLORS["warning"]
        return COLORS["danger"]

    g["Color"] = g["Promedio"].apply(_color)

    fig = go.Figure()
    src_lbl = "Gestión" if t_col == "_t_dias" else "Creación → Entrega"
    fig.add_trace(go.Bar(
        y=g["Origen"],
        x=g["Promedio"],
        orientation="h",
        marker_color=g["Color"].tolist(),
        text=g.apply(lambda r: f"{r['Promedio']:.1f} d  ({int(r['Pedidos'])} envíos)", axis=1),
        textposition="outside",
        customdata=g[["Mínimo", "Máximo", "Pedidos"]].values,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Promedio: %{x:.1f} días<br>"
            "Mínimo: %{customdata[0]:.1f} d | Máximo: %{customdata[1]:.1f} d<br>"
            "Pedidos: %{customdata[2]}<extra></extra>"
        ),
    ))
    fig.add_vline(
        x=sla_dias, line_dash="dash", line_color=COLORS["danger"], line_width=2,
        annotation_text=f"SLA {sla_dias}d", annotation_position="top right",
    )
    fig.update_layout(
        **_base_layout(f"⏱️ Días Promedio {src_lbl} por Provincia Origen", 460),
        xaxis_title="Días promedio",
        yaxis_title="",
        showlegend=False,
        xaxis=dict(range=[0, g["Promedio"].max() * 1.25]),
    )
    return fig


# ---------------------------------------------------------------------------
# 14. Heatmap origen × destino de tiempos  (nuevo)
# ---------------------------------------------------------------------------

def chart_heatmap_tiempos_od(df: pd.DataFrame, col_map: dict) -> go.Figure:
    """
    Heatmap: filas = provincia origen, columnas = provincia destino,
    valor = días promedio de entrega.
    """
    col_orig = col_map.get("provincia_origen")
    col_dest = col_map.get("provincia_destino")
    if not col_orig or not col_dest:
        return _no_data_fig("Sin columnas de Provincia Origen/Destino")
    if col_orig not in df.columns or col_dest not in df.columns:
        return _no_data_fig("Columnas de provincia no disponibles")

    # Columna de tiempo: _dias_total → fallback _tiempo_gestion_horas/24
    if "_dias_total" in df.columns:
        t_col = "_dias_total"
    elif "_tiempo_gestion_horas" in df.columns:
        df = df.copy()
        df["_t_dias"] = df["_tiempo_gestion_horas"] / 24
        t_col = "_t_dias"
    else:
        return _no_data_fig("Sin información de tiempos")

    pivot = (
        df.dropna(subset=[t_col])
        .groupby([col_orig, col_dest])[t_col]
        .mean()
        .round(1)
        .reset_index()
        .pivot(index=col_orig, columns=col_dest, values=t_col)
    )
    if pivot.empty:
        return _no_data_fig("Sin datos para el heatmap")

    # Limitar a los 12 orígenes y 12 destinos con más volumen
    top_orig = (
        df.groupby(col_orig).size().sort_values(ascending=False).head(12).index.tolist()
    )
    top_dest = (
        df.groupby(col_dest).size().sort_values(ascending=False).head(12).index.tolist()
    )
    pivot = pivot.loc[
        [o for o in top_orig if o in pivot.index],
        [d for d in top_dest if d in pivot.columns],
    ]

    fig = px.imshow(
        pivot,
        color_continuous_scale="RdYlGn_r",
        aspect="auto",
        text_auto=True,
        labels=dict(x="Destino", y="Origen", color="Días prom."),
    )
    fig.update_traces(textfont_size=11)
    fig.update_layout(
        **_base_layout("Días Promedio por Ruta  Origen → Destino", 520),
        xaxis_title="Provincia Destino",
        yaxis_title="Provincia Origen",
        coloraxis_colorbar=dict(title="Días"),
    )
    return fig


# ---------------------------------------------------------------------------
# 15. Resumen por Estado (barras + métricas)  (nuevo)
# ---------------------------------------------------------------------------

def chart_resumen_por_estado(df: pd.DataFrame, col_map: dict) -> go.Figure:
    """
    Dos paneles: volumen por estado (con % del total) + tiempo promedio de gestión.
    Usa _tiempo_gestion_horas como fuente principal de tiempo.
    """
    col_est = col_map.get("estado")
    if not col_est or col_est not in df.columns:
        return _no_data_fig("Sin columna de Estado")

    # ── Conteo por estado ──────────────────────────────────────────────────
    agg   = df.groupby(col_est).size().reset_index(name="Pedidos")
    total = agg["Pedidos"].sum()
    agg["Pct"] = (agg["Pedidos"] / max(total, 1) * 100).round(1)

    # ── Tiempo promedio: prioridad _tiempo_gestion_horas ──────────────────
    if "_tiempo_gestion_horas" in df.columns and df["_tiempo_gestion_horas"].notna().any():
        t = df.groupby(col_est)["_tiempo_gestion_horas"].mean().reset_index(name="horas")
        agg = agg.merge(t, on=col_est, how="left")
        time_subtitle = "Tiempo Prom. Gestión (FECHA SS → FECHA ESTADO)"
    elif "_dias_total" in df.columns and df["_dias_total"].notna().any():
        t = (df.groupby(col_est)["_dias_total"].mean() * 24).reset_index(name="horas")
        agg = agg.merge(t, on=col_est, how="left")
        time_subtitle = "Tiempo Prom. Entrega (días)"
    else:
        agg["horas"] = np.nan
        time_subtitle = "Tiempo Promedio (sin datos)"

    agg = agg.sort_values("Pedidos", ascending=True)
    agg.rename(columns={col_est: "Estado"}, inplace=True)

    # ── Color barra izquierda según tipo de estado (paleta azul) ───────────
    def _vol_color(e: str) -> str:
        e = e.lower()
        # Estados positivos / finalizados → azul oscuro (más fuerte)
        if any(k in e for k in ["entregad", "completad", "finaliz", "exitoso"]):
            return "#005F8E"
        # Estados negativos → azul medio-oscuro
        if any(k in e for k in ["cancelad", "devuelt", "no entregad", "rechaz", "faltante"]):
            return "#003B5C"
        # Estados intermedios → celeste CNT
        if any(k in e for k in ["solicitud", "pendiente", "admitid"]):
            return "#5DCFEF"
        # Default → azul medio
        return "#00AEEF"

    # ── Color barra derecha según duración (paleta azul) ───────────────────
    def _time_color(h) -> str:
        if pd.isna(h):  return "#C8E8F8"   # azul muy claro (sin dato)
        if h <= 24:     return "#5DCFEF"   # celeste claro — rápido
        if h <= 72:     return "#00AEEF"   # azul CNT — medio
        return "#005F8E"                   # azul oscuro — lento

    bar_colors  = [_vol_color(e)  for e in agg["Estado"]]
    time_colors = [_time_color(h) for h in agg["horas"]]
    time_texts  = agg["horas"].apply(format_horas)
    x_time      = agg["horas"].fillna(0)

    row_h = max(420, len(agg) * 46 + 100)

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Pedidos por Estado", time_subtitle),
        horizontal_spacing=0.14,
        column_widths=[0.52, 0.48],
    )

    # Barras volumen
    fig.add_trace(
        go.Bar(
            y=agg["Estado"], x=agg["Pedidos"],
            orientation="h",
            marker=dict(color=bar_colors, line=dict(width=0)),
            text=agg.apply(
                lambda r: f"  {int(r['Pedidos'])}  ({r['Pct']}%)", axis=1
            ),
            textposition="outside",
            textfont=dict(size=11, color=COLORS["dark"]),
            name="Pedidos",
            hovertemplate="<b>%{y}</b><br>Pedidos: %{x} (%{text})<extra></extra>",
        ),
        row=1, col=1,
    )

    # Barras tiempo
    fig.add_trace(
        go.Bar(
            y=agg["Estado"], x=x_time,
            orientation="h",
            marker=dict(color=time_colors, line=dict(width=0)),
            text=["  " + t for t in time_texts],
            textposition="outside",
            textfont=dict(size=11, color=COLORS["dark"]),
            name="Tiempo",
            hovertemplate="<b>%{y}</b><br>Tiempo prom: %{text}<extra></extra>",
        ),
        row=1, col=2,
    )

    fig.update_layout(
        **_base_layout("Análisis por Estado Logístico", row_h),
        showlegend=False,
    )
    fig.update_xaxes(showgrid=True, gridcolor="#ECF0F1", zeroline=False)
    fig.update_yaxes(tickfont_size=11)
    return fig


# ---------------------------------------------------------------------------
# Helpers de formato de tiempo
# ---------------------------------------------------------------------------

def format_horas(h) -> str:
    """Formatea horas numéricas → '2d 3h', '5h 30m', '45m', '—'."""
    try:
        h = float(h)
    except (TypeError, ValueError):
        return "—"
    if pd.isna(h) or h < 0:
        return "—"
    total_min = int(round(h * 60))
    d, rem = divmod(total_min, 1440)
    hr, mn = divmod(rem, 60)
    if d > 0:
        return f"{d}d {hr}h" if hr > 0 else f"{d}d"
    elif hr > 0:
        return f"{hr}h {mn}m" if mn > 0 else f"{hr}h"
    else:
        return f"{mn}m"


# ---------------------------------------------------------------------------
# 16. Distribución del Tiempo de Gestión (histograma)
# ---------------------------------------------------------------------------

def chart_distribucion_gestion(
    df: pd.DataFrame,
    col_map: dict,
    umbral_alerta_h: int = 24,
    umbral_critico_h: int = 72,
) -> go.Figure:
    """
    Histograma de tiempo de gestión mejorado:
    - Barras en celeste CNT por zona de urgencia
    - Bandas de fondo por zona
    - Líneas de media, mediana y P90
    - Líneas configurables de alerta y crítico
    - Resumen de conteo por zona en cabecera
    """
    if "_tiempo_gestion_horas" not in df.columns:
        return _no_data_fig("Sin datos de tiempo de gestión\n(FECHA SS → FECHA ESTADO)")

    data = df["_tiempo_gestion_horas"].dropna()
    data = data[data >= 0]
    if data.empty:
        return _no_data_fig("Sin valores válidos de tiempo de gestión")

    mean_h = float(data.mean())
    p50    = float(data.median())
    p90    = float(data.quantile(0.90))
    max_h  = float(data.max())
    n_tot  = len(data)

    # ── Zonas de urgencia (bandas de fondo) ───────────────────────────────
    ZONES = [
        ("< 1 día",  0,   24,  "#27AE60", "rgba(39,174,96,0.10)"),
        ("1–2 días", 24,  48,  "#F1C40F", "rgba(241,196,15,0.12)"),
        ("2–3 días", 48,  72,  "#E67E22", "rgba(230,126,34,0.12)"),
        ("> 3 días", 72, max_h + 1, "#E74C3C", "rgba(231,76,60,0.10)"),
    ]

    # ── Bineado manual — barras en celeste CNT con intensidad por zona ────
    n_bins = 28
    bins   = np.linspace(0, max_h, n_bins + 1)
    counts, edges = np.histogram(data, bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2
    widths  = edges[1:] - edges[:-1]

    # Celeste CNT: claro → oscuro según urgencia
    def _zone_color(h: float) -> str:
        if h < 24: return "#5DCFEF"   # celeste claro
        if h < 48: return "#00AEEF"   # celeste CNT principal
        if h < 72: return "#0090CC"   # celeste medio
        return "#005F8E"              # celeste oscuro

    bar_colors = [_zone_color(c) for c in centers]

    # ── Ticks eje X ────────────────────────────────────────────────────────
    if max_h <= 48:
        step = 6
    elif max_h <= 120:
        step = 12
    elif max_h <= 240:
        step = 24
    else:
        step = 48

    tick_vals = list(np.arange(0, max_h + step, step))
    tick_text = [format_horas(v) for v in tick_vals]

    fig = go.Figure()

    # ── 1. Bandas de fondo por zona ────────────────────────────────────────
    for name, z_min, z_max, col_hex, col_fill in ZONES:
        x1 = min(z_max, max_h + step)
        if z_min >= max_h:
            continue
        fig.add_vrect(
            x0=z_min, x1=x1,
            fillcolor=col_fill,
            layer="below",
            line_width=0,
        )

    # ── 2. Barras coloreadas ───────────────────────────────────────────────
    fig.add_trace(go.Bar(
        x=centers,
        y=counts,
        width=widths * 0.92,
        marker=dict(
            color=bar_colors,
            line=dict(color="white", width=0.4),
        ),
        name="Guías",
        hovertemplate=(
            "Tiempo: <b>%{customdata}</b><br>"
            "Guías: <b>%{y}</b><extra></extra>"
        ),
        customdata=[format_horas(c) for c in centers],
    ))

    # ── 3. Líneas estadísticas ─────────────────────────────────────────────
    stats = [
        (p50,    "dot",  "#2ECC71", f"Mediana {format_horas(p50)}",  "top left"),
        (mean_h, "dash", "#F39C12", f"Media {format_horas(mean_h)}",  "top right"),
        (p90,    "dashdot", "#E74C3C", f"P90 {format_horas(p90)}",   "top right"),
    ]
    for val, dash, color, label, pos in stats:
        if val <= max_h:
            fig.add_vline(
                x=val, line_dash=dash, line_color=color, line_width=2,
                annotation=dict(
                    text=label,
                    font=dict(size=10, color=color),
                    bgcolor="rgba(255,255,255,0.75)",
                    bordercolor=color,
                    borderwidth=1,
                    borderpad=3,
                ),
                annotation_position=pos,
            )

    # ── 4. Líneas de umbrales configurables ───────────────────────────────
    umbral_lines = [
        (umbral_alerta_h,  "longdashdot", "#E5A817",
         f"⚡ Alerta {format_horas(umbral_alerta_h)}", "bottom right"),
        (umbral_critico_h, "solid",       "#C0392B",
         f"🔴 Crítico {format_horas(umbral_critico_h)}", "bottom right"),
    ]
    for val, dash, color, label, pos in umbral_lines:
        if val <= max_h:
            fig.add_vline(
                x=val, line_dash=dash, line_color=color, line_width=2.5,
                annotation=dict(
                    text=label,
                    font=dict(size=10, color=color, family="Segoe UI"),
                    bgcolor="rgba(255,255,255,0.85)",
                    bordercolor=color,
                    borderwidth=1,
                    borderpad=3,
                ),
                annotation_position=pos,
            )

    # ── 5. Resumen por zona — centrado sobre cada banda (en franja inferior) ─
    # Se posicionan justo debajo del área de barras (y=-0.18) para no tapar
    # el título ni las barras altas del primer segmento.
    zone_labels = []
    for (name, z_min, z_max, col_hex, _) in ZONES:
        if z_min >= max_h:
            continue
        z_actual_max = min(z_max, max_h + step)
        z_center     = (z_min + z_actual_max) / 2
        n_z   = int(((data >= z_min) & (data < z_max)).sum())
        pct_z = round(n_z / n_tot * 100)
        zone_labels.append(dict(
            x=z_center, y=-0.20,
            xref="x", yref="paper",
            text=f"<b style='color:{col_hex}'>{name}</b>  {n_z} ({pct_z}%)",
            showarrow=False,
            font=dict(size=10, color=COLORS["dark"], family="Segoe UI"),
            align="center",
            bgcolor="rgba(255,255,255,0.90)",
            bordercolor=col_hex,
            borderwidth=1,
            borderpad=4,
            yanchor="top",
        ))

    fig.update_layout(
        **_base_layout("Distribución del Tiempo de Gestión", 440),
        xaxis_title="Tiempo transcurrido  (FECHA SS → FECHA ESTADO)",
        yaxis_title="N° de guías",
        bargap=0.04,
        showlegend=False,
        annotations=zone_labels,
        xaxis=dict(
            tickvals=tick_vals,
            ticktext=tick_text,
            tickangle=0,
            showgrid=True,
            gridcolor="#ECF0F1",
        ),
        yaxis=dict(showgrid=True, gridcolor="#ECF0F1"),
    )
    fig.update_layout(margin=dict(t=50, b=90, l=50, r=20))
    return fig


# ---------------------------------------------------------------------------
# 17. Horas promedio de gestión por Estado Actual
# ---------------------------------------------------------------------------

def chart_gestion_por_estado(df: pd.DataFrame, col_map: dict) -> go.Figure:
    """Barras horizontales: tiempo promedio de gestión agrupado por Estado Actual."""
    if "_tiempo_gestion_horas" not in df.columns:
        return _no_data_fig("Sin datos de tiempo de gestión")

    col_est = col_map.get("estado")
    if not col_est or col_est not in df.columns:
        return _no_data_fig("Sin columna de Estado Actual")

    g = (
        df.dropna(subset=["_tiempo_gestion_horas"])
        .query("_tiempo_gestion_horas >= 0")
        .groupby(col_est)["_tiempo_gestion_horas"]
        .agg(Promedio="mean", Pedidos="count", Maximo="max")
        .reset_index()
        .rename(columns={col_est: "Estado"})
        .sort_values("Promedio", ascending=True)
        .round(1)
    )
    if g.empty:
        return _no_data_fig("Sin datos suficientes por estado")

    def _color(v):
        if v <= 24:   return COLORS["success"]
        if v <= 72:   return COLORS["warning"]
        return COLORS["danger"]

    g["Color"]       = g["Promedio"].apply(_color)
    g["label_prom"]  = g["Promedio"].apply(format_horas)
    g["label_max"]   = g["Maximo"].apply(format_horas)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=g["Estado"],
        x=g["Promedio"],
        orientation="h",
        marker=dict(color=g["Color"].tolist(), line=dict(width=0)),
        text=g.apply(
            lambda r: f"  {r['label_prom']}  ({int(r['Pedidos'])} guías)", axis=1
        ),
        textposition="outside",
        textfont=dict(size=11, color=COLORS["dark"]),
        customdata=g[["Pedidos", "label_max", "label_prom"]].values,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Promedio: %{customdata[2]}<br>"
            "Máximo:   %{customdata[1]}<br>"
            "Guías:    %{customdata[0]}<extra></extra>"
        ),
    ))
    fig.update_layout(
        **_base_layout("T. Promedio de Gestión por Estado", max(360, len(g) * 42 + 80)),
        xaxis_title="Horas (escala interna)",
        xaxis=dict(
            showticklabels=False,   # ocultar números de horas crudas
            showgrid=False,
            zeroline=False,
        ),
        yaxis_title="",
        showlegend=False,
    )
    return fig


# ---------------------------------------------------------------------------
# 18. Tabla de detalle de gestión
# ---------------------------------------------------------------------------

def build_gestion_table_df(
    df: pd.DataFrame,
    col_map: dict,
    search_guia: str = "",
    ascending: bool = False,
    max_rows: int = 2000,
) -> pd.DataFrame:
    """
    DataFrame formateado para la tabla de tiempos de gestión.
    Columnas: Guía | Pedido | P.Destino | Estado | Detalle | Fecha SS | Fecha Estado | Tiempo
    Ordenado por _tiempo_gestion_horas (desc por defecto).
    """
    col_guia   = col_map.get("guia")
    col_pedido = col_map.get("pedido")
    col_estado = col_map.get("estado")
    col_fss    = col_map.get("fecha_ss")
    col_fest   = col_map.get("fecha_estado")
    col_dest   = col_map.get("provincia_destino")
    col_orig   = col_map.get("provincia_origen")
    col_det    = col_map.get("detalle_estado")
    col_nrv    = col_map.get("nro_visitas")
    col_rv1    = col_map.get("resultado_visita1")
    col_pv1    = col_map.get("primera_visita")
    col_resp   = col_map.get("responsable")

    # "_n_pedido" es una columna sintética añadida en app.py por lookup
    # cruzando con las hojas de especialidad (PEDIDO ↔ GUIA 1/2/3).
    col_n_pedido = "_n_pedido" if "_n_pedido" in df.columns else None

    cols_spec = [
        (col_guia,      "Guía"),
        (col_n_pedido,  "N° Pedido"),
        (col_pedido,    "Pedido"),
        (col_orig,      "P. Origen"),
        (col_dest,      "P. Destino"),
        (col_estado,    "Estado"),
        (col_det,       "Detalle Estado"),
        (col_nrv,       "N° Visitas"),
        (col_pv1,       "1ª Visita"),
        (col_rv1,       "Resultado 1ª Visita"),
        (col_fss,       "Fecha SS"),
        (col_fest,      "Fecha Estado"),
        (col_resp,      "Gestionista"),
    ]
    cols_present = [(c, lbl) for c, lbl in cols_spec if c and c in df.columns]
    real_cols  = [c for c, _ in cols_present]
    rename_map = {c: lbl for c, lbl in cols_present}

    working = df.copy()

    # Sort by gestión time
    if "_tiempo_gestion_horas" in working.columns:
        working = working.sort_values(
            "_tiempo_gestion_horas", ascending=ascending, na_position="last"
        )

    # Search filter: busca en Guía, Pedido lógico y N° Pedido (lookup) — OR sin regex
    q = search_guia.strip()
    if q:
        mask = pd.Series(False, index=working.index)
        for _sc in [col_guia, col_map.get("pedido"), "_n_pedido"]:
            if _sc and _sc in working.columns:
                mask = mask | working[_sc].astype(str).str.contains(
                    q, case=False, na=False, regex=False
                )
        working = working[mask]

    tbl = working[real_cols].copy() if real_cols else working.head(max_rows).copy()

    # Add formatted time column (aligned by index)
    if "_tiempo_gestion_horas" in working.columns:
        tbl["_h"] = working["_tiempo_gestion_horas"]
        tbl["Tiempo Transcurrido"] = tbl["_h"].apply(format_horas)
        tbl.drop(columns=["_h"], inplace=True)

    tbl.rename(columns=rename_map, inplace=True)

    # Format datetime columns
    for fc_lbl in ["Fecha SS", "Fecha Estado", "1ª Visita"]:
        if fc_lbl in tbl.columns:
            tbl[fc_lbl] = pd.to_datetime(tbl[fc_lbl], errors="coerce").dt.strftime(
                "%d/%m/%Y %H:%M"
            )

    result = tbl.head(max_rows)
    result.index = range(1, len(result) + 1)
    return result


def chart_envios_tiempo_por_provincia(
    df: pd.DataFrame, col_map: dict, top_n: int = 15
) -> go.Figure:
    """
    Barras horizontales agrupadas por provincia destino:
    - Barra azul   → N° de envíos   (eje X inferior)
    - Barra naranja → Días promedio de gestión (eje X superior)
    Ordenado de mayor a menor envíos.
    """
    col_dest = col_map.get("provincia_destino")
    if not col_dest or col_dest not in df.columns:
        return _no_data_fig("Sin columna de Provincia Destino")

    grp = df.dropna(subset=[col_dest]).groupby(col_dest)
    cnt = grp.size().reset_index(name="Envíos")

    # Tiempo promedio (horas → días)
    if "_tiempo_gestion_horas" in df.columns:
        t = grp["_tiempo_gestion_horas"].mean().reset_index(name="h")
        t["Días Prom"]  = (t["h"] / 24).round(1)
        t["Label Días"] = t["h"].apply(format_horas)
        merged = cnt.merge(t[[col_dest, "Días Prom", "Label Días"]], on=col_dest, how="left")
    elif "_dias_total" in df.columns:
        t = grp["_dias_total"].mean().reset_index(name="Días Prom")
        t["Días Prom"]  = t["Días Prom"].round(1)
        t["Label Días"] = t["Días Prom"].apply(lambda v: f"{v:.1f}d")
        merged = cnt.merge(t, on=col_dest, how="left")
    else:
        merged = cnt.copy()
        merged["Días Prom"]  = np.nan
        merged["Label Días"] = "—"

    merged = (
        merged
        .rename(columns={col_dest: "Provincia"})
        .sort_values("Envíos", ascending=True)
        .tail(top_n)
    )

    # ── Figura con doble eje X ─────────────────────────────────────────────
    fig = go.Figure()

    # Barra envíos → xaxis (inferior) — celeste CNT
    fig.add_trace(go.Bar(
        y=merged["Provincia"],
        x=merged["Envíos"],
        orientation="h",
        name="N° Envíos",
        xaxis="x",
        marker=dict(color="#00AEEF", opacity=0.88),
        text=merged["Envíos"].astype(str),
        textposition="outside",
        textfont=dict(size=10, color=COLORS["dark"]),
    ))

    # Barra días → xaxis2 (superior) — celeste oscuro CNT
    has_days = "Días Prom" in merged.columns and merged["Días Prom"].notna().any()
    if has_days:
        fig.add_trace(go.Bar(
            y=merged["Provincia"],
            x=merged["Días Prom"],
            orientation="h",
            name="Días Prom. Gestión",
            xaxis="x2",
            marker=dict(color="#0077B6", opacity=0.75),
            text=merged["Label Días"],
            textposition="outside",
            textfont=dict(size=10, color=COLORS["dark"]),
        ))

    row_h = max(400, len(merged) * 42 + 120)
    fig.update_layout(
        **_base_layout("Envíos y Tiempo de Gestión por Provincia Destino", row_h),
        barmode="overlay",
        bargap=0.28,
        legend=dict(orientation="h", y=1.06, x=0, font=dict(size=10)),
        xaxis=dict(
            title=dict(text="N° Envíos", font=dict(color="#00AEEF")),
            side="bottom",
            showgrid=True,
            gridcolor="#ECF0F1",
            tickfont=dict(color="#00AEEF"),
        ),
        xaxis2=dict(
            title=dict(
                text="Días Prom. Gestión" if has_days else "",
                font=dict(color="#0077B6"),
            ),
            overlaying="x",
            side="top",
            showgrid=False,
            tickfont=dict(color="#0077B6"),
        ),
        yaxis=dict(title="", tickfont=dict(size=10)),
    )
    fig.update_layout(margin=dict(t=80, b=50, l=10, r=60))
    return fig


# ---------------------------------------------------------------------------
# Ranking de Gestionistas
# ---------------------------------------------------------------------------

def chart_ranking_gestionistas(
    df: pd.DataFrame,
    col_map: dict,
) -> tuple[go.Figure, pd.DataFrame]:
    """
    Barras horizontales: N° pedidos por gestionista, coloreadas por % entregados.
    Retorna (figura, tabla_resumen).
    """
    col_resp = col_map.get("responsable")
    if not col_resp or col_resp not in df.columns:
        return _no_data_fig("Sin columna de Responsable / Gestionista"), pd.DataFrame()

    grp = df.dropna(subset=[col_resp]).groupby(col_resp)

    summary = grp.size().reset_index(name="Pedidos")
    summary.rename(columns={col_resp: "Gestionista"}, inplace=True)

    # % Entregados
    if "_entregado" in df.columns:
        ent = (df[df["_entregado"] == True]
               .dropna(subset=[col_resp])
               .groupby(col_resp).size()
               .reset_index(name="Entregados"))
        ent.rename(columns={col_resp: "Gestionista"}, inplace=True)
        summary = summary.merge(ent, on="Gestionista", how="left").fillna(0)
        summary["Entregados"] = summary["Entregados"].astype(int)
        summary["% Entregados"] = (summary["Entregados"] / summary["Pedidos"] * 100).round(1)
    else:
        summary["% Entregados"] = 0.0

    # Tiempo promedio de gestión
    if "_tiempo_gestion_horas" in df.columns:
        tp = (df.dropna(subset=[col_resp])
              .groupby(col_resp)["_tiempo_gestion_horas"]
              .mean()
              .reset_index(name="H_Prom"))
        tp.rename(columns={col_resp: "Gestionista"}, inplace=True)
        summary = summary.merge(tp, on="Gestionista", how="left")
        summary["T. Prom. Gestión"] = summary["H_Prom"].apply(
            lambda h: format_horas(h) if pd.notna(h) else "—"
        )
    else:
        summary["T. Prom. Gestión"] = "—"

    # Incidencias (1ª visita)
    if "_incidencia" in df.columns:
        inc = (df[df["_incidencia"] == True]
               .dropna(subset=[col_resp])
               .groupby(col_resp).size()
               .reset_index(name="Incidencias"))
        inc.rename(columns={col_resp: "Gestionista"}, inplace=True)
        summary = summary.merge(inc, on="Gestionista", how="left").fillna(0)
        summary["Incidencias"] = summary["Incidencias"].astype(int)
    else:
        summary["Incidencias"] = 0

    summary = summary.sort_values("Pedidos", ascending=True)

    # ── Figura ────────────────────────────────────────────────────────────────
    row_h = max(380, len(summary) * 46 + 120)
    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=summary["Gestionista"],
        x=summary["Pedidos"],
        orientation="h",
        name="Total Pedidos",
        marker=dict(
            color=summary["% Entregados"],
            colorscale=[
                [0.0,  "#C0392B"],   # rojo   — 0% entregados
                [0.5,  "#00AEEF"],   # celeste— 50%
                [1.0,  "#005F8E"],   # azul   — 100%
            ],
            cmin=0, cmax=100,
            showscale=True,
            colorbar=dict(
                title=dict(text="% Entregados", font=dict(size=11)),
                thickness=14, len=0.6, x=1.02,
                ticksuffix="%",
            ),
        ),
        text=summary["Pedidos"].astype(str),
        textposition="outside",
        textfont=dict(size=10, color=COLORS["dark"]),
        customdata=summary[["% Entregados", "T. Prom. Gestión", "Incidencias"]].values,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Pedidos: <b>%{x}</b><br>"
            "Entregados: <b>%{customdata[0]}%</b><br>"
            "T. Prom. Gestión: <b>%{customdata[1]}</b><br>"
            "Incidencias 1ª visita: <b>%{customdata[2]}</b>"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        **_base_layout("Ranking de Gestionistas", row_h),
        xaxis_title="N° Pedidos",
        yaxis_title="",
        bargap=0.30,
        showlegend=False,
    )
    fig.update_layout(margin=dict(t=50, b=50, l=10, r=80))

    # Tabla resumen limpia
    cols_out = ["Gestionista", "Pedidos", "Entregados", "% Entregados",
                "T. Prom. Gestión", "Incidencias"]
    cols_out = [c for c in cols_out if c in summary.columns]
    return fig, summary[cols_out].sort_values("Pedidos", ascending=False).reset_index(drop=True)


def chart_sla_gauge(kpis: dict) -> go.Figure:
    val = kpis.get("cumplimiento_pct")
    if val is None:
        return _no_data_fig("Sin datos SLA")

    color = COLORS["success"] if val >= 80 else (COLORS["warning"] if val >= 60 else COLORS["danger"])

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=val,
        title={"text": f"Cumplimiento SLA ({kpis.get('umbral_critico_h', 72)}h)", "font": {"size": 14}},
        number={"suffix": "%", "font": {"size": 28, "color": color}},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": color},
            "steps": [
                {"range": [0, 60],   "color": "#FADBD8"},
                {"range": [60, 80],  "color": "#FDEBD0"},
                {"range": [80, 100], "color": "#D5F5E3"},
            ],
            "threshold": {
                "line": {"color": COLORS["danger"], "width": 3},
                "thickness": 0.75,
                "value": 80,
            },
        },
    ))
    fig.update_layout(height=280, margin=dict(t=40, b=10, l=20, r=20))
    return fig
