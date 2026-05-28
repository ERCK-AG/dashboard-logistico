"""
cleaner.py — Normalización y limpieza de datos logísticos.
Detecta columnas por nombre (case-insensitive, con o sin tildes).
"""

import pandas as pd
import numpy as np
import unicodedata
import re
from typing import Optional

# ---------------------------------------------------------------------------
# Mapeos flexibles de nombres de columna
# ---------------------------------------------------------------------------
COLUMN_MAPPINGS: dict[str, list[str]] = {
    "guia": [
        "guia", "guía", "n° guia", "n° guía", "numero guia", "número guía",
        "num guia", "num_guia", "nro guia", "guia 1", "guia1", "nro guia 1",
        "order", "tracking", "codigo", "código", "cod", "referencia",
        "nro.", "no.", "no guia", "no. guia",
    ],
    "estado": [
        "estado", "estado actual", "status", "estado_actual",
        "estado logistico", "estado logístico", "ultimo estado",
        "último estado", "situacion", "situación",
    ],
    "incidencia": [
        "incidencia", "novedad", "tipo incidencia", "tipo_incidencia",
        "novedad logistica", "novedad logística", "motivo", "observacion",
        "observación", "issue", "problema", "tipo novedad",
    ],
    "provincia_origen": [
        "provincia origen", "provincia_origen", "origen", "ciudad origen",
        "ciudad_origen", "prov origen", "prov_origen", "remitente provincia",
        "ciudad remitente", "prov. origen", "provincia o.", "desde",
    ],
    "provincia_destino": [
        "provincia destino", "provincia_destino", "destino", "ciudad destino",
        "ciudad_destino", "prov destino", "prov_destino",
        "destinatario provincia", "ciudad destinatario",
        "prov. destino", "provincia d.", "hacia",
    ],
    "fecha_creacion": [
        "fecha creacion", "fecha_creacion", "fecha creación", "fecha_creación",
        "fecha pedido", "fecha_pedido", "fecha ingreso", "fecha_ingreso",
        "created_at", "creation_date", "fecha", "f. creacion", "f. pedido",
        "fec. creacion", "fec. pedido",
    ],
    "fecha_despacho": [
        "fecha despacho", "fecha_despacho", "despacho", "fecha envio",
        "fecha_envio", "fecha envío", "shipped_date", "dispatch_date",
        "f. despacho", "fec. despacho",
    ],
    "fecha_entrega": [
        "fecha entrega", "fecha_entrega", "entrega", "delivered_date",
        "delivery_date", "fecha entregado", "f. entrega", "fec. entrega",
    ],
    "tiempo_gestion": [
        "tiempo gestion", "tiempo_gestion", "tiempo gestión",
        "tiempo_gestión", "dias gestion", "días gestión",
        "transit_time", "dias transito", "días tránsito",
    ],
    "responsable": [
        "responsable", "agente", "operador", "operator", "agent",
        "ejecutivo", "gestor", "coordinador", "gestionista",
    ],
    "cliente": [
        "cliente", "client", "customer", "remitente", "shipper",
        "nombre cliente", "razon social", "razón social",
    ],
    "destinatario": [
        "destinatario", "recipient", "consignee", "nombre destinatario",
        "nombre dest.", "recibe",
    ],
    "telefono": [
        "telefonos", "telefono", "teléfono", "teléfonos", "celular",
        "celulares", "contacto", "telefono destinatario", "tel",
        "numero telefono", "número teléfono",
    ],
    "direccion_entrega": [
        "direccion de entrega", "dirección de entrega", "direccion entrega",
        "dirección entrega", "direccion", "dirección", "direccion destino",
        "dirección destino", "address",
    ],
    "transportista": [
        "transportista", "carrier", "courier", "empresa transporte",
        "empresa_transporte", "proveedor", "empresa", "operadora",
    ],
    "observaciones": [
        "observaciones", "observacion", "observación", "notas", "notes",
        "comentarios", "comments", "detalle", "detalle novedad",
    ],
    "peso": ["peso", "weight", "kg", "kilos", "peso kg", "peso aproximado", "peso util"],
    "bultos": [
        "bultos", "packages", "piezas", "pieces", "cantidad",
        "cant.", "unidades",
    ],
    "valor": [
        "valor", "value", "monto", "amount", "valor declarado",
        "valor mercancia", "valor mercancía", "valor asegurado",
    ],
    "ultimo_estado": [
        "ultimo estado", "último estado", "last status",
        "ultimo_estado", "novedad final",
    ],
    # ── Nuevas columnas del flujo CNT ──────────────────────────────────────
    "pedido": [
        "pedido", "n° pedido", "numero pedido", "número pedido",
        "nro pedido", "num pedido", "id pedido", "id_pedido",
        "nro. pedido", "no. pedido", "numero de pedido",
    ],
    "fecha_ss": [
        "fecha ss", "fecha_ss", "fecha sistema", "fechass",
        "f. ss", "fec. ss",
    ],
    "fecha_estado": [
        "fecha estado", "fecha_estado", "fecha de estado",
        "fecha actualizacion", "fecha actualización", "fecha_actualizacion",
        "f. estado", "fec. estado",
    ],
    "detalle_estado": [
        "detalle estado", "detalle_estado", "descripcion estado",
        "descripción estado", "detalle novedad",
    ],
    "fecha_ao": [
        "fecha ao", "fecha_ao", "fecha a/o", "fecha aviso origen",
    ],
    "arribo_destino": [
        "arribo destino", "arribo_destino", "fecha arribo destino",
    ],
    # ── Columnas de visitas (Estado de Gestión) ────────────────────────────
    "nro_visitas": [
        "nro visitas", "nro. visitas", "numero visitas", "número visitas",
        "n visitas", "n° visitas", "visitas",
    ],
    "primera_visita": [
        "primera visita", "primera_visita", "fecha primera visita",
        "fecha 1ra visita", "1ra visita",
    ],
    "resultado_visita1": [
        "resultado visita 1", "resultado visita1", "resultado_visita1",
        "resultado primera visita", "resultado 1", "resultado v1",
    ],
    "segunda_visita": [
        "segunda visita", "segunda_visita", "fecha segunda visita",
        "fecha 2da visita", "2da visita",
    ],
    "resultado_visita2": [
        "resultado visita 2", "resultado visita2", "resultado_visita2",
        "resultado segunda visita", "resultado 2", "resultado v2",
    ],
    "fec_dl_programada": [
        "fec dl programada", "fec. dl programada", "fecha dl programada",
        "fecha programada entrega", "fecha programada", "fec programada",
    ],
    "hora_entrega": [
        "hora entrega", "hora_entrega", "hora de entrega",
    ],
    "codigo_referencia": [
        "codigo referencia", "código referencia", "cod referencia",
        "codigo_referencia", "referencia", "cod. referencia",
    ],
}

# ---------------------------------------------------------------------------
# Mapeo de códigos de agencia CNT → provincia estándar
# ---------------------------------------------------------------------------
AGENCIA_CODE_TO_PROVINCIA: dict[str, str] = {
    # ── Agencias principales ─────────────────────────────────────────────────
    "UIO": "PICHINCHA",        # Quito
    "GYE": "GUAYAS",           # Guayaquil
    "CUE": "AZUAY",            # Cuenca
    "MEC": "MANABI",           # Manta
    "LOJ": "LOJA",             # Loja
    "RBM": "CHIMBORAZO",       # Riobamba
    "IBR": "IMBABURA",         # Ibarra
    "LTG": "COTOPAXI",         # Latacunga
    "MCH": "EL ORO",           # Machala
    "ESM": "ESMERALDAS",       # Esmeraldas
    "TCA": "CARCHI",           # Tulcán
    "LAG": "SUCUMBIOS",        # Lago Agrio
    "QVD": "LOS RIOS",         # Quevedo
    "BBA": "LOS RIOS",         # Babahoyo
    "GRD": "BOLIVAR",          # Guaranda
    "ORE": "ORELLANA",         # El Coca / Francisco de Orellana
    "TEN": "NAPO",             # Tena
    "PUY": "PASTAZA",          # Puyo
    "CHO": "MANABI",           # Chone
    "PVO": "MANABI",           # Portoviejo
    # ── Agencias secundarias ─────────────────────────────────────────────────
    "AMB": "TUNGURAHUA",       # Ambato
    "SDE": "SANTO DOMINGO",    # Santo Domingo de los Tsáchilas
    "SDT": "SANTO DOMINGO",    # variante Santo Domingo
    "SNA": "SANTA ELENA",      # Santa Elena / Salinas / La Libertad
    "AZO": "CANAR",            # Azogues
    "MCS": "MORONA SANTIAGO",  # Macas
    "ZAM": "ZAMORA CHINCHIPE", # Zamora
    "COC": "ORELLANA",         # El Coca (variante)
    "GAL": "GALAPAGOS",        # Galápagos
    "ATF": "IMBABURA",         # Atuntaqui (estimado)
    "SOZ": "LOJA",             # Sur del Ecuador (estimado)
    "SAC": "CANAR",            # Sur de la Sierra (estimado)
    "STC": "GALAPAGOS",        # Santa Cruz (estimado)
}

# ---------------------------------------------------------------------------
# Coordenadas y aliases de provincias de Ecuador
# ---------------------------------------------------------------------------
PROVINCE_ALIASES: dict[str, str] = {
    "QUITO": "PICHINCHA",
    "GUAYAQUIL": "GUAYAS",
    "CUENCA": "AZUAY",
    "PORTOVIEJO": "MANABI",
    "MANTA": "MANABI",
    "MONTECRISTI": "MANABI",
    "CHONE": "MANABI",
    "MACHALA": "EL ORO",
    "SANTA ROSA": "EL ORO",
    "BABAHOYO": "LOS RIOS",
    "QUEVEDO": "LOS RIOS",
    "VINCES": "LOS RIOS",
    "LOJA": "LOJA",
    "CATAMAYO": "LOJA",
    "AMBATO": "TUNGURAHUA",
    "RIOBAMBA": "CHIMBORAZO",
    "IBARRA": "IMBABURA",
    "OTAVALO": "IMBABURA",
    "ESMERALDAS": "ESMERALDAS",
    "ATACAMES": "ESMERALDAS",
    "TULCAN": "CARCHI",
    "IPIALES": "CARCHI",
    "GUARANDA": "BOLIVAR",
    "LATACUNGA": "COTOPAXI",
    "SAQUISILI": "COTOPAXI",
    "AZOGUES": "CANAR",
    "MACAS": "MORONA SANTIAGO",
    "ZAMORA": "ZAMORA CHINCHIPE",
    "NUEVA LOJA": "SUCUMBIOS",
    "LAGO AGRIO": "SUCUMBIOS",
    "TENA": "NAPO",
    "FRANCISCO DE ORELLANA": "ORELLANA",
    "COCA": "ORELLANA",
    "PUYO": "PASTAZA",
    "SANTO DOMINGO": "SANTO DOMINGO",
    "SANTA ELENA": "SANTA ELENA",
    "LA LIBERTAD": "SANTA ELENA",
    "SALINAS": "SANTA ELENA",
    "GALAPAGOS": "GALAPAGOS",
    "PUERTO BAQUERIZO": "GALAPAGOS",
    "DAULE": "GUAYAS",
    "MILAGRO": "GUAYAS",
    "DURAN": "GUAYAS",
    "SAMBORONDON": "GUAYAS",
}

PROVINCE_COORDS: dict[str, dict] = {
    "PICHINCHA":        {"lat": -0.22,  "lon": -78.51, "capital": "Quito"},
    "GUAYAS":           {"lat": -2.17,  "lon": -79.92, "capital": "Guayaquil"},
    "AZUAY":            {"lat": -2.89,  "lon": -78.98, "capital": "Cuenca"},
    "MANABI":           {"lat": -1.05,  "lon": -80.45, "capital": "Portoviejo"},
    "EL ORO":           {"lat": -3.26,  "lon": -79.96, "capital": "Machala"},
    "LOS RIOS":         {"lat": -1.81,  "lon": -79.53, "capital": "Babahoyo"},
    "LOJA":             {"lat": -3.99,  "lon": -79.20, "capital": "Loja"},
    "TUNGURAHUA":       {"lat": -1.25,  "lon": -78.63, "capital": "Ambato"},
    "CHIMBORAZO":       {"lat": -1.67,  "lon": -78.65, "capital": "Riobamba"},
    "IMBABURA":         {"lat":  0.35,  "lon": -78.12, "capital": "Ibarra"},
    "ESMERALDAS":       {"lat":  0.96,  "lon": -79.65, "capital": "Esmeraldas"},
    "CARCHI":           {"lat":  0.81,  "lon": -77.72, "capital": "Tulcán"},
    "BOLIVAR":          {"lat": -1.59,  "lon": -79.00, "capital": "Guaranda"},
    "COTOPAXI":         {"lat": -0.93,  "lon": -78.62, "capital": "Latacunga"},
    "CANAR":            {"lat": -2.74,  "lon": -78.85, "capital": "Azogues"},
    "MORONA SANTIAGO":  {"lat": -2.30,  "lon": -78.11, "capital": "Macas"},
    "ZAMORA CHINCHIPE": {"lat": -4.07,  "lon": -78.95, "capital": "Zamora"},
    "SUCUMBIOS":        {"lat": -0.09,  "lon": -76.88, "capital": "Nueva Loja"},
    "NAPO":             {"lat": -0.99,  "lon": -77.81, "capital": "Tena"},
    "ORELLANA":         {"lat": -0.46,  "lon": -76.99, "capital": "F. de Orellana"},
    "PASTAZA":          {"lat": -1.49,  "lon": -78.00, "capital": "Puyo"},
    "SANTO DOMINGO":    {"lat": -0.25,  "lon": -79.17, "capital": "Santo Domingo"},
    "SANTA ELENA":      {"lat": -2.23,  "lon": -80.86, "capital": "Santa Elena"},
    "GALAPAGOS":        {"lat": -0.90,  "lon": -89.61, "capital": "Pto. Baquerizo"},
}

# Renombrado de valores de estado/detalle para mostrar etiquetas más claras.
# Clave: valor normalizado (lower + strip). Valor: etiqueta a mostrar.
# Se aplica tanto a la columna de estado como a la de detalle_estado.
STATE_RELABEL: dict[str, str] = {
    "pick up (manual)": "Pendiente Recolección",
}


# Estados considerados "entregado"
DELIVERED_STATES = {
    "entregado", "entregada", "delivered", "completado", "completada",
    "finalizado", "finalizada", "cerrado", "cerrada", "concluido",
    "concluida", "exitoso", "exitosa",
}

# Estados considerados "pendiente"
PENDING_STATES = {
    "pendiente", "en proceso", "en tránsito", "en transito",
    "en ruta", "en camino", "procesando", "recibido", "despachado",
    "en bodega", "retenido",
}

# Palabras clave que indican incidencia de entrega (no se pudo entregar en primera visita)
# Se buscan en la columna de estado Y/O detalle_estado (subcadena, no exacta)
INCIDENCE_KEYWORDS: list[str] = [
    "visitado",
    "no hay quien",
    "desconocido",
    "ausente",
    "rechazado",
    "devuelto",
    "no entregado",
    "fallido",
    "intento",
    "novedad",
    "no reside",
    "domicilio cerrado",
    "no encontrado",
    "direcci",          # direccion incorrecta / dirección incorrecta
    "no recibe",
    "se niega",
    "lugar incorrecto",
    "dato incorrecto",
    "sin acceso",
    "zona restringida",
    "reintento",
]

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _normalize_str(s: str) -> str:
    """Quita tildes, convierte a minúsculas y elimina espacios extras."""
    if not isinstance(s, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", s)
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_str.lower().strip())


def find_column(df: pd.DataFrame, key: str) -> Optional[str]:
    """
    Busca en el DataFrame la columna que mejor coincide con la clave lógica.
    Retorna el nombre real de la columna o None si no se encuentra.
    """
    candidates = COLUMN_MAPPINGS.get(key, [key])
    normalized_cols = {_normalize_str(c): c for c in df.columns}

    for candidate in candidates:
        norm = _normalize_str(candidate)
        if norm in normalized_cols:
            return normalized_cols[norm]
    return None


def get_column_map(df: pd.DataFrame) -> dict[str, Optional[str]]:
    """Retorna un dict {clave_lógica: nombre_real_columna} para todo el DataFrame."""
    return {key: find_column(df, key) for key in COLUMN_MAPPINGS}


# ---------------------------------------------------------------------------
# Limpieza principal
# ---------------------------------------------------------------------------

def normalize_province(value) -> str:
    """
    Normaliza ciudad/provincia/código de agencia CNT al nombre estándar.

    Orden de resolución:
      1. Código de agencia CNT (2-4 letras, ej. "UIO", "GYE") → provincia
      2. Alias de ciudad conocido (ej. "QUITO" → "PICHINCHA")
      3. Provincia ya conocida tal cual
      4. Valor original capitalizado como fallback
    """
    if pd.isna(value) or str(value).strip() == "":
        return "DESCONOCIDO"

    raw = str(value).strip()
    upper = raw.upper()

    # 1. Código de agencia CNT (2-4 letras mayúsculas, sin espacios)
    if re.match(r"^[A-Z]{2,4}$", upper) and upper in AGENCIA_CODE_TO_PROVINCIA:
        return AGENCIA_CODE_TO_PROVINCIA[upper]

    # 2-4. Lógica existente de alias / provincia conocida
    norm = _normalize_str(raw).upper()
    if norm in PROVINCE_ALIASES:
        return PROVINCE_ALIASES[norm]
    for alias, province in PROVINCE_ALIASES.items():
        if alias in norm:
            return province
    if norm in PROVINCE_COORDS:
        return norm
    return norm.title()  # Devolver tal cual, capitalizado


def normalize_state(value) -> str:
    if pd.isna(value) or str(value).strip() == "":
        return "SIN ESTADO"
    return str(value).strip().upper()


def clean_dates(df: pd.DataFrame, date_columns: list[str]) -> pd.DataFrame:
    for col in date_columns:
        if col in df.columns:
            raw = df[col]
            # Si ya son datetime (leídos por openpyxl), conservar tal cual
            if pd.api.types.is_datetime64_any_dtype(raw):
                continue
            # Intentar formato ISO (YYYY-MM-DD …) que es como CNT exporta las fechas
            try:
                parsed = pd.to_datetime(raw, errors="coerce", format="mixed", dayfirst=False)
            except TypeError:
                # pandas < 2.0 no tiene format="mixed"
                parsed = pd.to_datetime(raw, errors="coerce", infer_datetime_format=True)
            # Fallback a dayfirst solo si la mayoría quedó NaT (fechas en DD/MM/YYYY)
            nat_pct = parsed.isna().mean()
            if nat_pct > 0.5:
                try:
                    parsed = pd.to_datetime(raw, errors="coerce", format="mixed", dayfirst=True)
                except TypeError:
                    parsed = pd.to_datetime(raw, errors="coerce", dayfirst=True)
            df[col] = parsed
    return df


def calculate_time_deltas(df: pd.DataFrame, col_map: dict[str, Optional[str]]) -> pd.DataFrame:
    """Calcula diferencias de tiempo entre etapas logísticas."""
    fc = col_map.get("fecha_creacion")
    fd = col_map.get("fecha_despacho")
    fe = col_map.get("fecha_entrega")

    if fc and fe and fc in df.columns and fe in df.columns:
        df["_dias_total"] = (df[fe] - df[fc]).dt.days
        df["_dias_total"] = df["_dias_total"].clip(lower=0)

    if fc and fd and fc in df.columns and fd in df.columns:
        df["_dias_prep"] = (df[fd] - df[fc]).dt.days
        df["_dias_prep"] = df["_dias_prep"].clip(lower=0)

    if fd and fe and fd in df.columns and fe in df.columns:
        df["_dias_transito"] = (df[fe] - df[fd]).dt.days
        df["_dias_transito"] = df["_dias_transito"].clip(lower=0)

    # Tiempo de gestión: FECHA SS → FECHA ESTADO (en horas)
    fss  = col_map.get("fecha_ss")
    fest = col_map.get("fecha_estado")
    if fss and fest and fss in df.columns and fest in df.columns:
        delta = df[fest] - df[fss]
        df["_tiempo_gestion_horas"] = (delta.dt.total_seconds() / 3600).clip(lower=0)

    return df


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Optional[str]]]:
    """
    Limpia y normaliza el DataFrame principal.
    Retorna (df_limpio, col_map).
    """
    df = df.copy()

    # Eliminar filas completamente vacías
    df.dropna(how="all", inplace=True)

    # Mapear columnas lógicas
    col_map = get_column_map(df)

    # Limpiar fechas detectadas
    date_cols = [
        col_map.get("fecha_creacion"),
        col_map.get("fecha_despacho"),
        col_map.get("fecha_entrega"),
        col_map.get("fecha_ss"),
        col_map.get("fecha_estado"),
        col_map.get("fecha_ao"),
        col_map.get("arribo_destino"),
        col_map.get("primera_visita"),
        col_map.get("segunda_visita"),
        col_map.get("fec_dl_programada"),
    ]
    date_cols = [c for c in date_cols if c]
    df = clean_dates(df, date_cols)

    # Normalizar provincias
    for key in ("provincia_origen", "provincia_destino"):
        col = col_map.get(key)
        if col and col in df.columns:
            df[col] = df[col].apply(normalize_province)

    # Normalizar estado
    estado_col = col_map.get("estado")
    if estado_col and estado_col in df.columns:
        df[estado_col] = df[estado_col].apply(normalize_state)

    # Renombrar etiquetas (ej: "Pick UP (Manual)" → "Pendiente Recolección")
    # Se aplica a estado y detalle_estado (comparación case-insensitive).
    def _relabel(value):
        if pd.isna(value):
            return value
        key = str(value).strip().lower()
        return STATE_RELABEL.get(key, value)

    for _key in ("estado", "detalle_estado"):
        _col = col_map.get(_key)
        if _col and _col in df.columns:
            df[_col] = df[_col].apply(_relabel)

    # Calcular tiempos
    df = calculate_time_deltas(df, col_map)

    # Columna auxiliar de entregado
    if estado_col and estado_col in df.columns:
        df["_entregado"] = df[estado_col].apply(
            lambda x: _normalize_str(str(x)) in DELIVERED_STATES
        )
    else:
        df["_entregado"] = False

    # Columna auxiliar de incidencia de entrega (primera visita fallida).
    # Prioridad:
    #   1. RESULTADO VISITA 1 existe, tiene valor y NO es un estado de entregado
    #   2. Fallback: tiene registro en Estado de Gestión pero no fue entregado
    col_rv1 = col_map.get("resultado_visita1")
    if col_rv1 and col_rv1 in df.columns:
        rv1_str = df[col_rv1].astype(str).str.strip()
        rv1_filled = rv1_str.ne("") & rv1_str.ne("nan") & df[col_rv1].notna()
        rv1_not_delivered = ~rv1_str.apply(
            lambda x: _normalize_str(x) in DELIVERED_STATES
        )
        df["_incidencia"] = rv1_filled & rv1_not_delivered
    elif "_tiempo_gestion_horas" in df.columns:
        df["_incidencia"] = (
            df["_tiempo_gestion_horas"].notna() & (~df["_entregado"])
        )
    else:
        df["_incidencia"] = ~df["_entregado"]

    return df, col_map
