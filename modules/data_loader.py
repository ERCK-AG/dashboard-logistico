"""
data_loader.py — Carga y caché de datos desde Excel.

Arquitectura multi-hoja:
  • Hoja principal : "Estado de Gestion"  → dashboard general
  • Hojas especialidad → tabs individuales (auto-detectadas)
      - "ENVIOS CENTRO DE DISTRIBUCION"  (tipo: logistica)
      - "ENVIOS ENTRE PROVINCIAS"        (tipo: logistica)
      - "ENVIOS TELEFONIA MOVIL"         (tipo: telefonia)
"""

import os
import base64
import tempfile
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from modules.cleaner import clean_dataframe, find_column
from modules import overrides as ov

# ---------------------------------------------------------------------------
# Constantes configurables
# ---------------------------------------------------------------------------

# Hoja principal — informe general de todos los pedidos
SHEET_PRINCIPAL     = "Estado de Gestión"
SHEET_PRINCIPAL_ALT = ["Estado de Gestion", "Estado Gestion", "Gestion", "Estado"]

# Hojas de especialidad conocidas — la búsqueda es case-insensitive.
# Agrega nuevas hojas aquí a medida que las crees en el Excel.
SPECIALTY_SHEETS = [
    # ── Nombres actuales en el Excel ─────────────────────────────────────────
    "ENVIOS CENTRO DE DISTRIBUCION",
    "ENVIOS ENTRE PROVINCIAS",
    "ENVIOS TELEFONIA MOVIL",
    # ── Variantes con tildes / alias históricos ───────────────────────────────
    "Envíos entre provincias",
    "Envios entre provincias",
    "Envíos telefonía Móvil",
    "Envios telefonia Movil",
    "Envíos desde el Centro de Distribución UIO",
    "Envios desde el Centro de Distribucion UIO",
]

EXCEL_EXTENSIONS = ("*.xlsx", "*.xlsm", "*.xls")

# Carpeta raíz del proyecto (donde está app.py)
ROOT_DIR = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Detección del archivo más reciente
# ---------------------------------------------------------------------------

def find_latest_excel(folder: Optional[Path] = None) -> Optional[Path]:
    """
    Encuentra el archivo Excel más reciente en `folder`.
    Excluye archivos internos del proyecto (overrides.xlsx, etc.) que no son
    fuentes de datos sino almacenes de configuración del dashboard.
    """
    # Archivos a ignorar (no son fuentes de datos)
    EXCLUDED_NAMES = {"overrides.xlsx"}

    folder = folder or ROOT_DIR
    candidates = []
    for ext in EXCEL_EXTENSIONS:
        candidates.extend(folder.glob(ext))
    # Filtrar archivos excluidos y temporales de Office (~$*.xlsx)
    candidates = [
        p for p in candidates
        if p.name.lower() not in EXCLUDED_NAMES
        and not p.name.startswith("~$")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def get_file_mtime(filepath: Path) -> float:
    try:
        return filepath.stat().st_mtime
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Descarga desde URL (OneDrive / SharePoint / cualquier link directo)
# ---------------------------------------------------------------------------

def _onedrive_personal_to_direct(share_url: str) -> str:
    """
    Convierte un share link de OneDrive PERSONAL a URL de descarga directa
    usando la API pública /shares/u! con base64.
    NOTA: Para SharePoint/OneDrive Business no funciona ("User migrated") —
    en ese caso se usa el método &download=1.
    """
    b64 = base64.urlsafe_b64encode(share_url.encode("utf-8")).decode("utf-8")
    b64 = b64.rstrip("=")
    return f"https://api.onedrive.com/v1.0/shares/u!{b64}/root/content"


def _sharepoint_to_direct(share_url: str) -> str:
    """
    Para OneDrive for Business / SharePoint:
    simplemente agregar `&download=1` (o `?download=1` si no hay query string)
    al share link público convierte el link en una descarga directa.
    """
    if "?" in share_url:
        return share_url + "&download=1"
    return share_url + "?download=1"


def _to_direct_download_url(share_url: str) -> str:
    """
    Normaliza un share link a una URL de descarga directa.
    Soporta OneDrive personal, OneDrive Business (SharePoint), y URLs directas.
    """
    if not share_url:
        return ""
    s = share_url.strip()
    sl = s.lower()
    # Si ya parece una URL de descarga directa, úsala tal cual
    if "api.onedrive.com" in sl or "download=1" in sl:
        return s
    # SharePoint / OneDrive for Business → método &download=1
    if "sharepoint.com" in sl:
        return _sharepoint_to_direct(s)
    # OneDrive personal → método base64
    if "onedrive.live.com" in sl or "1drv.ms" in sl:
        return _onedrive_personal_to_direct(s)
    # En otros casos: asumir que ya es una URL directa
    return s


@st.cache_data(ttl=60, show_spinner="📥 Descargando Excel desde OneDrive…")
def download_excel_from_url(share_url: str) -> Optional[str]:
    """
    Descarga un Excel desde una URL pública a un archivo temporal.
    Retorna la ruta local del archivo descargado, o None en caso de error.
    El TTL del caché es 30 segundos — coincide con load_all_sheets.
    """
    if not share_url:
        return None
    try:
        import requests
    except ImportError:
        return None

    direct_url = _to_direct_download_url(share_url)
    try:
        resp = requests.get(direct_url, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        # Guardar en archivo temporal
        tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        tmp.write(resp.content)
        tmp.close()
        return tmp.name
    except Exception as e:
        st.warning(f"⚠️ No se pudo descargar el Excel desde OneDrive: {e}")
        return None


def _get_excel_url_from_secrets() -> Optional[str]:
    """Lee la URL del Excel desde st.secrets si está configurada."""
    try:
        url = st.secrets["onedrive"]["excel_url"]
        return url.strip() if url and url.strip() else None
    except (KeyError, FileNotFoundError):
        return None


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _find_sheet(xl: pd.ExcelFile, primary: str, alternates: list[str]) -> Optional[str]:
    """Busca hoja por nombre exacto o alternativo (case-insensitive)."""
    sheets_lower = {s.lower(): s for s in xl.sheet_names}
    if primary.lower() in sheets_lower:
        return sheets_lower[primary.lower()]
    for alt in alternates:
        if alt.lower() in sheets_lower:
            return sheets_lower[alt.lower()]
    return None


def _load_sheet(xl: pd.ExcelFile, sheet_name: str) -> pd.DataFrame:
    """
    Carga una hoja, elimina filas vacías y normaliza encabezados.
    Solo elimina columnas vacías SIN nombre ("Unnamed: ..."); las columnas
    con nombre se preservan aunque estén vacías (caso GUIA 1/2/3 que pueden
    ir llenándose progresivamente).
    """
    df = xl.parse(sheet_name)
    df.dropna(how="all", inplace=True)
    # Eliminar solo columnas vacías SIN nombre (preserva columnas estructurales)
    _empty_unnamed = [
        c for c in df.columns
        if df[c].isna().all() and str(c).startswith("Unnamed")
    ]
    if _empty_unnamed:
        df.drop(columns=_empty_unnamed, inplace=True)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _open_excel(filepath: Path, warnings_list: list) -> Optional[pd.ExcelFile]:
    """Abre el Excel con manejo de archivo bloqueado (abierto en Excel)."""
    try:
        return pd.ExcelFile(filepath, engine="openpyxl")
    except PermissionError:
        import shutil, tempfile
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
            tmp.close()
            shutil.copy2(filepath, tmp.name)
            xl = pd.ExcelFile(tmp.name, engine="openpyxl")
            os.unlink(tmp.name)
            warnings_list.append("El archivo está abierto en Excel. Se leyó una copia temporal.")
            return xl
        except Exception as e:
            return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Función principal con caché
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60, show_spinner=False)
def load_all_sheets(filepath_str: str, file_mtime: float) -> tuple[
    Optional[pd.DataFrame],   # df principal (Estado de Gestión)
    Optional[dict],           # col_map del principal
    dict,                     # {nombre_hoja: (df_limpio, col_map)} hojas especialidad
    list[str],                # advertencias
    list[str],                # errores críticos
]:
    """
    Carga la hoja principal y todas las hojas de especialidad encontradas.

    Retorna:
        df_main      — DataFrame principal (Estado de Gestión) limpio
        col_map      — Mapa de columnas lógicas → reales del principal
        specialty    — Dict {nombre_real_hoja: (df_limpio, col_map)}
        warnings     — Advertencias no críticas
        errors       — Errores críticos
    """
    filepath = Path(filepath_str)
    warnings_list: list[str] = []
    errors_list:   list[str] = []
    specialty:     dict      = {}

    # ── Abrir archivo ────────────────────────────────────────────────────────
    xl = _open_excel(filepath, warnings_list)
    if xl is None:
        errors_list.append("No se pudo abrir el archivo Excel.")
        return None, None, specialty, warnings_list, errors_list

    # ── Hoja principal ───────────────────────────────────────────────────────
    sheet_p = _find_sheet(xl, SHEET_PRINCIPAL, SHEET_PRINCIPAL_ALT)
    if sheet_p is None:
        errors_list.append(
            f"No se encontró la hoja principal '{SHEET_PRINCIPAL}'. "
            f"Hojas disponibles: {xl.sheet_names}"
        )
        return None, None, specialty, warnings_list, errors_list

    df_main_raw = _load_sheet(xl, sheet_p)
    if df_main_raw.empty:
        errors_list.append(f"La hoja '{SHEET_PRINCIPAL}' está vacía.")
        return None, None, specialty, warnings_list, errors_list

    df_main, col_map = clean_dataframe(df_main_raw)

    # Advertencias de columnas críticas faltantes
    for key in ["guia", "estado", "provincia_destino"]:
        if col_map.get(key) is None:
            warnings_list.append(
                f"No se detectó columna para '{key}' en '{SHEET_PRINCIPAL}'. "
                "Algunos KPIs o gráficos pueden no estar disponibles."
            )

    # ── Hojas de especialidad ─────────────────────────────────────────────────
    # Cada hoja de especialidad se guarda como (df_raw, df_clean, col_map).
    # df_raw  = DataFrame sin transformar (para renderers que conocen su estructura)
    # df_clean = DataFrame limpiado por clean_dataframe (para renderers genéricos)
    # col_map  = mapa de columnas lógicas detectadas
    already_loaded = {sheet_p.lower()}

    for sp_name in SPECIALTY_SHEETS:
        real_name = _find_sheet(xl, sp_name, [])
        if real_name is None or real_name.lower() in already_loaded:
            continue
        already_loaded.add(real_name.lower())
        df_sp_raw = _load_sheet(xl, real_name)
        if df_sp_raw.empty:
            warnings_list.append(f"La hoja '{real_name}' está vacía, se omite.")
            continue
        df_sp_clean, cm_sp = clean_dataframe(df_sp_raw.copy())
        # Guardamos (raw, clean, col_map) para que cada renderer use lo que necesite
        specialty[real_name] = (df_sp_raw, df_sp_clean, cm_sp)

    if specialty:
        names = ", ".join(f"'{k}'" for k in specialty)
        warnings_list.append(f"Hojas de especialidad cargadas: {names}")

    # ── Enriquecimiento (N° Pedido + Agencia) — dentro del caché ──────────────
    # Antes corría en cada rerun de app.py con iterrows() (lento). Ahora se
    # calcula una sola vez por ventana de caché, vectorizado con zip().
    df_main = _build_enrichment(df_main, col_map, specialty)

    return df_main, col_map, specialty, warnings_list, errors_list


# ---------------------------------------------------------------------------
# Enriquecimiento: N° Pedido + Agencia por lookup con hojas de especialidad
# ---------------------------------------------------------------------------

def _build_enrichment(df_main, col_map, specialty):
    """
    Agrega columnas _n_pedido y _agencia a df_main cruzando GUIA 1/2/3 con
    las hojas de especialidad. Vectorizado con zip() (no iterrows).
    """
    if df_main is None or df_main.empty or not col_map:
        return df_main
    col_guia = col_map.get("guia")
    if not col_guia or col_guia not in df_main.columns:
        return df_main
    if not specialty:
        return df_main

    # Reutilizamos find_col de specialty_views (lazy import, evita ciclos)
    from modules.specialty_views import find_col as _find_col

    pedido_lookup:  dict[str, str] = {}
    agencia_lookup: dict[str, str] = {}

    for _sn, (_sraw, _, _) in specialty.items():
        col_ped = _find_col(_sraw, "PEDIDO", "pedido", "N° Pedido",
                            "Documento compras", "documento compras")
        col_ag = _find_col(_sraw, "AGENCIA DESTINO", "agencia destino",
                          "Nombre 1", "nombre 1", "Centro", "centro")
        for gname in ("GUIA 1", "GUIA 2", "GUIA 3"):
            col_g = _find_col(_sraw, gname, gname.lower())
            if not col_g or col_g not in _sraw.columns:
                continue
            gvals = _sraw[col_g].astype(str).str.strip().tolist()
            n = len(gvals)
            pvals = (_sraw[col_ped].tolist()
                     if col_ped and col_ped in _sraw.columns else [None] * n)
            avals = (_sraw[col_ag].tolist()
                     if col_ag and col_ag in _sraw.columns else [None] * n)
            # zip sobre listas — ~50x más rápido que iterrows
            for g, p, a in zip(gvals, pvals, avals):
                if not g or g in ("nan", "None", ""):
                    continue
                if g not in pedido_lookup and p is not None and pd.notna(p):
                    ps = str(p).strip()
                    if ps not in ("", "nan"):
                        if ps.endswith(".0"):
                            ps = ps[:-2]
                        pedido_lookup[g] = ps
                if g not in agencia_lookup and a is not None and pd.notna(a):
                    a_str = str(a).strip()
                    if a_str not in ("", "nan"):
                        agencia_lookup[g] = a_str

    guia_norm = df_main[col_guia].astype(str).str.strip()
    df_main = df_main.copy()
    df_main["_n_pedido"] = guia_norm.map(pedido_lookup).fillna("NA")
    df_main["_agencia"]  = guia_norm.map(agencia_lookup).fillna("—")
    return df_main


# ---------------------------------------------------------------------------
# Helper público
# ---------------------------------------------------------------------------

def get_data_with_refresh(folder: Optional[Path] = None):
    """
    Carga el Excel:
      1. Si hay URL configurada en st.secrets["onedrive"]["excel_url"] → descarga
      2. Si no, busca el Excel más reciente en `folder` local

    Aplica overrides (empates/anulaciones) FUERA del caché para que los
    cambios surtan efecto inmediatamente sin necesidad de limpiar caché.

    Retorna:
        df_main, col_map, specialty_dfs, warn_list, err_list
    """
    excel_url = _get_excel_url_from_secrets()
    latest: Optional[Path] = None

    if excel_url:
        # Modo cloud: descargar desde OneDrive
        downloaded = download_excel_from_url(excel_url)
        if downloaded is None:
            return None, None, {}, [], [
                "No se pudo descargar el Excel desde OneDrive. "
                "Verifica que el link sea válido y de tipo 'Cualquiera con el enlace'."
            ]
        latest = Path(downloaded)
    else:
        # Modo local: buscar archivo en la carpeta
        latest = find_latest_excel(folder)
        if latest is None:
            return None, None, {}, [], [
                f"No se encontró ningún archivo Excel en: {folder or ROOT_DIR}\n\n"
                "💡 Si estás en Streamlit Cloud, configura la URL del Excel "
                "en Secrets (sección [onedrive], clave `excel_url`)."
            ]

    mtime = get_file_mtime(latest)
    df_main, col_map, specialty, warn_list, err_list = load_all_sheets(str(latest), mtime)

    # ── Aplicar overrides (empates / anulaciones) ────────────────────────────
    # Se aplica fuera del caché para que las modificaciones del usuario en
    # overrides.xlsx surtan efecto inmediato sin tener que refrescar el caché.
    if df_main is not None and not df_main.empty and col_map:
        col_guia = col_map.get("guia")
        if col_guia and col_guia in df_main.columns:
            df_main_filtered, _ov_info = ov.apply_overrides(df_main, col_guia)
            df_main = df_main_filtered
            if _ov_info["anuladas_aplicadas"] > 0:
                warn_list.append(
                    f"🚫 {_ov_info['anuladas_aplicadas']} guía(s) anulada(s) "
                    "fueron excluidas de los reportes."
                )
            if _ov_info["empates_aplicados"] > 0:
                warn_list.append(
                    f"🔗 {_ov_info['empates_aplicados']} guía(s) empatada(s) "
                    "fueron reemplazadas por sus guías nuevas."
                )

    return df_main, col_map, specialty, warn_list, err_list
