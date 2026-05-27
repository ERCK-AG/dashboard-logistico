"""
overrides.py — Gestión de empates y anulaciones de guías.

Persiste todas las operaciones en `overrides.xlsx` (junto a app.py) con dos hojas:

  • EMPATES   — Guía Original → Guía Nueva (cuando se generó una guía
                de reemplazo porque la original nunca se entregó).
                La guía original deja de aparecer en reportes.

  • ANULADAS  — Guías excluidas completamente del flujo (canceladas,
                duplicadas, datos incorrectos, etc.).

Las operaciones REVERTIDAS se mantienen en el archivo (Estado="REVERTIDA")
para tener un histórico de auditoría completo.

Las funciones de modificación (add_*, revert_*) escriben directamente al
archivo. Las funciones de lectura (load_*, get_*) se usan en cada rerun.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

OVERRIDES_FILE = Path(__file__).parent.parent / "overrides.xlsx"

EMPATES_COLS = [
    "Guía Original", "Guía Nueva",
    "Fecha Empate", "Motivo", "Usuario", "Notas", "Estado",
]
ANULADAS_COLS = [
    "Guía Anulada",
    "Fecha Anulación", "Motivo", "Usuario", "Notas", "Estado",
]

MOTIVOS_EMPATE = [
    "Nunca retirado del emisor",
    "Falló 1ra y 2da visita",
    "Dirección incorrecta",
    "Cliente cambió dirección",
    "Daño en transporte",
    "Otro",
]
MOTIVOS_ANULACION = [
    "Cliente canceló",
    "Duplicada",
    "Datos incorrectos",
    "Error de registro",
    "Otro",
]


# ---------------------------------------------------------------------------
# Persistencia (lectura / escritura del archivo Excel)
# ---------------------------------------------------------------------------

def _ensure_file_exists() -> None:
    """
    Asegura que overrides.xlsx existe localmente.
    Prioridad:
      1. Si ya existe local → no hace nada
      2. Intenta descargar desde GitHub (si PAT está configurado)
      3. Si no, crea uno vacío
    """
    if OVERRIDES_FILE.exists():
        return

    # Intentar descargar desde GitHub
    try:
        from modules import user_store
        if user_store.is_github_configured():
            content_bytes = user_store.github_download_binary("overrides.xlsx")
            if content_bytes:
                OVERRIDES_FILE.write_bytes(content_bytes)
                return
    except Exception:
        pass

    # Crear archivo vacío
    with pd.ExcelWriter(OVERRIDES_FILE, engine="openpyxl") as writer:
        pd.DataFrame(columns=EMPATES_COLS).to_excel(
            writer, sheet_name="EMPATES", index=False
        )
        pd.DataFrame(columns=ANULADAS_COLS).to_excel(
            writer, sheet_name="ANULADAS", index=False
        )


def _commit_to_github(commit_msg: str) -> tuple[bool, str]:
    """Commitea overrides.xlsx a GitHub. Si no hay PAT, retorna (False, mensaje)."""
    try:
        from modules import user_store
        if not user_store.is_github_configured():
            return False, "Sin PAT — los empates solo se guardan localmente y se perderán en el próximo redeploy."
        if not OVERRIDES_FILE.exists():
            return False, "No existe el archivo local."
        content_bytes = OVERRIDES_FILE.read_bytes()
        return user_store.github_commit_binary(
            "overrides.xlsx", content_bytes, commit_msg
        )
    except Exception as e:
        return False, f"Error: {e}"


def load_overrides() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Carga las dos hojas. Retorna (df_empates, df_anuladas)."""
    _ensure_file_exists()
    try:
        empates = pd.read_excel(OVERRIDES_FILE, sheet_name="EMPATES", dtype=str)
        anuladas = pd.read_excel(OVERRIDES_FILE, sheet_name="ANULADAS", dtype=str)
    except Exception:
        empates = pd.DataFrame(columns=EMPATES_COLS)
        anuladas = pd.DataFrame(columns=ANULADAS_COLS)

    # Asegurar todas las columnas esperadas
    for c in EMPATES_COLS:
        if c not in empates.columns:
            empates[c] = ""
    for c in ANULADAS_COLS:
        if c not in anuladas.columns:
            anuladas[c] = ""

    # Limpiar NaN
    empates = empates.fillna("")
    anuladas = anuladas.fillna("")

    return empates, anuladas


def _save_overrides(empates: pd.DataFrame, anuladas: pd.DataFrame,
                    commit_msg: Optional[str] = None) -> tuple[bool, str]:
    """
    Escribe ambas hojas al archivo local.
    Si commit_msg está dado y GitHub está configurado, también commitea.
    Retorna (github_ok, github_msg) — útil para mostrar feedback al usuario.
    """
    with pd.ExcelWriter(OVERRIDES_FILE, engine="openpyxl") as writer:
        empates[EMPATES_COLS].to_excel(writer, sheet_name="EMPATES", index=False)
        anuladas[ANULADAS_COLS].to_excel(writer, sheet_name="ANULADAS", index=False)

    if commit_msg:
        return _commit_to_github(commit_msg)
    return True, "Guardado local"


# ---------------------------------------------------------------------------
# Helpers de filtrado de overrides activos
# ---------------------------------------------------------------------------

def get_active_empates(empates: pd.DataFrame) -> dict[str, str]:
    """Retorna dict { guia_original: guia_nueva } solo para empates ACTIVA."""
    if empates.empty:
        return {}
    mask = empates["Estado"].astype(str).str.upper().ne("REVERTIDA")
    activos = empates[mask]
    return {
        str(r["Guía Original"]).strip(): str(r["Guía Nueva"]).strip()
        for _, r in activos.iterrows()
        if str(r["Guía Original"]).strip() and str(r["Guía Nueva"]).strip()
    }


def get_active_anuladas(anuladas: pd.DataFrame) -> set[str]:
    """Retorna set de guías anuladas activas."""
    if anuladas.empty:
        return set()
    mask = anuladas["Estado"].astype(str).str.upper().ne("REVERTIDA")
    activas = anuladas[mask]
    return {
        str(g).strip()
        for g in activas["Guía Anulada"]
        if str(g).strip()
    }


def resolve_chain(empates_dict: dict[str, str], guia: str) -> str:
    """Sigue la cadena A→B→C y retorna el destino final."""
    visited: set[str] = set()
    current = guia
    while current in empates_dict and current not in visited:
        visited.add(current)
        current = empates_dict[current]
    return current


# ---------------------------------------------------------------------------
# Aplicación de overrides al DataFrame principal
# ---------------------------------------------------------------------------

def apply_overrides(
    df: pd.DataFrame,
    col_guia: Optional[str],
) -> tuple[pd.DataFrame, dict]:
    """
    Aplica empates y anulaciones a un DataFrame.

    Retorna (df_filtrado, info) donde info tiene:
        - 'anuladas_aplicadas': int
        - 'empates_aplicados':  int
        - 'guias_anuladas':     list[str]
        - 'guias_empatadas':    list[str]
    """
    info = {
        "anuladas_aplicadas": 0,
        "empates_aplicados": 0,
        "guias_anuladas": [],
        "guias_empatadas": [],
    }

    if df is None or df.empty or not col_guia or col_guia not in df.columns:
        return df, info

    empates_df, anuladas_df = load_overrides()
    empates_dict = get_active_empates(empates_df)
    anuladas_set = get_active_anuladas(anuladas_df)

    guias_norm = df[col_guia].astype(str).str.strip()

    # 1) Anulaciones — quitar filas con guía anulada
    mask_no_anuladas = ~guias_norm.isin(anuladas_set)
    info["anuladas_aplicadas"] = int((~mask_no_anuladas).sum())
    info["guias_anuladas"] = sorted(
        set(guias_norm[~mask_no_anuladas].tolist())
    )
    df_out = df[mask_no_anuladas].copy()

    # 2) Empates — quitar guías originales (las nuevas siguen en df desde CNT)
    guias_originales = set(empates_dict.keys())
    guias_norm_out = df_out[col_guia].astype(str).str.strip()
    mask_no_originales = ~guias_norm_out.isin(guias_originales)
    info["empates_aplicados"] = int((~mask_no_originales).sum())
    info["guias_empatadas"] = sorted(
        set(guias_norm_out[~mask_no_originales].tolist())
    )
    df_out = df_out[mask_no_originales].copy()

    return df_out, info


# ---------------------------------------------------------------------------
# Operaciones CRUD
# ---------------------------------------------------------------------------

def add_empate(
    guia_old: str, guia_new: str, motivo: str,
    usuario: str = "operador", notas: str = "",
) -> tuple[bool, str]:
    """Agrega un empate. Retorna (success, mensaje)."""
    guia_old = str(guia_old).strip()
    guia_new = str(guia_new).strip()
    motivo   = str(motivo).strip()
    usuario  = str(usuario).strip() or "operador"
    notas    = str(notas).strip()

    if not guia_old or not guia_new:
        return False, "❌ Ambas guías son obligatorias."
    if guia_old == guia_new:
        return False, "❌ La guía original y la nueva no pueden ser iguales."
    if not motivo:
        return False, "❌ Selecciona un motivo."

    empates_df, anuladas_df = load_overrides()

    # ¿La guía original ya tiene un empate activo?
    existing = empates_df[
        (empates_df["Guía Original"].astype(str).str.strip() == guia_old)
        & (empates_df["Estado"].astype(str).str.upper().ne("REVERTIDA"))
    ]
    if not existing.empty:
        return False, (
            f"⚠️ La guía {guia_old} ya tiene un empate activo con "
            f"{existing.iloc[0]['Guía Nueva']}. Revierte ese empate primero."
        )

    # ¿La guía está anulada?
    anul_existing = anuladas_df[
        (anuladas_df["Guía Anulada"].astype(str).str.strip() == guia_old)
        & (anuladas_df["Estado"].astype(str).str.upper().ne("REVERTIDA"))
    ]
    if not anul_existing.empty:
        return False, f"⚠️ La guía {guia_old} está anulada. Revierte la anulación primero."

    nueva_fila = {
        "Guía Original": guia_old,
        "Guía Nueva":    guia_new,
        "Fecha Empate":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Motivo":        motivo,
        "Usuario":       usuario,
        "Notas":         notas,
        "Estado":        "ACTIVA",
    }
    empates_df = pd.concat([empates_df, pd.DataFrame([nueva_fila])], ignore_index=True)
    gh_ok, gh_msg = _save_overrides(
        empates_df, anuladas_df,
        commit_msg=f"Empate: {guia_old} -> {guia_new}",
    )
    base_msg = f"✅ Empate registrado: {guia_old} → {guia_new}"
    if gh_ok:
        return True, base_msg + " (guardado en GitHub ✅)"
    return True, base_msg + f" ⚠️ {gh_msg}"


def add_anulacion(
    guia: str, motivo: str,
    usuario: str = "operador", notas: str = "",
) -> tuple[bool, str]:
    """Agrega una anulación. Retorna (success, mensaje)."""
    guia    = str(guia).strip()
    motivo  = str(motivo).strip()
    usuario = str(usuario).strip() or "operador"
    notas   = str(notas).strip()

    if not guia:
        return False, "❌ La guía es obligatoria."
    if not motivo:
        return False, "❌ Selecciona un motivo."

    empates_df, anuladas_df = load_overrides()

    existing = anuladas_df[
        (anuladas_df["Guía Anulada"].astype(str).str.strip() == guia)
        & (anuladas_df["Estado"].astype(str).str.upper().ne("REVERTIDA"))
    ]
    if not existing.empty:
        return False, f"⚠️ La guía {guia} ya está anulada."

    nueva_fila = {
        "Guía Anulada":    guia,
        "Fecha Anulación": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Motivo":          motivo,
        "Usuario":         usuario,
        "Notas":           notas,
        "Estado":          "ACTIVA",
    }
    anuladas_df = pd.concat([anuladas_df, pd.DataFrame([nueva_fila])], ignore_index=True)
    gh_ok, gh_msg = _save_overrides(
        empates_df, anuladas_df,
        commit_msg=f"Anular guía: {guia}",
    )
    base_msg = f"✅ Guía {guia} anulada."
    if gh_ok:
        return True, base_msg + " (guardada en GitHub ✅)"
    return True, base_msg + f" ⚠️ {gh_msg}"


def revert(tipo: str, idx: int) -> tuple[bool, str]:
    """Marca un empate o anulación como REVERTIDA por su índice."""
    empates_df, anuladas_df = load_overrides()

    if tipo == "empate":
        if idx < 0 or idx >= len(empates_df):
            return False, "❌ Índice de empate inválido."
        empates_df.at[idx, "Estado"] = "REVERTIDA"
        msg = "✅ Empate revertido."
    elif tipo == "anulacion":
        if idx < 0 or idx >= len(anuladas_df):
            return False, "❌ Índice de anulación inválido."
        anuladas_df.at[idx, "Estado"] = "REVERTIDA"
        msg = "✅ Anulación revertida."
    else:
        return False, "❌ Tipo desconocido."

    gh_ok, gh_msg = _save_overrides(
        empates_df, anuladas_df,
        commit_msg=f"Revertir {tipo} idx={idx}",
    )
    if gh_ok:
        return True, msg + " (sincronizado a GitHub ✅)"
    return True, msg + f" ⚠️ {gh_msg}"


# ---------------------------------------------------------------------------
# Histórico combinado
# ---------------------------------------------------------------------------

def get_history() -> pd.DataFrame:
    """
    Retorna histórico combinado de empates + anulaciones,
    ordenado por fecha descendente.

    Columnas internas (_tipo, _idx) sirven para los botones Deshacer.
    """
    empates_df, anuladas_df = load_overrides()

    rows: list[dict] = []
    for idx, r in empates_df.iterrows():
        rows.append({
            "Fecha":   str(r.get("Fecha Empate", "")),
            "Tipo":    "🔗 Empate",
            "Guía":    str(r.get("Guía Original", "")),
            "Detalle": f"→ {r.get('Guía Nueva', '')}",
            "Motivo":  str(r.get("Motivo", "")),
            "Usuario": str(r.get("Usuario", "")),
            "Notas":   str(r.get("Notas", "")),
            "Estado":  str(r.get("Estado", "ACTIVA")),
            "_tipo":   "empate",
            "_idx":    int(idx),
        })
    for idx, r in anuladas_df.iterrows():
        rows.append({
            "Fecha":   str(r.get("Fecha Anulación", "")),
            "Tipo":    "🚫 Anulación",
            "Guía":    str(r.get("Guía Anulada", "")),
            "Detalle": "—",
            "Motivo":  str(r.get("Motivo", "")),
            "Usuario": str(r.get("Usuario", "")),
            "Notas":   str(r.get("Notas", "")),
            "Estado":  str(r.get("Estado", "ACTIVA")),
            "_tipo":   "anulacion",
            "_idx":    int(idx),
        })

    if not rows:
        return pd.DataFrame(columns=[
            "Fecha", "Tipo", "Guía", "Detalle", "Motivo",
            "Usuario", "Notas", "Estado", "_tipo", "_idx",
        ])

    hist = pd.DataFrame(rows).sort_values("Fecha", ascending=False).reset_index(drop=True)
    return hist
