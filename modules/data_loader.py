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

@st.cache_data(ttl=30, show_spinner=False)
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

    return df_main, col_map, specialty, warnings_list, errors_list


# ---------------------------------------------------------------------------
# Helper público
# ---------------------------------------------------------------------------

def get_data_with_refresh(folder: Optional[Path] = None):
    """
    Encuentra el Excel más reciente y carga todas las hojas.
    Aplica overrides (empates/anulaciones) FUERA del caché para que los
    cambios surtan efecto inmediatamente sin necesidad de limpiar caché.

    Retorna:
        df_main, col_map, specialty_dfs, warn_list, err_list
    """
    latest = find_latest_excel(folder)
    if latest is None:
        return None, None, {}, [], [
            f"No se encontró ningún archivo Excel en: {folder or ROOT_DIR}"
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
