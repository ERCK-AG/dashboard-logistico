"""
app.py — Dashboard Logístico Profesional
BUSINESSPOINT S.A. — Transporte de Carga Liviana
Ejecutar: streamlit run app.py
"""

import base64, io, sys, time
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Dashboard Logístico | BUSINESSPOINT",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT_DIR   = Path(__file__).parent
ASSETS_DIR = ROOT_DIR / "assets"
sys.path.insert(0, str(ROOT_DIR))

# ── AUTENTICACIÓN ──────────────────────────────────────────────────────
# Esto debe ir ANTES de cargar datos, porque si el usuario no está
# autenticado se detiene la app aquí mismo.
from modules import auth
USER = auth.require_login()

# ── AUTO-REFRESH cada 2 horas ──────────────────────────────────────────
# Streamlit no auto-recarga páginas — sin esto, los datos solo se actualizan
# cuando el usuario interactúa con la app. Con este componente la app se
# refresca automáticamente cada N milisegundos, sin perder el estado.
try:
    from streamlit_autorefresh import st_autorefresh
    # 2 horas = 2 * 60 * 60 * 1000 = 7,200,000 ms
    st_autorefresh(
        interval=2 * 60 * 60 * 1000,
        limit=None,                  # repetir indefinidamente
        key="auto_refresh_2h",
    )
except ImportError:
    # Fallback si el paquete no está instalado (modo local sin la dependencia)
    pass

from modules.data_loader import get_data_with_refresh, find_latest_excel
from modules.kpis import calculate_kpis
from modules.charts import (
    chart_entregas_por_provincia, chart_heatmap_incidencias,
    chart_tendencia, chart_estado_distribucion, chart_top_retrasos,
    chart_embudo_logistico, chart_ranking_tiempos, chart_mapa_ecuador,
    chart_tiempo_por_estado, chart_sla_gauge, chart_tiempo_por_origen,
    chart_heatmap_tiempos_od, chart_resumen_por_estado, build_table_df,
    chart_distribucion_gestion, chart_gestion_por_estado,
    build_gestion_table_df, format_horas, chart_mapa_rutas_pendientes,
    chart_envios_tiempo_por_provincia, chart_ranking_gestionistas,
)
from modules.alerts import check_alerts, get_delayed_orders
from modules.cleaner import DELIVERED_STATES, _normalize_str as _ns
import modules.specialty_views as sv
from modules import overrides as ov

# ── CSS corporativo (modo claro) ───────────────────────────────────────────
st.markdown("""
<style>
/* Fondo general */
.main .block-container { padding: 1rem 1.6rem 2rem; max-width: 1600px; }
.stApp { background: #F2F6FB; }

/* ── KPI cards ── */
[data-testid="metric-container"] {
    background: white;
    border-radius: 12px;
    padding: 16px 18px 14px;
    box-shadow: 0 2px 12px rgba(26,122,60,0.10);
    border-left: 5px solid #1A7A3C;
    transition: box-shadow .2s, transform .15s;
}
[data-testid="metric-container"]:hover {
    box-shadow: 0 6px 20px rgba(26,122,60,0.18);
    transform: translateY(-2px);
}
[data-testid="stMetricValue"]  { font-size: 2rem !important; font-weight: 800 !important; color: #1C2A1E !important; }
[data-testid="stMetricLabel"]  { font-size: 0.7rem !important; font-weight: 700 !important;
                                  text-transform: uppercase; letter-spacing: .6px; color: #6C8C74 !important; }
[data-testid="stMetricDelta"]  { font-size: 0.82rem !important; font-weight: 600 !important; }

/* Colores de borde por posición */
div[data-testid="column"]:nth-child(1) [data-testid="metric-container"] { border-left-color: #1A7A3C; }
div[data-testid="column"]:nth-child(2) [data-testid="metric-container"] { border-left-color: #25A85A; }
div[data-testid="column"]:nth-child(3) [data-testid="metric-container"] { border-left-color: #E5A817; }
div[data-testid="column"]:nth-child(4) [data-testid="metric-container"] { border-left-color: #C0392B; }
div[data-testid="column"]:nth-child(5) [data-testid="metric-container"] { border-left-color: #1A7A3C; }
div[data-testid="column"]:nth-child(6) [data-testid="metric-container"] { border-left-color: #E5A817; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0D3320 0%, #1A7A3C 100%) !important;
    border-right: none;
}
section[data-testid="stSidebar"] * { color: #EAF0FB !important; }
/* Fondo blanco para todos los controles de entrada */
section[data-testid="stSidebar"] .stTextInput input,
section[data-testid="stSidebar"] .stNumberInput input,
section[data-testid="stSidebar"] .stDateInput input,
section[data-testid="stSidebar"] .stDateInput [data-baseweb="input"],
section[data-testid="stSidebar"] .stDateInput [data-baseweb="base-input"],
section[data-testid="stSidebar"] .stMultiSelect [data-baseweb="select"],
section[data-testid="stSidebar"] .stSelectbox  [data-baseweb="select"] {
    background: rgba(255,255,255,0.92) !important;
    border: 1px solid rgba(255,255,255,0.4) !important;
    border-radius: 8px !important;
}
/* Texto oscuro dentro de inputs — anula el * { color: #EAF0FB } */
section[data-testid="stSidebar"] .stTextInput input,
section[data-testid="stSidebar"] .stNumberInput input,
section[data-testid="stSidebar"] .stDateInput input,
section[data-testid="stSidebar"] .stMultiSelect input,
section[data-testid="stSidebar"] .stMultiSelect [data-baseweb="input"],
section[data-testid="stSidebar"] .stMultiSelect [data-baseweb="base-input"],
section[data-testid="stSidebar"] .stSelectbox  input,
section[data-testid="stSidebar"] .stSelectbox  [data-baseweb="input"],
section[data-testid="stSidebar"] .stSelectbox  [data-baseweb="base-input"],
section[data-testid="stSidebar"] .stSelectbox  [data-baseweb="select"] span,
section[data-testid="stSidebar"] .stMultiSelect [data-baseweb="tag"]  span,
section[data-testid="stSidebar"] .stMultiSelect [data-baseweb="tag"] {
    color: #1A2744 !important;
    font-weight: 600 !important;
}
section[data-testid="stSidebar"] .stNumberInput input,
section[data-testid="stSidebar"] .stDateInput  input {
    font-weight: 700 !important;
    font-size: 0.85rem !important;
}
section[data-testid="stSidebar"] .stTextInput    input::placeholder,
section[data-testid="stSidebar"] .stMultiSelect  input::placeholder,
section[data-testid="stSidebar"] .stSelectbox    input::placeholder {
    color: #7A94B0 !important;
    opacity: 1 !important;
}
section[data-testid="stSidebar"] label {
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: .5px;
    color: #A8DDB8 !important;
}
section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.15) !important; }
section[data-testid="stSidebar"] .stDownloadButton button {
    background: rgba(255,255,255,0.15) !important;
    border: 1px solid rgba(255,255,255,0.3) !important;
    color: white !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
section[data-testid="stSidebar"] .stDownloadButton button:hover {
    background: rgba(255,255,255,0.25) !important;
}
section[data-testid="stSidebar"] .stButton button {
    background: rgba(255,255,255,0.15) !important;
    border: 1px solid rgba(255,255,255,0.3) !important;
    color: white !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
section[data-testid="stSidebar"] .stButton button:hover {
    background: rgba(255,255,255,0.25) !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: white;
    border-radius: 10px;
    padding: 4px 6px;
    box-shadow: 0 1px 6px rgba(26,122,60,0.10);
    gap: 2px;
}
.stTabs [role="tab"] {
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    padding: 0.4rem 0.9rem !important;
    color: #6C8C74 !important;
}
.stTabs [aria-selected="true"] {
    background: #1A7A3C !important;
    color: white !important;
}

/* ── Cards de sección ── */
.sec-card {
    background: white;
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    box-shadow: 0 2px 10px rgba(26,122,60,0.07);
    margin-bottom: 1rem;
}

/* ── Alertas ── */
[data-testid="stAlert"] { border-radius: 10px !important; font-weight: 500 !important; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────
def _logo_b64(path: Path) -> str | None:
    if path.exists():
        return base64.b64encode(path.read_bytes()).decode()
    return None

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

def _to_xlsx(df: pd.DataFrame) -> bytes:
    """Serializa un DataFrame a bytes .xlsx listo para st.download_button."""
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return buf.getvalue()


@st.cache_data(ttl=60, show_spinner=False)
def _cached_kpis(df: pd.DataFrame, col_map: dict,
                 umbral_alerta_h: int, umbral_critico_h: int) -> dict:
    """KPIs cacheados — evita recalcular en cada cambio de tab (mismo df → cache hit)."""
    return calculate_kpis(
        df, col_map,
        umbral_alerta_h=umbral_alerta_h,
        umbral_critico_h=umbral_critico_h,
    )

def sec(title: str, icon: str = ""):
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:8px;margin:1.1rem 0 .5rem'>"
        f"<div style='width:4px;height:22px;background:#1A7A3C;border-radius:3px'></div>"
        f"<span style='font-size:.92rem;font-weight:700;color:#1C2A1E;text-transform:uppercase;"
        f"letter-spacing:.4px'>{icon} {title}</span></div>",
        unsafe_allow_html=True,
    )


# ── Estado de sesión ───────────────────────────────────────────────────────
for k, v in [("umbral_alerta_h", 24), ("umbral_critico_h", 72)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Carga de datos ─────────────────────────────────────────────────────────
# df_raw  = data CON overrides aplicados (para reportes/KPIs)
# df_full = data COMPLETA sin overrides (para que la búsqueda encuentre
#           guías empatadas/anuladas)
with st.spinner("⏳ Cargando datos desde Excel…"):
    df_raw, col_map, specialty_dfs, warn_list, err_list, df_full = get_data_with_refresh(ROOT_DIR)

# Guarda defensiva: si el caché guardó el formato antiguo (2-tuplas en lugar de 3),
# lo limpia automáticamente y recarga sin interrumpir al usuario.
if specialty_dfs:
    _first_val = next(iter(specialty_dfs.values()))
    if not isinstance(_first_val, tuple) or len(_first_val) != 3:
        st.cache_data.clear()
        df_raw, col_map, specialty_dfs, warn_list, err_list, df_full = get_data_with_refresh(ROOT_DIR)

# Fallback: si df_full quedó None (error de carga), usar df_raw
if df_full is None:
    df_full = df_raw


# ── Enriquecimiento (N° Pedido + Agencia) ──────────────────────────────────
# Se calcula DENTRO de load_all_sheets (cacheado) por rendimiento — las
# columnas _n_pedido y _agencia ya vienen en df_raw. Ver data_loader._build_enrichment.


# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════
with st.sidebar:

    # Logos
    b64_emp = _logo_b64(ASSETS_DIR / "logo_empresa.png")
    b64_cnt = _logo_b64(ASSETS_DIR / "logo_cnt.png")

    if b64_emp or b64_cnt:
        logo_parts = ""
        if b64_emp:
            logo_parts += f"<img src='data:image/png;base64,{b64_emp}' style='height:48px;object-fit:contain'/>"
        if b64_cnt:
            logo_parts += f"<img src='data:image/png;base64,{b64_cnt}' style='height:48px;object-fit:contain'/>"
        st.markdown(
            f"<div style='display:flex;justify-content:center;align-items:center;"
            f"gap:16px;padding:14px 0 10px;background:rgba(255,255,255,0.1);"
            f"border-radius:10px;margin-bottom:10px'>{logo_parts}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='text-align:center;padding:16px 0 8px'>"
            "<div style='font-size:2.2rem'>📦</div></div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        "<div style='text-align:center;padding:4px 0 12px'>"
        "<div style='font-size:1.05rem;font-weight:800;letter-spacing:.3px'>BUSINESSPOINT S.A.</div>"
        "<div style='font-size:0.72rem;opacity:.7;margin-top:2px'>Jefatura Logística</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Usuario autenticado ──────────────────────────────────────────────
    _role_badges = {
        "admin":    ("👑 Admin",    "#E5A817"),
        "operador": ("🔧 Operador", "#00AEEF"),
        "viewer":   ("👁️ Consulta", "#6C8C74"),
    }
    _badge_label, _badge_color = _role_badges.get(
        USER["role"], ("Usuario", "#6C8C74")
    )
    st.markdown(
        f"<div style='background:rgba(255,255,255,0.12);border-radius:10px;"
        f"padding:10px 12px;margin-bottom:8px;text-align:center'>"
        f"<div style='font-size:0.85rem;font-weight:700;color:#EAF0FB'>👤 {USER['name']}</div>"
        f"<div style='display:inline-block;margin-top:4px;padding:2px 10px;"
        f"background:{_badge_color};color:white;border-radius:12px;"
        f"font-size:0.7rem;font-weight:700'>{_badge_label}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    auth.logout_button(USER, location="sidebar")
    st.divider()

    # Configuración
    st.markdown("**⚙️ CONFIGURACIÓN**")
    _ua1, _ua2 = st.columns(2)
    with _ua1:
        umbral_alerta_h = st.number_input(
            "⚡ Alerta (h)", min_value=1, max_value=240,
            value=st.session_state["umbral_alerta_h"], step=1,
        )
    with _ua2:
        umbral_critico_h = st.number_input(
            "🔴 Crítico (h)", min_value=1, max_value=720,
            value=st.session_state["umbral_critico_h"], step=1,
        )
    st.session_state["umbral_alerta_h"]  = umbral_alerta_h
    st.session_state["umbral_critico_h"] = umbral_critico_h
    if st.button("🔄 Refrescar datos ahora", use_container_width=True,
                 help="Descarga la última versión del Excel desde OneDrive"):
        st.cache_data.clear()
        st.rerun()
    st.caption("⏱️ Auto-refresh cada 2 horas")
    st.divider()

    if df_raw is None or df_raw.empty:
        st.error("Sin datos cargados")
        st.stop()

    # Búsqueda
    st.markdown("**🔍 BÚSQUEDA**")
    search_guia = st.text_input(
        "N° Guía o N° Pedido",
        placeholder="Ej: WYB174282285 o 4700317515",
        help="Busca por Guía o N° de Pedido. Ignora los filtros del sidebar.",
        label_visibility="collapsed",
    )
    st.divider()

    # Filtros
    st.markdown("**🎛️ FILTROS**")
    df = df_raw.copy()

    def _multi(key, label, icon=""):
        col = col_map.get(key)
        if col and col in df_raw.columns:
            opts = sorted(df_raw[col].dropna().astype(str).unique().tolist())
            if opts:
                return st.multiselect(f"{icon} {label}", opts, default=[],
                                      key=f"flt_{key}")
        return []

    col_fecha = col_map.get("fecha_creacion") or col_map.get("fecha_ss")
    if col_fecha and col_fecha in df.columns:
        mn, mx = df[col_fecha].dropna().min(), df[col_fecha].dropna().max()
        if pd.notna(mn) and pd.notna(mx):
            st.markdown("**📅 Rango de fechas**")
            fd1, fd2 = st.columns(2)
            with fd1:
                fecha_desde = st.date_input(
                    "Desde", value=mn.date(),
                    min_value=mn.date(), max_value=mx.date(),
                    key="fd_desde", label_visibility="visible",
                )
            with fd2:
                fecha_hasta = st.date_input(
                    "Hasta", value=mx.date(),
                    min_value=mn.date(), max_value=mx.date(),
                    key="fd_hasta", label_visibility="visible",
                )
            if fecha_desde <= fecha_hasta:
                df = df[df[col_fecha].between(
                    pd.Timestamp(fecha_desde),
                    pd.Timestamp(fecha_hasta),
                    inclusive="both",
                )]
            else:
                st.warning("⚠️ 'Desde' debe ser anterior a 'Hasta'")

    sel_orig   = _multi("provincia_origen",  "Provincia Origen",  "📍")
    sel_dest   = _multi("provincia_destino", "Provincia Destino", "📍")
    sel_estado = _multi("estado",            "Estado",            "🔖")
    sel_inc    = _multi("incidencia",        "Incidencia",        "⚠️")
    sel_resp   = _multi("responsable",       "Responsable",       "👤")
    sel_cli    = _multi("cliente",           "Cliente",           "🏢")
    sel_trans  = _multi("transportista",     "Transportista",     "🚚")

    for key, sel in [
        ("provincia_origen", sel_orig), ("provincia_destino", sel_dest),
        ("estado", sel_estado),         ("incidencia", sel_inc),
        ("responsable", sel_resp),      ("cliente", sel_cli),
        ("transportista", sel_trans),
    ]:
        c = col_map.get(key)
        if c and c in df.columns and sel:
            df = df[df[c].astype(str).isin(sel)]

    st.divider()

    total_raw = len(df_raw)
    total_fil = len(df)
    pct = round(total_fil / total_raw * 100) if total_raw else 0
    pct_bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))

    st.markdown(
        f"<div style='background:rgba(255,255,255,0.12);border-radius:10px;"
        f"padding:12px 14px;text-align:center'>"
        f"<div style='font-size:1.6rem;font-weight:800'>{total_fil:,}</div>"
        f"<div style='font-size:0.72rem;opacity:.75;margin-bottom:6px'>"
        f"pedidos filtrados de {total_raw:,} ({pct}%)</div>"
        f"<div style='font-size:0.55rem;letter-spacing:1px;color:#7CB9E8'>{pct_bar}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.divider()

    st.markdown("**💾 EXPORTAR**")
    try:
        st.download_button("⬇️ Descargar Excel", _to_xlsx(df),
                           "pedidos.xlsx", XLSX_MIME,
                           use_container_width=True)
    except Exception:
        pass

    st.divider()
    latest_file = find_latest_excel(ROOT_DIR)
    if latest_file:
        fdate = datetime.fromtimestamp(latest_file.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
        st.caption(f"📂 {latest_file.name}")
        st.caption(f"🕐 {fdate}")


# ═══════════════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════════════
latest_file = find_latest_excel(ROOT_DIR)
# Si la fuente es OneDrive (no hay archivo local), mostramos cuándo se cargó
# el dashboard. Si es archivo local, mostramos la fecha de modificación.
try:
    _excel_url_active = bool(st.secrets["onedrive"]["excel_url"].strip())
except Exception:
    _excel_url_active = False

if _excel_url_active:
    fname = "CONSOLIDADO JEFATURA LOGISTICA.xlsx (OneDrive)"
    fdate = datetime.now().strftime("%d/%m/%Y %H:%M") + " · cargado ahora"
elif latest_file:
    fname = latest_file.name
    fdate = datetime.fromtimestamp(latest_file.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
else:
    fname = "—"
    fdate = "—"

logo_html = ""
for lp in [ASSETS_DIR / "logo_empresa.png", ASSETS_DIR / "logo_cnt.png"]:
    b = _logo_b64(lp)
    if b:
        logo_html += (f"<img src='data:image/png;base64,{b}' "
                      f"style='height:42px;object-fit:contain;"
                      f"background:rgba(255,255,255,0.15);border-radius:8px;padding:4px 8px'/>")

st.markdown(
    f"<div style='background:linear-gradient(135deg,#0D3320 0%,#1A7A3C 55%,#25A85A 100%);"
    f"color:white;padding:1rem 1.8rem;border-radius:14px;margin-bottom:1.2rem;"
    f"display:flex;justify-content:space-between;align-items:center;"
    f"box-shadow:0 6px 20px rgba(13,51,32,.30)'>"
    f"<div style='display:flex;align-items:center;gap:16px'>"
    f"{'<div>' + logo_html + '</div>' if logo_html else '<span style=font-size:2rem>📦</span>'}"
    f"<div><div style='font-size:1.3rem;font-weight:800;letter-spacing:.2px'>"
    f"Panel Logístico — Transporte de Carga Liviana</div>"
    f"<div style='font-size:.8rem;opacity:.8;margin-top:3px'>BUSINESSPOINT SA | Jefatura Logística</div>"
    f"</div></div>"
    f"<div style='text-align:right;font-size:.75rem;opacity:.85'>"
    f"📂 <b>{fname}</b><br>🕐 Actualizado: {fdate}</div></div>",
    unsafe_allow_html=True,
)

# Errores críticos — detienen la app si los datos no se pueden cargar
if err_list:
    for e in err_list: st.error(f"❌ {e}")
    st.stop()
if df.empty:
    st.warning("⚠️ Sin datos con los filtros aplicados.")
    st.stop()
# NOTA: las advertencias (warn_list) NO se muestran aquí.
# Se muestran al FINAL de la página, justo antes del footer, para no
# saturar la parte superior del dashboard.


# ═══════════════════════════════════════════════════════════════════════════
# KPIs
# ═══════════════════════════════════════════════════════════════════════════
kpis = _cached_kpis(df, col_map, umbral_alerta_h, umbral_critico_h)

if "_tiempo_gestion_horas" in df.columns:
    _hv = df["_tiempo_gestion_horas"].dropna()
    _hv = _hv[_hv >= 0]
    t_prom  = format_horas(_hv.mean()) if not _hv.empty else "—"
    t_max   = format_horas(_hv.max())  if not _hv.empty else "—"
else:
    t_prom = (f"{kpis['tiempo_promedio_dias']} días"
              if kpis.get("tiempo_promedio_dias") is not None else "—")
    t_max  = "—"

# Incidencias 2ª visita
_col_rv2 = col_map.get("resultado_visita2")
if _col_rv2 and _col_rv2 in df.columns:
    _rv2 = df[_col_rv2].astype(str).str.strip()
    _rv2_filled = _rv2.ne("") & _rv2.ne("nan") & df[_col_rv2].notna()
    _rv2_not_del = ~_rv2.apply(lambda x: _ns(x) in DELIVERED_STATES)
    _inc_2v = int((_rv2_filled & _rv2_not_del).sum())
else:
    _inc_2v = 0
_pct_inc2v = round(_inc_2v / kpis["total"] * 100, 1) if kpis["total"] else 0

k1, k2, k3, k4, k5, k6 = st.columns(6)
with k1: st.metric("📦 Total Pedidos",     kpis["total"])
with k2: st.metric("✅ Entregados",        kpis["entregados"],  f"{kpis['pct_entregados']} %")
with k3: st.metric("🕐 Pendientes",        kpis["pendientes"],  f"-{kpis['pct_entregados']} %")
with k4: st.metric("⚠️ 1ª Visita Fallida", kpis["incidencias"], f"{kpis['pct_incidencias']} %")
with k5: st.metric("🔁 2ª Visita Fallida", _inc_2v,             f"{_pct_inc2v} %")
with k6: st.metric("⏱️ T. Prom. Gestión",  t_prom)

# Alertas operativas
alerts = check_alerts(df, col_map, umbral_alerta_h=umbral_alerta_h, umbral_critico_h=umbral_critico_h)
if alerts:
    st.markdown("<div style='margin-top:.6rem'>", unsafe_allow_html=True)
    for a in alerts:
        msg = f"**{a.title}** — {a.detail} *({a.count} pedidos)*"
        if   a.level == "error":   st.error(f"🔴 {msg}")
        elif a.level == "warning": st.warning(f"🟡 {msg}")
        else:                      st.info(f"🔵 {msg}")
    st.markdown("</div>", unsafe_allow_html=True)

st.divider()


# ═══════════════════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════════════════
# ── Normalizar claves de specialty_dfs a nombres canónicos ────────────────
# Usa detect_type (que ya funciona) para asignar el nombre correcto,
# sin depender de cómo esté escrito el nombre de la hoja en el Excel.
if specialty_dfs:
    _canonical_dfs: dict = {}
    for _k, _v in specialty_dfs.items():
        _raw_k, _, _ = _v
        _stype = sv.detect_type(_raw_k, _k)
        if _stype == "telefonia":
            _cname = "ENVÍOS TELEFONÍA MÓVIL"
        elif _stype == "logistica":
            _ku = _k.strip().upper()
            if "CENTRO" in _ku or "DISTRIBUC" in _ku:
                _cname = "ENVÍOS CENTRO DE DISTRIBUCIÓN"
            else:
                _cname = "ENVÍOS ENTRE PROVINCIAS"
        else:
            _cname = _k
        _canonical_dfs[_cname] = _v
    specialty_dfs = _canonical_dfs

# ── Tabs base (siempre presentes) + tabs de especialidad (dinámicos) ──────
# "Empates" y "Info" van al FINAL (después de los tabs de especialidad)
_BASE_TABS    = ["⏱️ Gestión", "📌 Por Estado", "🌎 Mapa", "📋 Detalle"]
_OVERRIDE_TAB = "🔄 Empates y Anulaciones"
_USERS_TAB    = "👥 Usuarios"
_INFO_TAB     = "ℹ️ Info"
# El tab Empates aparece siempre, pero el contenido se gatea por rol
_CAN_EDIT_OVERRIDES = auth.can_edit_overrides(USER)
_IS_ADMIN           = auth.is_admin(USER)

# Ícono por hoja de especialidad
def _sp_icon(name: str) -> str:
    n = name.lower()
    if "provincia" in n: return "🗺️"
    if any(k in n for k in ("telefon", "móvil", "movil", "pelicula", "pelic")): return "📱"
    if "centro" in n or "uio" in n: return "🏭"
    return "📦"


def _sp_display_name(name: str) -> str:
    """
    Devuelve un nombre canónico para la hoja de especialidad.
    Funciona aunque el nombre tenga tildes, caracteres U+FFFD o
    cualquier variante ortográfica.
    """
    # Quitar tildes explícitamente + carácter U+FFFD + pasar a minúsculas
    n = (
        name.lower()
        .replace("�", "")          # reemplazar U+FFFD (encoding roto)
        .replace("á", "a").replace("é", "e").replace("í", "i")
        .replace("ó", "o").replace("ú", "u").replace("ñ", "n")
    )
    # Buscar en mayúsculas sin modificar encoding:
    # "TELEFON" aparece antes del carácter especial en "TELEFONÍA/TELEFONIA"
    nu = name.strip().upper()
    if "TELEFON" in nu:
        return "ENVÍOS TELEFONÍA MÓVIL"
    if "CENTRO" in nu or "DISTRIBUC" in nu:
        return "ENVÍOS CENTRO DE DISTRIBUCIÓN"
    if "PROVINCIAS" in nu or "PROVINCIA" in nu:
        return "ENVÍOS ENTRE PROVINCIAS"
    return nu


_sp_names   = list(specialty_dfs.keys())          # hojas encontradas en el Excel
_sp_labels  = [f"{_sp_icon(n)} {_sp_display_name(n)}" for n in _sp_names]

# Orden final: [base...] + [especialidad...] + [Empates] + [Usuarios si admin] + [Info]
if _IS_ADMIN:
    _all_labels = _BASE_TABS + _sp_labels + [_OVERRIDE_TAB, _USERS_TAB, _INFO_TAB]
else:
    _all_labels = _BASE_TABS + _sp_labels + [_OVERRIDE_TAB, _INFO_TAB]

_all_tabs = st.tabs(_all_labels)
# Desempaquetado: 4 base + N especialidad + Empates + [Usuarios si admin] + Info
(tab1, tab3, tab4, tab5) = _all_tabs[:4]
_n_sp        = len(_sp_labels)
_sp_tabs     = _all_tabs[4:4 + _n_sp]
if _IS_ADMIN:
    tab_override = _all_tabs[-3]   # Empates (antepenúltimo)
    tab_users    = _all_tabs[-2]   # Usuarios (penúltimo)
    tab6         = _all_tabs[-1]   # Info (último)
else:
    tab_override = _all_tabs[-2]
    tab_users    = None
    tab6         = _all_tabs[-1]


# ══ TAB 1 — GESTIÓN DE TIEMPOS ═════════════════════════════════════════════
with tab1:
    sec("Tiempo de Gestión por Guía  (FECHA SS → FECHA ESTADO)", "⏱️")

    if "_tiempo_gestion_horas" not in df.columns:
        st.warning(
            "⚠️ Sin datos de tiempo de gestión. "
            "Verifica que el Excel contenga **FECHA SS** y **FECHA ESTADO** "
            "en la hoja *Estado de Gestión*."
        )
        col_ss_chk  = col_map.get("fecha_ss")
        col_est_chk = col_map.get("fecha_estado")
        st.caption(
            f"FECHA SS detectada: `{col_ss_chk or 'No encontrada'}`  |  "
            f"FECHA ESTADO detectada: `{col_est_chk or 'No encontrada'}`"
        )
    else:
        h_all   = df["_tiempo_gestion_horas"]
        h_valid = h_all.dropna()
        h_valid = h_valid[h_valid >= 0]

        n_total = len(h_valid)
        prom_h  = float(h_valid.mean()) if n_total else None
        max_h   = float(h_valid.max())  if n_total else None
        # Mínimo solo de pedidos entregados
        _h_entregados = (
            df.loc[df["_entregado"] == True, "_tiempo_gestion_horas"].dropna()
            if "_entregado" in df.columns else h_valid
        )
        _h_entregados = _h_entregados[_h_entregados > 0]
        min_h = float(_h_entregados.min()) if not _h_entregados.empty else None
        pct_lt_c = round(len(h_valid[h_valid <  umbral_critico_h]) / n_total * 100, 1) if n_total else 0
        pct_gt_c = round(len(h_valid[h_valid >= umbral_critico_h]) / n_total * 100, 1) if n_total else 0
        lbl_uc   = format_horas(umbral_critico_h)

        g1, g2, g3, g4, g5 = st.columns(5)
        with g1: st.metric("📊 Con Registro",       f"{n_total:,}")
        with g2: st.metric("⬇️ Mín. Gestión",       format_horas(min_h) if min_h is not None else "—")
        with g3: st.metric("⬆️ Máximo",              format_horas(max_h) if max_h is not None else "—")
        with g4: st.metric(f"✅ < {lbl_uc}",         f"{pct_lt_c} %")
        with g5: st.metric(f"🔴 > {lbl_uc}",         f"{pct_gt_c} %")

        st.divider()

        # ── Tendencia de pedidos (mismo chart del Tab Resumen) ─────────────
        sec("Tendencia de Pedidos", "📈")
        _freq_g = st.radio(
            "", ["Diaria", "Semanal"], horizontal=True,
            key="r_freq_gestion", label_visibility="collapsed",
        )
        st.plotly_chart(
            chart_tendencia(df, col_map, "D" if _freq_g == "Diaria" else "W"),
            use_container_width=True, key="ch_tendencia_gestion",
        )

        st.divider()

        ch1, ch2 = st.columns([1, 1])
        with ch1:
            sec("Distribución del Tiempo de Gestión", "📊")
            st.plotly_chart(
                chart_distribucion_gestion(df, col_map,
                    umbral_alerta_h=umbral_alerta_h,
                    umbral_critico_h=umbral_critico_h),
                use_container_width=True, key="ch_dist_gestion",
            )
            # Donut de urgencia — rellena el espacio bajo el histograma
            if "_tiempo_gestion_horas" in df.columns:
                _hv = df["_tiempo_gestion_horas"].dropna()
                _hv = _hv[_hv >= 0]
                if not _hv.empty:
                    _lbl_a = format_horas(umbral_alerta_h)
                    _lbl_c = format_horas(umbral_critico_h)
                    _zonas = [
                        (f"< {_lbl_a}",
                         int((_hv < umbral_alerta_h).sum()), "#5DCFEF"),
                        (f"{_lbl_a} – {_lbl_c}",
                         int(((_hv >= umbral_alerta_h) & (_hv < umbral_critico_h)).sum()), "#00AEEF"),
                        (f"> {_lbl_c}",
                         int((_hv >= umbral_critico_h).sum()), "#005F8E"),
                    ]
                    _labels = [z[0] for z in _zonas]
                    _values = [z[1] for z in _zonas]
                    _colors = [z[2] for z in _zonas]
                    _fig_d = go.Figure(go.Pie(
                        labels=_labels, values=_values,
                        hole=0.52,
                        marker=dict(colors=_colors,
                                    line=dict(color="white", width=2)),
                        textinfo="label+percent",
                        textfont=dict(size=12),
                        hovertemplate="<b>%{label}</b><br>%{value} guías (%{percent})<extra></extra>",
                        sort=False,
                    ))
                    _fig_d.add_annotation(
                        text=f"<b>{len(_hv)}</b><br><span style='font-size:11px'>guías</span>",
                        x=0.5, y=0.5, xref="paper", yref="paper",
                        showarrow=False, font=dict(size=18, color="#1C2A1E"),
                    )
                    _fig_d.update_layout(
                        title=dict(text="Guías por Zona de Urgencia",
                                   font=dict(size=13, color="#1C2A1E"), x=0.02),
                        height=300,
                        paper_bgcolor="white", plot_bgcolor="white",
                        margin=dict(t=45, b=10, l=10, r=10),
                        legend=dict(orientation="h", y=-0.05, x=0.5,
                                    xanchor="center", font=dict(size=11)),
                        showlegend=True,
                    )
                    st.plotly_chart(_fig_d, use_container_width=True, key="ch_donut_urgencia")
        with ch2:
            sec("Envíos y Días de Gestión por Provincia Destino", "📦")
            st.plotly_chart(
                chart_envios_tiempo_por_provincia(df, col_map),
                use_container_width=True, key="ch_envios_prov",
            )

        st.divider()
        sec("Top 10 Guías Pendientes con Mayor Tiempo de Gestión", "🔴")
        st.caption("Excluye guías entregadas y devoluciones al shipper — solo gestión pendiente real.")
        # Excluir entregadas Y devoluciones al shipper (esas tienen su propia tabla abajo)
        # Sin .copy(): el filtrado booleano ya crea un frame nuevo y
        # build_gestion_table_df copia internamente.
        _df_top = df[df["_entregado"] == False] if "_entregado" in df.columns else df
        _col_est_top = col_map.get("estado")
        if _col_est_top and _col_est_top in _df_top.columns:
            _df_top = _df_top[
                ~_df_top[_col_est_top].astype(str).str.upper().str.contains(
                    "DEVOLUCION", na=False
                )
            ]
        top10_df = build_gestion_table_df(_df_top, col_map, ascending=False, max_rows=10)
        st.dataframe(
            top10_df.style.apply(
                lambda col: ["background-color:#FDEAEA;color:#922B21" if col.name == "Tiempo"
                             else "" for _ in col],
                axis=0,
            ),
            use_container_width=True,
            height=min(400, (len(top10_df) + 1) * 38 + 10),
        )

        st.divider()
        sec("Detalle por Guía — Guía | Pedido | Estado | Fecha SS | Fecha Estado | Tiempo Transcurrido", "📋")

        col_est_g = col_map.get("estado")
        estados_g = ["— Todos —"]
        if col_est_g and col_est_g in df.columns:
            estados_g += sorted(df[col_est_g].dropna().astype(str).unique().tolist())

        # ── Lookup: guías presentes en cada hoja de especialidad ───────────
        # Permite filtrar la tabla principal mostrando solo los pedidos
        # que pertenecen a una hoja específica (ENVIOS CENTRO DE DIST., etc.)
        _guias_por_hoja: dict[str, set] = {}
        for _sn_g, (_sraw_g, _, _) in specialty_dfs.items():
            _cg = sv.find_col(_sraw_g, "GUIA 1", "guia 1")
            if _cg and _cg in _sraw_g.columns:
                _gs = _sraw_g[_cg].dropna().astype(str).str.strip()
                _gs = set(_gs[~_gs.isin(["", "nan", "None"])].tolist())
                if _gs:
                    _guias_por_hoja[_sn_g] = _gs

        # ── Fila de filtros ────────────────────────────────────────────────
        fg0, fg1, fg2 = st.columns([2, 2, 2])

        # Mapa nombre_legible → clave_real (bulletproof: usa detect_type + heurísticas)
        _hoja_display_map: dict[str, str] = {}
        for _kk in _guias_por_hoja.keys():
            _kk_upper = str(_kk).upper()
            _raw_kk = specialty_dfs[_kk][0] if _kk in specialty_dfs else None

            # Detección por tipo (usa columnas del DataFrame)
            _stype_kk = sv.detect_type(_raw_kk, _kk) if _raw_kk is not None else "unknown"

            # Forzar nombre canónico con doble verificación
            if (_stype_kk == "telefonia"
                    or "TELEFON" in _kk_upper
                    or "PELIC" in _kk_upper
                    or "MOVIL" in _kk_upper
                    or "MÓVIL" in _kk_upper):
                _disp = "ENVÍOS TELEFONÍA MÓVIL"
            elif ("CENTRO" in _kk_upper
                  or "DISTRIBUC" in _kk_upper
                  or "UIO" in _kk_upper):
                _disp = "ENVÍOS CENTRO DE DISTRIBUCIÓN"
            elif ("PROVINCIA" in _kk_upper
                  or "PROVINCIAS" in _kk_upper
                  or _stype_kk == "logistica"):
                _disp = "ENVÍOS ENTRE PROVINCIAS"
            else:
                _disp = _kk_upper

            _hoja_display_map[_disp] = _kk

        _opciones_hoja = ["— Todos los pedidos —"] + list(_hoja_display_map.keys())

        # Limpieza agresiva de session_state — descarta cualquier valor obsoleto
        # de versiones anteriores del dropdown
        for _stale_key in ("sel_g_hoja", "sel_g_hoja_v2"):
            if _stale_key in st.session_state and st.session_state[_stale_key] not in _opciones_hoja:
                del st.session_state[_stale_key]

        with fg0:
            # Nueva clave de widget (v3) → fuerza a Streamlit a crear un widget limpio
            hoja_g = st.selectbox(
                "📂 Tipo de envío",
                _opciones_hoja,
                key="sel_g_hoja_v3",
                help="Filtra por los pedidos registrados en cada hoja de especialidad",
            )

        with fg1:
            estado_g = st.selectbox("🔖 Estado", estados_g, key="sel_g_estado")

        with fg2:
            orden_g = st.selectbox(
                "⏱️ Ordenar por tiempo",
                ["Mayor tiempo primero", "Menor tiempo primero"],
                key="sel_g_orden",
            )

        # ── Aplicar filtros ────────────────────────────────────────────────
        # IMPORTANTE: si hay búsqueda activa, partimos de df_full (data COMPLETA
        # sin overrides ni filtros del sidebar) para que la búsqueda SIEMPRE
        # encuentre la guía, incluso si fue empatada o anulada.
        # Los filtros del tab (hoja, estado) sí se respetan.
        _search_active = bool(search_guia and search_guia.strip())
        df_g = df_full.copy() if _search_active else df.copy()

        # 1) Filtro por hoja de especialidad
        if hoja_g != "— Todos los pedidos —":
            _real_hoja_key = _hoja_display_map.get(hoja_g)
            if _real_hoja_key and _real_hoja_key in _guias_por_hoja:
                _col_guia_g = col_map.get("guia")
                if _col_guia_g and _col_guia_g in df_g.columns:
                    _set_guias = _guias_por_hoja[_real_hoja_key]
                    df_g = df_g[
                        df_g[_col_guia_g].astype(str).str.strip().isin(_set_guias)
                    ]

        # 2) Filtro por estado
        if estado_g != "— Todos —" and col_est_g and col_est_g in df_g.columns:
            df_g = df_g[df_g[col_est_g].astype(str) == estado_g]

        asc_g = orden_g == "Menor tiempo primero"
        # entregados_last=True → guías entregadas van al final de la tabla,
        # las pendientes con mayor tiempo de gestión quedan arriba.
        tbl_g = build_gestion_table_df(df_g, col_map,
                                       search_guia=search_guia, ascending=asc_g,
                                       entregados_last=True)

        # Indicador de búsqueda activa (los filtros del sidebar se ignoran)
        if _search_active:
            st.info(
                f"🔍 Búsqueda activa: «**{search_guia.strip()}**» — "
                f"{len(tbl_g):,} resultado(s). "
                "Los filtros del sidebar (fecha, provincia, etc.) se ignoran "
                "durante la búsqueda."
            )
        # Indicador de hoja activa
        elif hoja_g != "— Todos los pedidos —":
            st.info(f"📂 Mostrando pedidos de **{hoja_g}** — {len(tbl_g):,} registros")
        else:
            st.caption(f"Mostrando **{len(tbl_g):,}** registros")

        st.dataframe(tbl_g, use_container_width=True, height=500)
        st.download_button(
            "⬇️ Exportar Gestión Excel",
            _to_xlsx(tbl_g),
            "tiempos_gestion.xlsx", XLSX_MIME,
            key="dl_gestion",
        )

        # ── Tabla dedicada: Devoluciones al Shipper ────────────────────────
        st.divider()
        sec("Devoluciones al Shipper", "↩️")
        _col_est_dev = col_map.get("estado")
        if _col_est_dev and _col_est_dev in df.columns:
            # Sin .copy() — el filtrado booleano ya crea frame nuevo
            _df_dev = df[
                df[_col_est_dev].astype(str).str.upper().str.contains(
                    "DEVOLUCION", na=False
                )
            ]
            tbl_dev = build_gestion_table_df(
                _df_dev, col_map, ascending=False, max_rows=2000
            )
            st.caption(f"🔄 **{len(tbl_dev):,}** guía(s) en devolución al shipper")
            if tbl_dev.empty:
                st.success("✅ No hay devoluciones al shipper actualmente.")
            else:
                st.dataframe(tbl_dev, use_container_width=True, height=400)
                st.download_button(
                    "⬇️ Exportar Devoluciones Excel",
                    _to_xlsx(tbl_dev),
                    "devoluciones_shipper.xlsx", XLSX_MIME,
                    key="dl_devoluciones",
                )
        else:
            st.info("No se detectó columna de Estado para filtrar devoluciones.")


# ══ TAB 3 — POR ESTADO ═════════════════════════════════════════════════════
with tab3:
    col_est = col_map.get("estado")
    if not col_est or col_est not in df.columns:
        st.warning("⚠️ No se detectó columna de Estado.")
    else:
        sec("Resumen General por Estado", "📊")
        st.plotly_chart(chart_resumen_por_estado(df, col_map),
                        use_container_width=True, key="ch_resumen_estado")
        st.divider()

        sec("Análisis Detallado por Estado", "🔍")
        estados = sorted(df[col_est].dropna().astype(str).unique().tolist())
        c_sel, _ = st.columns([2, 3])
        with c_sel:
            estado_sel = st.selectbox("Selecciona un estado",
                                      ["— Ver todos —"] + estados,
                                      key="sel_estado_tab")

        df_est = df if estado_sel == "— Ver todos —" \
                    else df[df[col_est].astype(str) == estado_sel].copy()

        ent_est  = int(df_est["_entregado"].sum()) if "_entregado" in df_est.columns else 0
        ci_c     = col_map.get("incidencia")
        inc_est  = int(df_est[ci_c].notna().sum()) if ci_c and ci_c in df_est.columns else 0
        if "_tiempo_gestion_horas" in df_est.columns:
            _hv_est = df_est["_tiempo_gestion_horas"].dropna()
            _hv_est = _hv_est[_hv_est >= 0]
            t_gest_est = format_horas(_hv_est.mean()) if not _hv_est.empty else "—"
        elif "_dias_total" in df_est.columns:
            _dv = df_est["_dias_total"].dropna()
            t_gest_est = f"{_dv.mean():.1f}d" if not _dv.empty else "—"
        else:
            t_gest_est = "—"

        e1, e2, e3, e4 = st.columns(4)
        with e1: st.metric("Pedidos en estado", len(df_est))
        with e2: st.metric("Entregados", ent_est)
        with e3: st.metric("Incidencias", inc_est)
        with e4: st.metric("T. Prom. Gestión", t_gest_est)

        col_dest2 = col_map.get("provincia_destino")
        if col_dest2 and col_dest2 in df_est.columns and not df_est.empty:
            c1, c2 = st.columns(2)
            with c1:
                sec("Distribución por Provincia Destino", "📍")
                pc = df_est[col_dest2].value_counts().reset_index()
                pc.columns = ["Provincia", "Pedidos"]
                fig_pc = px.bar(pc.head(15), x="Pedidos", y="Provincia",
                                orientation="h", color="Pedidos",
                                color_continuous_scale=["#C8E8F8", "#00AEEF", "#005F8E"],
                                text="Pedidos")
                fig_pc.update_traces(textposition="outside")
                fig_pc.update_layout(height=400, template="plotly_white",
                                     coloraxis_showscale=False,
                                     yaxis=dict(autorange="reversed"),
                                     margin=dict(t=20, b=20, l=10, r=20))
                st.plotly_chart(fig_pc, use_container_width=True, key="ch_est_prov")
            with c2:
                _tcol = ("_tiempo_gestion_horas" if "_tiempo_gestion_horas" in df_est.columns
                         else "_dias_total" if "_dias_total" in df_est.columns else None)
                if _tcol and col_dest2 and col_dest2 in df_est.columns and not df_est.empty:
                    _es_horas = _tcol == "_tiempo_gestion_horas"
                    sec("T. Prom. Gestión por Provincia Destino", "⏱️")
                    dp = (df_est.dropna(subset=[_tcol])
                          .groupby(col_dest2)[_tcol].mean()
                          .round(1).reset_index()
                          .sort_values(_tcol, ascending=False).head(15))
                    dp.columns = ["Provincia", "Valor"]
                    dp["Label"] = (dp["Valor"].apply(format_horas) if _es_horas
                                   else dp["Valor"].apply(lambda x: f"{x:.1f}d"))
                    fig_dp = px.bar(dp, x="Valor", y="Provincia", orientation="h",
                                    color="Valor",
                                    color_continuous_scale=["#ADE8F4", "#00AEEF", "#0077B6", "#005F8E", "#002D5C"],
                                    text="Label")
                    if _es_horas:
                        fig_dp.add_vline(
                            x=umbral_alerta_h, line_dash="longdashdot",
                            line_color="#E5A817",
                            annotation_text=f"⚡ {format_horas(umbral_alerta_h)}")
                        fig_dp.add_vline(
                            x=umbral_critico_h, line_dash="dash",
                            line_color="#C0392B",
                            annotation_text=f"🔴 {format_horas(umbral_critico_h)}")
                    else:
                        fig_dp.add_vline(
                            x=umbral_critico_h / 24, line_dash="dash",
                            line_color="#C0392B",
                            annotation_text=f"🔴 {format_horas(umbral_critico_h)}")
                    fig_dp.update_traces(textposition="outside")
                    fig_dp.update_layout(height=400, template="plotly_white",
                                         paper_bgcolor="#F2F6FB", plot_bgcolor="#F2F6FB",
                                         coloraxis_showscale=False,
                                         yaxis=dict(autorange="reversed"),
                                         margin=dict(t=20, b=20, l=10, r=20))
                    st.plotly_chart(fig_dp, use_container_width=True, key="ch_est_dias")

        st.divider()
        lbl = estado_sel if estado_sel != "— Ver todos —" else "todos los estados"
        sec(f"Pedidos — {lbl}", "📋")
        tbl_est = build_table_df(df_est, col_map, search_guia=search_guia)
        st.caption(f"{len(tbl_est):,} registros")
        st.dataframe(tbl_est, use_container_width=True, height=420)
        st.download_button(f"⬇️ Exportar Excel",
                           _to_xlsx(tbl_est),
                           f"estado_{lbl.replace(' ','_')}.xlsx", XLSX_MIME,
                           key="dl_estado_tab")


# ══ TAB 4 — MAPA ═══════════════════════════════════════════════════════════
with tab4:
    sec("Mapa de Operaciones — Ecuador", "🌎")
    metrica = st.radio("Métrica",
                       ["Pendientes de retirar", "Volumen de pedidos",
                        "Retrasos (días prom.)"],
                       horizontal=True, key="r_mapa")
    if metrica == "Pendientes de retirar":

        # ── Filtros específicos para rutas pendientes ──────────────────────
        _df_pend = df[~df["_entregado"]].copy() if "_entregado" in df.columns else df.copy()
        _col_est_m  = col_map.get("estado")
        _col_resp_m = col_map.get("responsable")

        with st.expander("🔧 Filtros de rutas pendientes", expanded=True):
            fm1, fm2, fm3, fm4 = st.columns([2, 2, 2, 2])

            with fm1:
                color_modo = st.radio(
                    "🎨 Colorear por",
                    ["Provincia Origen", "Urgencia (tiempo)"],
                    horizontal=False, key="r_color_modo",
                )
                color_by = "urgencia" if color_modo == "Urgencia (tiempo)" else "origen"

            with fm2:
                min_h_val = 0.0
                if "_tiempo_gestion_horas" in _df_pend.columns:
                    _max_h_fil = float(_df_pend["_tiempo_gestion_horas"].dropna().max() or 168)
                    min_h_val = st.slider(
                        "⏱️ Mostrar solo con más de X horas",
                        0.0, min(_max_h_fil, 168.0), 0.0, step=6.0,
                        key="sl_min_horas",
                        format="%.0fh",
                    )

            with fm3:
                estados_mapa = []
                if _col_est_m and _col_est_m in _df_pend.columns:
                    _opts_est = sorted(_df_pend[_col_est_m].dropna().astype(str).unique())
                    estados_mapa = st.multiselect(
                        "🔖 Estado actual",
                        _opts_est, default=[], key="ms_est_mapa",
                    )

            with fm4:
                gest_mapa = None
                if _col_resp_m and _col_resp_m in _df_pend.columns:
                    _opts_resp = ["— Todos —"] + sorted(
                        _df_pend[_col_resp_m].dropna().astype(str).unique()
                    )
                    _sel_resp = st.selectbox(
                        "👤 Gestionista", _opts_resp, key="sb_resp_mapa"
                    )
                    gest_mapa = None if _sel_resp == "— Todos —" else _sel_resp

            # Leyenda de urgencia
            if color_by == "urgencia":
                st.markdown(
                    "<div style='font-size:.78rem;margin-top:4px'>"
                    "<span style='color:#5DCFEF'>●</span> &lt;24h &nbsp;"
                    "<span style='color:#00AEEF'>●</span> 24–48h &nbsp;"
                    "<span style='color:#0090CC'>●</span> 48–72h &nbsp;"
                    "<span style='color:#005F8E'>●</span> &gt;72h"
                    "</div>", unsafe_allow_html=True,
                )

        st.plotly_chart(
            chart_mapa_rutas_pendientes(
                df, col_map,
                min_horas=min_h_val,
                color_by=color_by,
                estados_sel=estados_mapa if estados_mapa else None,
                gestionista_sel=gest_mapa,
            ),
            use_container_width=True, key="ch_mapa_rutas",
        )

        # ── Mini tabla resumen de rutas pendientes ─────────────────────────
        with st.expander("📋 Detalle de rutas pendientes"):
            _col_orig_m = col_map.get("provincia_origen")
            _col_dest_m = col_map.get("provincia_destino")
            if _col_orig_m and _col_dest_m and \
               _col_orig_m in _df_pend.columns and _col_dest_m in _df_pend.columns:

                _agg = (
                    _df_pend.dropna(subset=[_col_orig_m, _col_dest_m])
                    .groupby([_col_orig_m, _col_dest_m])
                    .agg(
                        Pedidos=(_col_orig_m, "count"),
                        **( {"T. Prom. Gestión": ("_tiempo_gestion_horas", lambda x: format_horas(x.mean()))}
                            if "_tiempo_gestion_horas" in _df_pend.columns else {} )
                    )
                    .reset_index()
                    .rename(columns={_col_orig_m: "Origen", _col_dest_m: "Destino"})
                    .sort_values("Pedidos", ascending=False)
                )
                st.dataframe(_agg, use_container_width=True,
                             hide_index=True,
                             height=min(420, (len(_agg) + 1) * 36 + 10))
                st.download_button(
                    "⬇️ Exportar rutas pendientes",
                    _to_xlsx(_agg), "rutas_pendientes.xlsx", XLSX_MIME,
                    key="dl_rutas_pend",
                )
    else:
        mkey = {"Retrasos (días prom.)": "retrasos",
                "Volumen de pedidos": "volumen"}[metrica]
        st.plotly_chart(chart_mapa_ecuador(df, col_map, metric=mkey),
                        use_container_width=True, key="ch_mapa")


# ══ TAB 5 — TABLA DETALLE ══════════════════════════════════════════════════
with tab5:
    sec("Detalle Completo de Pedidos", "📋")
    # Si hay búsqueda activa, usar df_full (data completa sin overrides) para
    # encontrar la guía aunque esté empatada/anulada o fuera de los filtros.
    _search_active_t5 = bool(search_guia and search_guia.strip())
    _df_for_tbl = df_full if _search_active_t5 else df
    tbl = build_table_df(_df_for_tbl, col_map, search_guia=search_guia)
    if _search_active_t5:
        st.info(
            f"🔍 Búsqueda activa: «**{search_guia.strip()}**» — "
            f"{len(tbl):,} resultado(s). "
            "Los filtros del sidebar se ignoran durante la búsqueda."
        )
    else:
        st.caption(f"Mostrando **{len(tbl):,}** registros")
    st.dataframe(tbl, use_container_width=True, height=520)
    st.download_button("⬇️ Exportar Excel",
                       _to_xlsx(tbl),
                       "detalle_pedidos.xlsx", XLSX_MIME,
                       key="dl_detalle_tab")


# ══ TAB EMPATES Y ANULACIONES ══════════════════════════════════════════════
# NOTA: se envuelve en una función para evitar st.stop() — antes se usaba
# st.stop() que halta TODA la app, lo que impedía que los tabs siguientes
# (Usuarios, Info, especialidad) se renderizaran para usuarios sin permisos.
def _render_overrides_content():
    """Renderiza el contenido del tab Empates. Solo se llama si el usuario
    tiene rol admin u operador."""
    sec("Empates y Anulaciones de Guías", "🔄")

    st.markdown(
        "<div style='background:#EAF5EE;border-left:4px solid #1A7A3C;"
        "padding:10px 14px;border-radius:6px;margin-bottom:14px;font-size:.88rem'>"
        "<b>💡 ¿Cuándo usar cada uno?</b><br>"
        "• <b>🔗 Empate:</b> cuando una guía no se entregó y se generó "
        "una NUEVA guía para reemplazarla (la nueva ya está en CNT).<br>"
        "• <b>🚫 Anulación:</b> cuando una guía se cancela y NO se reemplaza "
        "(duplicada, cliente canceló, etc.)."
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Cargar histórico y estado actual ──────────────────────────────────
    _hist     = ov.get_history()
    _empates_df, _anuladas_df = ov.load_overrides()
    _emp_act  = ov.get_active_empates(_empates_df)
    _anul_act = ov.get_active_anuladas(_anuladas_df)

    # Resumen rápido
    _r1, _r2, _r3 = st.columns(3)
    with _r1: st.metric("🔗 Empates activos", len(_emp_act))
    with _r2: st.metric("🚫 Anulaciones activas", len(_anul_act))
    with _r3: st.metric("📜 Operaciones totales (histórico)", len(_hist))

    st.divider()

    # ════════════════════════════════════════════════════════════════════
    # FORMULARIO 1 — EMPATAR GUÍAS
    # ════════════════════════════════════════════════════════════════════
    sec("Empatar Guías  (guía vieja → guía nueva)", "🔗")

    with st.form("form_empate", clear_on_submit=True):
        e1, e2, e3 = st.columns([2, 2, 2])
        with e1:
            _emp_old = st.text_input(
                "Guía original (no se entregó)",
                placeholder="Ej: WYB1234567890",
                key="emp_old",
            )
        with e2:
            _emp_new = st.text_input(
                "Guía nueva (reemplazo)",
                placeholder="Ej: WYB9876543210",
                key="emp_new",
            )
        with e3:
            _emp_motivo = st.selectbox(
                "Motivo",
                ov.MOTIVOS_EMPATE,
                key="emp_motivo",
            )
        e4, e5 = st.columns([3, 2])
        with e4:
            _emp_notas = st.text_input(
                "Notas (opcional)",
                placeholder="Detalles adicionales…",
                key="emp_notas",
            )
        with e5:
            _emp_user = st.text_input(
                "Usuario", value="operador", key="emp_user",
            )
        _emp_submit = st.form_submit_button(
            "🔗 Crear empate", use_container_width=True, type="primary",
        )

        if _emp_submit:
            ok, msg = ov.add_empate(
                _emp_old, _emp_new, _emp_motivo,
                usuario=_emp_user, notas=_emp_notas,
            )
            if ok:
                st.success(msg)
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(msg)

    st.divider()

    # ════════════════════════════════════════════════════════════════════
    # FORMULARIO 2 — ANULAR GUÍA
    # ════════════════════════════════════════════════════════════════════
    sec("Anular Guía  (excluir de reportes)", "🚫")

    with st.form("form_anul", clear_on_submit=True):
        a1, a2 = st.columns([2, 3])
        with a1:
            _anul_guia = st.text_input(
                "Guía a anular",
                placeholder="Ej: WYB1234567890",
                key="anul_guia",
            )
        with a2:
            _anul_motivo = st.selectbox(
                "Motivo",
                ov.MOTIVOS_ANULACION,
                key="anul_motivo",
            )
        a3, a4 = st.columns([3, 2])
        with a3:
            _anul_notas = st.text_input(
                "Notas (opcional)",
                placeholder="Detalles adicionales…",
                key="anul_notas",
            )
        with a4:
            _anul_user = st.text_input(
                "Usuario", value="operador", key="anul_user",
            )
        _anul_submit = st.form_submit_button(
            "🚫 Anular guía", use_container_width=True, type="primary",
        )

        if _anul_submit:
            ok, msg = ov.add_anulacion(
                _anul_guia, _anul_motivo,
                usuario=_anul_user, notas=_anul_notas,
            )
            if ok:
                st.success(msg)
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(msg)

    st.divider()

    # ════════════════════════════════════════════════════════════════════
    # HISTÓRICO + DESHACER
    # ════════════════════════════════════════════════════════════════════
    sec("Histórico de Operaciones", "📜")

    if _hist.empty:
        st.info("📭 Aún no hay empates ni anulaciones registradas.")
    else:
        h_c1, h_c2 = st.columns([2, 3])
        with h_c1:
            _flt_tipo = st.selectbox(
                "Filtrar por tipo",
                ["Todos", "🔗 Empate", "🚫 Anulación"],
                key="hist_tipo",
            )
        with h_c2:
            _flt_estado = st.radio(
                "Estado",
                ["Todos", "Solo ACTIVA", "Solo REVERTIDA"],
                horizontal=True,
                key="hist_estado",
            )

        # Aplicar filtros
        _hist_f = _hist.copy()
        if _flt_tipo != "Todos":
            _hist_f = _hist_f[_hist_f["Tipo"] == _flt_tipo]
        if _flt_estado == "Solo ACTIVA":
            _hist_f = _hist_f[_hist_f["Estado"].str.upper() == "ACTIVA"]
        elif _flt_estado == "Solo REVERTIDA":
            _hist_f = _hist_f[_hist_f["Estado"].str.upper() == "REVERTIDA"]

        st.caption(f"Mostrando **{len(_hist_f):,}** operaciones")

        # Tabla visible (sin columnas internas _tipo / _idx)
        _hist_view = _hist_f.drop(columns=["_tipo", "_idx"]).copy()
        _hist_view.index = range(1, len(_hist_view) + 1)
        st.dataframe(_hist_view, use_container_width=True, height=320)

        # Exportar
        st.download_button(
            "⬇️ Exportar histórico Excel",
            _to_xlsx(_hist_view),
            "historico_overrides.xlsx", XLSX_MIME,
            key="dl_hist_ov",
        )

        # Sección de DESHACER (solo operaciones ACTIVA)
        st.markdown("---")
        st.markdown("**↩️ Deshacer una operación**")

        _hist_activas = _hist_f[_hist_f["Estado"].str.upper() == "ACTIVA"]
        if _hist_activas.empty:
            st.caption("No hay operaciones activas que se puedan revertir con los filtros actuales.")
        else:
            _opts_undo = [
                f"{r['Tipo']}  |  {r['Guía']}  {r['Detalle']}  |  {r['Fecha']}"
                for _, r in _hist_activas.iterrows()
            ]
            _sel_undo = st.selectbox(
                "Selecciona la operación a revertir",
                ["—"] + _opts_undo,
                key="sel_undo",
            )
            if _sel_undo != "—":
                _idx_sel = _opts_undo.index(_sel_undo)
                _row = _hist_activas.iloc[_idx_sel]
                if st.button(
                    f"🗑️ Revertir esta operación", type="secondary",
                    key="btn_revert",
                ):
                    ok, msg = ov.revert(_row["_tipo"], int(_row["_idx"]))
                    if ok:
                        st.success(msg)
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(msg)


# Render del tab Empates: solo invoca la función si el usuario tiene permisos
with tab_override:
    if _CAN_EDIT_OVERRIDES:
        _render_overrides_content()
    else:
        st.warning(
            "🔒 No tienes permisos para crear empates o anulaciones.\n\n"
            f"Tu rol actual: **{USER['role']}**. "
            "Esta sección requiere rol **admin** u **operador**."
        )


# ══ TAB USUARIOS — Solo admin ══════════════════════════════════════════════
if tab_users is not None and _IS_ADMIN:
    with tab_users:
        sec("Gestión de Usuarios", "👥")

        from modules import user_store as _us_status
        _auto_mode = _us_status.is_github_configured()
        if _auto_mode:
            st.success(
                "🤖 **Modo automático activo** — Los usuarios se crean, "
                "modifican y eliminan directamente. Cada cambio se commitea "
                "a GitHub y Streamlit Cloud redespliega la app (~1 min)."
            )
        else:
            st.info(
                "📝 **Modo manual** — Configura un GitHub Personal Access "
                "Token en Secrets para activar el modo automático. Mientras "
                "tanto, los cambios deben pegarse manualmente en Secrets."
            )

        # ── Lista de usuarios actuales ─────────────────────────────────
        sec("Usuarios actuales", "📋")
        try:
            from modules import user_store as _us_list
            _current_users = _us_list.get_all_users()
            _users_rows = []
            for _u, _data in _current_users.items():
                _role = _data.get("role", "viewer")
                _badge = {"admin": "👑", "operador": "🔧", "viewer": "👁️"}.get(_role, "👤")
                _users_rows.append({
                    "Usuario":  _u,
                    "Nombre":   _data.get("name", ""),
                    "Email":    _data.get("email", "—") or "—",
                    "Rol":      f"{_badge} {_role}",
                })
            _users_df = pd.DataFrame(_users_rows)
            _users_df.index = range(1, len(_users_df) + 1)
            st.dataframe(_users_df, use_container_width=True, hide_index=False)
        except Exception as _e:
            st.warning(f"No se pudieron listar usuarios: {_e}")

        st.divider()

        # ── Formulario: Agregar / Actualizar usuario ───────────────────
        sec("Agregar o actualizar usuario", "➕")

        with st.form("form_new_user", clear_on_submit=False):
            _u1, _u2 = st.columns(2)
            with _u1:
                _new_username = st.text_input(
                    "Nombre de usuario *",
                    placeholder="ej: juan_perez",
                    help="Solo letras, números y guiones bajos. Sin espacios.",
                    key="nu_username",
                )
                _new_name = st.text_input(
                    "Nombre completo *",
                    placeholder="ej: Juan Pérez",
                    key="nu_name",
                )
                _new_email = st.text_input(
                    "Email (opcional)",
                    placeholder="juan@empresa.com",
                    key="nu_email",
                )
            with _u2:
                _new_password = st.text_input(
                    "Contraseña *",
                    type="password",
                    placeholder="Mínimo 6 caracteres",
                    key="nu_password",
                )
                _new_password2 = st.text_input(
                    "Confirmar contraseña *",
                    type="password",
                    key="nu_password2",
                )
                _new_role = st.selectbox(
                    "Rol *",
                    ["admin", "operador", "viewer"],
                    index=2,
                    help=(
                        "• admin: todo permitido\n"
                        "• operador: ver + crear empates/anulaciones\n"
                        "• viewer: solo consulta"
                    ),
                    key="nu_role",
                )

            _submit = st.form_submit_button(
                "🔑 Generar credenciales", use_container_width=True, type="primary",
            )

        if _submit:
            # Validaciones
            _errors = []
            if not _new_username or not _new_username.strip():
                _errors.append("Nombre de usuario es obligatorio")
            elif not _new_username.replace("_", "").isalnum():
                _errors.append("Usuario solo puede tener letras, números y guion bajo")
            if not _new_name or not _new_name.strip():
                _errors.append("Nombre completo es obligatorio")
            if not _new_password:
                _errors.append("Contraseña es obligatoria")
            elif len(_new_password) < 6:
                _errors.append("Contraseña debe tener al menos 6 caracteres")
            elif _new_password != _new_password2:
                _errors.append("Las contraseñas no coinciden")

            if _errors:
                for _err in _errors:
                    st.error(f"❌ {_err}")
            else:
                try:
                    import bcrypt
                    from modules import user_store

                    _hashed = bcrypt.hashpw(
                        _new_password.encode(), bcrypt.gensalt()
                    ).decode()
                    _username_clean = _new_username.strip().lower()

                    # ── Auto-commit via GitHub API ─────────────────────
                    _ok, _msg = user_store.add_or_update_user(
                        username=_username_clean,
                        name=_new_name.strip(),
                        email=_new_email.strip(),
                        role=_new_role,
                        hashed_password=_hashed,
                    )

                    if _ok:
                        st.success(_msg)
                        st.info(
                            "⏱️ Espera ~1 minuto y luego refresca esta página. "
                            "El nuevo usuario ya podrá ingresar."
                        )
                    else:
                        # GitHub no configurado — mostrar TOML para fallback manual
                        st.warning(_msg)
                        st.markdown("---")
                        st.markdown(
                            "**📋 Modo manual:** copia este bloque y pégalo en "
                            "Streamlit Cloud → Settings → Secrets:"
                        )
                        _toml = (
                            f'[auth.credentials.usernames.{_username_clean}]\n'
                            f'name     = "{_new_name.strip()}"\n'
                            f'email    = "{_new_email.strip()}"\n'
                            f'role     = "{_new_role}"\n'
                            f'password = "{_hashed}"\n'
                        )
                        st.code(_toml, language="toml")

                except ImportError:
                    st.error("❌ Falta el paquete `bcrypt`")
                except Exception as _e:
                    st.error(f"Error generando credenciales: {_e}")

        st.divider()

        # ── Eliminar usuario ───────────────────────────────────────────
        sec("Eliminar usuario", "🗑️")

        try:
            _existing_users = list(
                st.secrets["auth"]["credentials"]["usernames"].keys()
            )
        except Exception:
            _existing_users = []

        # Lista directa de usuarios desde user_store (refleja el estado real)
        from modules import user_store as _us
        _existing_users = list(_us.get_all_users().keys())

        if not _existing_users:
            st.info("No hay usuarios registrados.")
        else:
            _to_delete = st.selectbox(
                "Selecciona el usuario a eliminar",
                ["—"] + _existing_users,
                key="del_user_sel",
            )
            if _to_delete and _to_delete != "—":
                if _to_delete == USER["username"]:
                    st.error(
                        "❌ No puedes eliminarte a ti mismo. Pide a otro admin "
                        "que lo haga, o cambia el rol primero."
                    )
                else:
                    _confirm = st.checkbox(
                        f"Sí, eliminar definitivamente al usuario **{_to_delete}**",
                        key="del_user_confirm",
                    )
                    if _confirm and st.button(
                        "🗑️ ELIMINAR USUARIO", type="primary", key="btn_del_user",
                    ):
                        _ok_d, _msg_d = _us.remove_user(_to_delete)
                        if _ok_d:
                            st.success(_msg_d)
                            st.info("⏱️ Espera ~1 minuto y refresca la página.")
                        else:
                            st.warning(_msg_d)

        st.divider()

        # ── Cambiar contraseña de un usuario existente ─────────────────
        sec("Resetear contraseña", "🔑")

        with st.form("form_reset_pwd", clear_on_submit=False):
            _r1, _r2 = st.columns(2)
            with _r1:
                _reset_user = st.selectbox(
                    "Usuario",
                    _existing_users or ["—"],
                    key="rst_user",
                )
            with _r2:
                _reset_pwd = st.text_input(
                    "Nueva contraseña",
                    type="password",
                    placeholder="Mín 6 caracteres",
                    key="rst_pwd",
                )
            _reset_submit = st.form_submit_button(
                "🔑 Generar nueva contraseña", use_container_width=True,
            )

        if _reset_submit:
            if _reset_user == "—" or not _reset_user:
                st.error("❌ Selecciona un usuario.")
            elif not _reset_pwd or len(_reset_pwd) < 6:
                st.error("❌ Contraseña debe tener al menos 6 caracteres")
            else:
                try:
                    import bcrypt
                    from modules import user_store as _us2
                    _new_hash = bcrypt.hashpw(
                        _reset_pwd.encode(), bcrypt.gensalt()
                    ).decode()

                    # Mantener los demás datos del usuario
                    _existing_data = _us2.get_all_users().get(_reset_user, {})
                    _ok_r, _msg_r = _us2.add_or_update_user(
                        username=_reset_user,
                        name=_existing_data.get("name", _reset_user),
                        email=_existing_data.get("email", ""),
                        role=_existing_data.get("role", "viewer"),
                        hashed_password=_new_hash,
                    )
                    if _ok_r:
                        st.success(_msg_r)
                        st.info("⏱️ Espera ~1 minuto y refresca la página.")
                    else:
                        st.warning(_msg_r)
                        st.markdown(
                            "**📋 Modo manual:** reemplaza la línea `password` del "
                            f"bloque `[auth.credentials.usernames.{_reset_user}]` en Secrets:"
                        )
                        st.code(f'password = "{_new_hash}"', language="toml")
                except Exception as _e:
                    st.error(f"Error: {_e}")


# ══ TAB 6 — INFORMACIÓN ════════════════════════════════════════════════════
with tab6:
    c1, c2 = st.columns(2)
    with c1:
        sec("Sobre el Dashboard", "ℹ️")
        st.markdown("""
**Dashboard Logístico — BUSINESSPOINT S.A.**
Transporte de Carga Liviana | Jefatura Logística

**Tecnología:** Python · Streamlit · Plotly · Pandas · OpenPyXL

**Fuente de datos:**
- Hoja **Estado de Gestión** → dashboard general (todos los pedidos)
- Hojas de especialidad → tabs individuales (se cargan automáticamente si existen)

**Panel principal (Tab 1):** Tiempo entre FECHA SS y FECHA ESTADO

**Logos:** Guardar en `assets/logo_empresa.png` y `assets/logo_cnt.png`
        """)

    with c2:
        sec("Columnas Detectadas en el Excel", "🔎")
        col_info = []
        for key in ["guia", "pedido", "estado", "incidencia", "provincia_origen",
                    "provincia_destino", "fecha_ss", "fecha_estado",
                    "fecha_creacion", "fecha_entrega",
                    "responsable", "cliente", "transportista", "detalle_estado"]:
            real = col_map.get(key)
            col_info.append({
                "Campo lógico": key,
                "Columna Excel": real if real else "⚠️ No detectada",
                "Estado": "✅" if real else "❌",
            })
        st.dataframe(pd.DataFrame(col_info), use_container_width=True,
                     hide_index=True, height=440)

    col_est_i = col_map.get("estado")
    if col_est_i and col_est_i in df.columns:
        st.divider()
        sec("Estados detectados en los datos", "🔖")
        ec = df[col_est_i].value_counts().reset_index()
        ec.columns = ["Estado", "Cantidad"]
        ec["% del total"] = (ec["Cantidad"] / len(df) * 100).round(1)
        st.dataframe(ec, use_container_width=True, hide_index=True)

    # Actualizar descripción de fuente de datos según hojas disponibles
    st.divider()
    sec("Hojas de datos activas", "📂")
    _sheet_info = [{"Hoja": "Estado de Gestión (principal)", "Registros": f"{len(df):,}", "Rol": "Dashboard general"}]
    for _sn, (_sraw, _sclean, _) in specialty_dfs.items():
        _sheet_info.append({"Hoja": _sn, "Registros": f"{len(_sraw):,}", "Rol": "Hoja especialidad"})
    st.dataframe(pd.DataFrame(_sheet_info), use_container_width=True, hide_index=True)


# ══ TABS DE ESPECIALIDAD (dinámicos) ════════════════════════════════════════
for _sp_tab, _sp_sheet_name in zip(_sp_tabs, _sp_names):
    _sp_raw, _sp_clean, _sp_col_map = specialty_dfs[_sp_sheet_name]
    _sp_type = sv.detect_type(_sp_raw, _sp_sheet_name)
    _sp_fname_base = (
        _sp_sheet_name.lower()
        .replace(" ", "_").replace("ó","o").replace("í","i").replace("é","e")
    )

    with _sp_tab:
        sec(_sp_display_name(_sp_sheet_name), _sp_icon(_sp_sheet_name))

        # ════════════════════════════════════════════════════════════════════
        # TIPO A — Logística (ENVIOS CENTRO DE DIST. / ENTRE PROVINCIAS)
        # ════════════════════════════════════════════════════════════════════
        if _sp_type == "logistica":
            _lk = sv.kpis_logistica(_sp_raw)
            lk1, lk2, lk3, lk4, lk5, lk6 = st.columns(6)
            with lk1: st.metric("📦 Total Envíos",        _lk["total"])
            with lk2: st.metric("📋 Pedidos únicos",      _lk["pedidos_unicos"])
            with lk3: st.metric("🏷️ Guías asignadas",     _lk["guias"])
            with lk4: st.metric("🗺️ Provincias destino",  _lk["destinos"])
            with lk5: st.metric("📍 Provincias origen",   _lk["origenes"])
            with lk6: st.metric("📅 Último envío",        _lk["fecha_max"])

            st.divider()

            # ── Gráficos ──────────────────────────────────────────────────
            _la, _lb = st.columns(2)
            with _la:
                sec("Envíos por Provincia Destino", "📍")
                st.plotly_chart(
                    sv.chart_log_por_provincia(
                        _sp_raw, "PROVINCIA DESTINO", "Envíos por Provincia Destino"),
                    use_container_width=True, key=f"sp_dest_{_sp_sheet_name}",
                )
            with _lb:
                sec("Envíos por Provincia Origen", "📌")
                st.plotly_chart(
                    sv.chart_log_por_provincia(
                        _sp_raw, "PROVINCIA ORIGEN", "Envíos por Provincia Origen"),
                    use_container_width=True, key=f"sp_orig_{_sp_sheet_name}",
                )

            _lc, _ld = st.columns([3, 2])
            with _lc:
                sec("Tendencia de Envíos por Fecha", "📈")
                st.plotly_chart(
                    sv.chart_log_tendencia(_sp_raw),
                    use_container_width=True, key=f"sp_tend_{_sp_sheet_name}",
                )
            with _ld:
                sec("Estado de Asignación de Guías", "🏷️")
                st.plotly_chart(
                    sv.chart_log_guias_donut(_sp_raw),
                    use_container_width=True, key=f"sp_guias_{_sp_sheet_name}",
                )

            st.divider()

            # ── Filtros + Tabla ───────────────────────────────────────────
            sec("Detalle de Registros", "📋")
            _col_orig_f = sv.find_col(_sp_raw, "PROVINCIA ORIGEN")
            _col_dest_f = sv.find_col(_sp_raw, "PROVINCIA DESTINO")
            _col_g1_f   = sv.find_col(_sp_raw, "GUIA 1", "guia 1")

            _df_log = _sp_raw.copy()
            _lf1, _lf2, _lf3 = st.columns([2, 2, 2])
            with _lf1:
                if _col_orig_f and _col_orig_f in _sp_raw.columns:
                    _opts_lo = ["— Todos —"] + sorted(
                        _sp_raw[_col_orig_f].dropna().astype(str).unique().tolist()
                    )
                    _sel_lo = st.selectbox("📍 Provincia Origen", _opts_lo,
                                           key=f"sp_flt_orig_{_sp_sheet_name}")
                    if _sel_lo != "— Todos —":
                        _df_log = _df_log[_df_log[_col_orig_f].astype(str) == _sel_lo]
            with _lf2:
                if _col_dest_f and _col_dest_f in _sp_raw.columns:
                    _opts_ld = ["— Todos —"] + sorted(
                        _sp_raw[_col_dest_f].dropna().astype(str).unique().tolist()
                    )
                    _sel_ld = st.selectbox("📍 Provincia Destino", _opts_ld,
                                           key=f"sp_flt_dest_{_sp_sheet_name}")
                    if _sel_ld != "— Todos —":
                        _df_log = _df_log[_df_log[_col_dest_f].astype(str) == _sel_ld]
            with _lf3:
                if _col_g1_f and _col_g1_f in _sp_raw.columns:
                    _guia_filter = st.radio(
                        "🏷️ Guía", ["Todos", "Con guía", "Sin guía"],
                        horizontal=True, key=f"sp_flt_guia_{_sp_sheet_name}",
                    )
                    if _guia_filter == "Con guía":
                        _df_log = _df_log[_df_log[_col_g1_f].notna()]
                    elif _guia_filter == "Sin guía":
                        _df_log = _df_log[_df_log[_col_g1_f].isna()]

            # ── Enriquecer GUIA 1 con estado real desde "Estado de Gestión" ─
            _col_guia_main   = col_map.get("guia")
            _col_estado_main = col_map.get("estado")
            _col_g1_sp       = sv.find_col(_df_log, "GUIA 1", "guia 1")

            if (_col_guia_main and _col_estado_main and _col_g1_sp
                    and _col_guia_main in df_raw.columns
                    and _col_estado_main in df_raw.columns
                    and _col_g1_sp in _df_log.columns):
                # Tabla de lookup: guía → estado (usa df_raw completo, sin filtros)
                _lookup_estado = (
                    df_raw[[_col_guia_main, _col_estado_main]]
                    .dropna(subset=[_col_guia_main])
                    .assign(**{
                        _col_guia_main: lambda d: d[_col_guia_main].astype(str).str.strip()
                    })
                    .drop_duplicates(subset=[_col_guia_main])
                    .set_index(_col_guia_main)[_col_estado_main]
                    .to_dict()
                )
                _guias_sp     = _df_log[_col_g1_sp].astype(str).str.strip()
                _no_guia_mask = _df_log[_col_g1_sp].isna() | _guias_sp.isin(["nan", "None", ""])
                _df_log = _df_log.copy()
                _df_log["Estado Guía 1"] = _guias_sp.map(_lookup_estado)
                _df_log.loc[_no_guia_mask, "Estado Guía 1"] = "⏳ Sin Guía"
                _df_log["Estado Guía 1"] = _df_log["Estado Guía 1"].fillna("⚠️ No encontrada")

            st.caption(f"Mostrando **{len(_df_log):,}** registros")
            _tbl_log = sv.build_display_table(_df_log)
            st.dataframe(_tbl_log, use_container_width=True, height=480)
            st.download_button(
                f"⬇️ Exportar {_sp_sheet_name}",
                _to_xlsx(_tbl_log),
                f"{_sp_fname_base}.xlsx", XLSX_MIME,
                key=f"dl_sp_{_sp_sheet_name}",
            )

        # ════════════════════════════════════════════════════════════════════
        # TIPO B — Telefonía Móvil (ENVIOS TELEFONIA MOVIL)
        # ════════════════════════════════════════════════════════════════════
        elif _sp_type == "telefonia":
            # ── Enriquecer _sp_raw con _pendiente_real (cross-reference) ─────
            # Si la GUIA 1 de una línea está marcada como ENTREGADA en
            # "Estado de Gestión", consideramos sus unidades como entregadas
            # (Por entregar real = 0). Caso contrario, usamos el valor original.
            _col_g1_sp_tel    = sv.find_col(_sp_raw, "GUIA 1", "guia 1")
            _col_pend_sp_tel  = sv.find_col(
                _sp_raw, "Por entregar (cantidad)",
                "por entregar (cantidad)", "por entregar",
            )
            _col_guia_main_t  = col_map.get("guia")

            if (_col_g1_sp_tel and _col_pend_sp_tel and _col_guia_main_t
                    and _col_g1_sp_tel in _sp_raw.columns
                    and _col_pend_sp_tel in _sp_raw.columns
                    and _col_guia_main_t in df_raw.columns
                    and "_entregado" in df_raw.columns):

                _delivered_guias = set(
                    df_raw.loc[df_raw["_entregado"] == True, _col_guia_main_t]
                          .astype(str).str.strip().dropna().unique()
                )
                _sp_raw = _sp_raw.copy()
                _g1_str_tel    = _sp_raw[_col_g1_sp_tel].astype(str).str.strip()
                _is_delivered  = _g1_str_tel.isin(_delivered_guias)
                _orig_pend_tel = pd.to_numeric(
                    _sp_raw[_col_pend_sp_tel], errors="coerce"
                ).fillna(0)
                # Si está entregado → pendiente real = 0
                _sp_raw["_pendiente_real"] = _orig_pend_tel.where(~_is_delivered, other=0)

            _tk = sv.kpis_telefonia(_sp_raw)
            tk1, tk2, tk3, tk4, tk5, tk6 = st.columns(6)
            with tk1: st.metric("📋 Total Líneas",        _tk["total"])
            with tk2: st.metric("⏳ Líneas Pendientes",   _tk["lineas_pendientes"])
            with tk3: st.metric("📦 Unidades Pedidas",    f"{_tk['cant_total']:,}")
            with tk4: st.metric("🕐 Unidades Pendientes", f"{_tk['cant_pendiente']:,}")
            with tk5: st.metric("🏷️ Guías asignadas",     _tk["guias"])
            with tk6: st.metric("🏭 Centros",             _tk["centros"])

            st.divider()

            # ── Gráficos ──────────────────────────────────────────────────
            _ta, _tb = st.columns(2)
            with _ta:
                sec("Top Materiales — Unidades Pedidas", "📦")
                st.plotly_chart(
                    sv.chart_tel_top_materiales(_sp_raw),
                    use_container_width=True, key=f"sp_mat_{_sp_sheet_name}",
                )
            with _tb:
                sec("Kilos Pendientes por Centro", "⚖️")
                st.plotly_chart(
                    sv.chart_tel_pendientes_por_centro(_sp_raw),
                    use_container_width=True, key=f"sp_pend_{_sp_sheet_name}",
                )

            _tc, _td = st.columns([3, 2])
            with _tc:
                sec("Evolución de Unidades por Fecha de Documento", "📈")
                st.plotly_chart(
                    sv.chart_tel_tendencia(_sp_raw),
                    use_container_width=True, key=f"sp_tel_tend_{_sp_sheet_name}",
                )
            with _td:
                sec("Estado de Entrega — Unidades", "🎯")
                st.plotly_chart(
                    sv.chart_tel_pedido_vs_pendiente(_sp_raw),
                    use_container_width=True, key=f"sp_tel_donut_{_sp_sheet_name}",
                )

            st.divider()

            # ── Filtros + Tabla ───────────────────────────────────────────
            sec("Detalle de Registros", "📋")
            _col_centro = sv.find_col(_sp_raw, "Nombre 1", "nombre 1", "Centro")
            # Material = código del producto (40006050, POP-036, etc.)
            _col_mat    = sv.find_col(_sp_raw, "Material", "material")
            _col_pend   = sv.find_col(_sp_raw, "Por entregar (cantidad)", "por entregar")

            _df_tel = _sp_raw.copy()
            _tf1, _tf2, _tf3 = st.columns([2, 3, 2])
            with _tf1:
                if _col_centro and _col_centro in _sp_raw.columns:
                    _opts_tc = ["— Todos —"] + sorted(
                        _sp_raw[_col_centro].dropna().astype(str).unique().tolist()
                    )
                    _sel_tc = st.selectbox("🏭 Centro / Destino", _opts_tc,
                                           key=f"sp_flt_centro_{_sp_sheet_name}")
                    if _sel_tc != "— Todos —":
                        _df_tel = _df_tel[_df_tel[_col_centro].astype(str) == _sel_tc]
            with _tf2:
                if _col_mat and _col_mat in _sp_raw.columns:
                    _opts_tm = ["— Todos —"] + sorted(
                        _sp_raw[_col_mat].dropna().astype(str).unique().tolist()
                    )
                    _sel_tm = st.selectbox("🔢 Material (código)", _opts_tm,
                                           key=f"sp_flt_matcode_{_sp_sheet_name}")
                    if _sel_tm != "— Todos —":
                        _df_tel = _df_tel[_df_tel[_col_mat].astype(str) == _sel_tm]
            with _tf3:
                if _col_pend and _col_pend in _sp_raw.columns:
                    _only_pend = st.checkbox("Solo pendientes de entrega",
                                             key=f"sp_chk_pend_{_sp_sheet_name}")
                    if _only_pend:
                        _df_tel = _df_tel[
                            pd.to_numeric(_df_tel[_col_pend], errors="coerce").fillna(0) > 0
                        ]

            # ── Enriquecer con datos desde "Estado de Gestión" ─────────────
            # Vía GUIA 1 traemos: Estado, Recibido por, Fecha entrega, Hora entrega.
            _col_guia_main_t   = col_map.get("guia")
            _col_estado_main_t = col_map.get("estado")
            _col_g1_tel        = sv.find_col(_df_tel, "GUIA 1", "guia 1")

            # Columnas adicionales desde Estado de Gestión
            def _find_main(name_options):
                for _n in name_options:
                    if _n in df_raw.columns:
                        return _n
                return None
            _col_recibido = _find_main(["RECIBIDO POR", "Recibido por", "recibido por"])
            _col_fest_main = col_map.get("fecha_estado")  # FECHA ESTADO
            _col_hora_ent  = _find_main(["HORA ENTREGA", "Hora entrega", "hora entrega"])

            if (_col_guia_main_t and _col_estado_main_t and _col_g1_tel
                    and _col_guia_main_t in df_raw.columns
                    and _col_estado_main_t in df_raw.columns
                    and _col_g1_tel in _df_tel.columns):

                # Base del lookup: deduplicado por guía
                _base = (
                    df_raw.dropna(subset=[_col_guia_main_t])
                    .assign(**{
                        _col_guia_main_t: lambda d: d[_col_guia_main_t].astype(str).str.strip()
                    })
                    .drop_duplicates(subset=[_col_guia_main_t])
                    .set_index(_col_guia_main_t)
                )

                _lookup_estado_t = _base[_col_estado_main_t].to_dict()
                _lookup_recibido = (
                    _base[_col_recibido].to_dict() if _col_recibido else {}
                )
                _lookup_fest = (
                    _base[_col_fest_main].to_dict() if _col_fest_main else {}
                )
                _lookup_hora = (
                    _base[_col_hora_ent].to_dict() if _col_hora_ent else {}
                )

                _guias_tel    = _df_tel[_col_g1_tel].astype(str).str.strip()
                _no_guia_mask = _df_tel[_col_g1_tel].isna() | _guias_tel.isin(["nan", "None", ""])
                _df_tel = _df_tel.copy()

                # Columna existente: Estado Guía 1
                _df_tel["Estado Guía 1"] = _guias_tel.map(_lookup_estado_t)
                _df_tel.loc[_no_guia_mask, "Estado Guía 1"] = "⏳ Sin Guía"
                _df_tel["Estado Guía 1"] = _df_tel["Estado Guía 1"].fillna("⚠️ No encontrada")

                # NUEVO: Nombre del responsable que recibe
                if _lookup_recibido:
                    _df_tel["Recibido por"] = (
                        _guias_tel.map(_lookup_recibido)
                        .where(~_no_guia_mask, other="")
                        .fillna("")
                    )

                # NUEVO: Fecha y Hora de recepción (sólo si Estado contiene "entregad"
                # — para no poner una fecha que no es realmente la de entrega).
                _is_entregado = (
                    _df_tel["Estado Guía 1"].astype(str).str.upper().str.contains("ENTREGAD", na=False)
                )

                if _lookup_fest:
                    _fest_series = _guias_tel.map(_lookup_fest)
                    _fest_dt = pd.to_datetime(_fest_series, errors="coerce")
                    _df_tel["Fecha de recepción"] = (
                        _fest_dt.dt.strftime("%d/%m/%Y").where(_is_entregado, other="")
                    ).fillna("")
                    # Si existe HORA ENTREGA usa esa, sino extrae hora de FECHA ESTADO
                    if _lookup_hora:
                        _hora_series = _guias_tel.map(_lookup_hora).astype(str)
                        _df_tel["Hora de recepción"] = _hora_series.where(
                            _is_entregado, other=""
                        ).replace({"nan": "", "None": "", "NaT": ""}).fillna("")
                    else:
                        _df_tel["Hora de recepción"] = (
                            _fest_dt.dt.strftime("%H:%M").where(_is_entregado, other="")
                        ).fillna("")

            st.caption(f"Mostrando **{len(_df_tel):,}** registros")
            _tbl_tel = sv.build_display_table(_df_tel)
            st.dataframe(_tbl_tel, use_container_width=True, height=480)
            st.download_button(
                f"⬇️ Exportar {_sp_sheet_name}",
                _to_xlsx(_tbl_tel),
                f"{_sp_fname_base}.xlsx", XLSX_MIME,
                key=f"dl_sp_{_sp_sheet_name}",
            )

        # ════════════════════════════════════════════════════════════════════
        # FALLBACK — Hoja desconocida (renderer genérico)
        # ════════════════════════════════════════════════════════════════════
        else:
            _sp_kpis = calculate_kpis(_sp_clean, _sp_col_map,
                                      umbral_alerta_h=umbral_alerta_h,
                                      umbral_critico_h=umbral_critico_h)
            _gk1, _gk2, _gk3, _gk4 = st.columns(4)
            with _gk1: st.metric("📦 Total",      _sp_kpis["total"])
            with _gk2: st.metric("✅ Entregados", _sp_kpis["entregados"],
                                  f"{_sp_kpis['pct_entregados']} %")
            with _gk3: st.metric("🕐 Pendientes", _sp_kpis["pendientes"])
            with _gk4: st.metric("⚠️ Incidencias", _sp_kpis["incidencias"])
            st.divider()
            _gc1, _gc2 = st.columns(2)
            with _gc1:
                sec("Distribución por Estado", "📊")
                st.plotly_chart(
                    chart_estado_distribucion(_sp_clean, _sp_col_map),
                    use_container_width=True, key=f"sp_estado_{_sp_sheet_name}",
                )
            with _gc2:
                sec("Envíos por Provincia Destino", "📍")
                st.plotly_chart(
                    chart_entregas_por_provincia(_sp_clean, _sp_col_map),
                    use_container_width=True, key=f"sp_prov_{_sp_sheet_name}",
                )
            st.divider()
            sec("Detalle de Registros", "📋")
            _sp_tbl = build_table_df(_sp_clean, _sp_col_map, search_guia=search_guia)
            st.caption(f"Mostrando **{len(_sp_tbl):,}** registros de *{_sp_sheet_name}*")
            st.dataframe(_sp_tbl, use_container_width=True, height=480)
            st.download_button(
                f"⬇️ Exportar {_sp_sheet_name}",
                _to_xlsx(_sp_tbl),
                f"{_sp_fname_base}.xlsx", XLSX_MIME,
                key=f"dl_sp_{_sp_sheet_name}",
            )


# ── Advertencias del sistema (movidas al final para no saturar arriba) ────
if warn_list:
    st.divider()
    with st.expander("ℹ️ Información del sistema y advertencias",
                     expanded=False):
        for w in warn_list:
            st.warning(f"⚠️ {w}")


# ── Footer ─────────────────────────────────────────────────────────────────
st.markdown(
    "<div style='text-align:center;padding:1rem 0 .5rem;"
    "color:#8FA8C8;font-size:.75rem'>"
    "Dashboard Logístico — BUSINESSPOINT S.A. | Python · Streamlit · Plotly"
    "</div>",
    unsafe_allow_html=True,
)

