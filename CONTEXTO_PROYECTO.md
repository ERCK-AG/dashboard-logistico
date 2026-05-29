# 📋 CONTEXTO DEL PROYECTO — Dashboard Logístico

> **Para empezar un chat nuevo:** copia y pega este archivo completo (o di
> "lee CONTEXTO_PROYECTO.md") para que el asistente tenga todo el contexto
> sin tener que re-explicar nada.

---

## 🎯 Qué es

Dashboard logístico en **Streamlit** para **BUSINESSPOINT S.A. / LogikTel**
(transporte de carga liviana, cliente **CNT EP**). Lee un Excel de OneDrive,
cruza varias hojas y genera KPIs, gráficos, mapas y tablas de gestión.

- **App en vivo:** https://dashboard-logistico-qfaim86hzb2hsshmehwwvp.streamlit.app/
- **Repo GitHub:** `ERCK-AG/dashboard-logistico` (público)
- **Carpeta local:** `...\Transporte de Carga Liviana\MEJORAS`
- **Login admin:** `admin` / `ErickLogikTel2026`

---

## 🏗️ Arquitectura / Archivos

```
MEJORAS/
├── app.py                      # App principal (tabs, sidebar, login)
├── modules/
│   ├── auth.py                 # Login (streamlit-authenticator) + roles
│   ├── user_store.py           # Usuarios en users.json + commit a GitHub (PAT)
│   ├── data_loader.py          # Carga Excel (OneDrive/local), caché, enriquecimiento
│   ├── cleaner.py              # Limpieza, mapeo columnas, normalización, relabeling
│   ├── charts.py               # Gráficos Plotly + builders de tablas (gestión/detalle)
│   ├── kpis.py                 # Cálculo de KPIs
│   ├── specialty_views.py      # Render de hojas de especialidad (logística/telefonía)
│   ├── overrides.py            # Empates y anulaciones (persist en overrides.xlsx + GitHub)
│   └── alerts.py               # Alertas operativas
├── users.json                  # Base de usuarios (en repo, commit por PAT)
├── overrides.xlsx              # Histórico empates/anulaciones (en repo, commit por PAT)
├── .streamlit/
│   ├── config.toml             # toolbarMode=minimal, tema, etc. (SÍ en repo)
│   └── secrets.toml            # Credenciales (NO en repo, gitignored)
├── requirements.txt
└── generate_password_hashes.py # Utilidad para generar hashes bcrypt
```

---

## ☁️ Despliegue (cómo funciona)

1. **Código** → GitHub (`ERCK-AG/dashboard-logistico`)
2. **Streamlit Cloud** observa el repo → re-despliega automático en cada `git push`
3. **Excel** → OneDrive con link directo (`&download=1`), URL en Secrets `[onedrive]`
4. **Persistencia** (usuarios, empates) → la app commitea a GitHub vía **PAT**
   (token en Secrets `[github]`), Streamlit Cloud redespliega → datos persisten

**Secrets en Streamlit Cloud** (Settings → Secrets) tienen 3 secciones:
`[onedrive]` (excel_url), `[auth]` (cookie + usuarios), `[github]` (PAT).

**Flujo para cambios de código:**
```
editar local → git add/commit/push → Streamlit Cloud redespliega (~1 min)
```

---

## 📊 Estructura del Excel (OneDrive)

| Hoja | Tipo | Columnas clave |
|---|---|---|
| **Estado de Gestion** | principal (~363 filas) | GUIA, ESTADO ACTUAL, DETALLE ESTADO, FECHA SS, FECHA ESTADO, ORIGEN/DESTINO (códigos agencia 3 letras), DESTINATARIO, TELEFONOS, DIRECCION DE ENTREGA, RECIBIDO POR, HORA ENTREGA, NRO VISITAS, PRIMERA/SEGUNDA VISITA, RESULTADO VISITA 1/2, GESTIONISTA |
| **ENVIOS CENTRO DE DISTRIBUCION** | logística | PROVINCIA ORIGEN/DESTINO, AGENCIA DESTINO, PEDIDO, GUIA 1/2/3 |
| **ENVIOS ENTRE PROVINCIAS** | logística | (igual que arriba) |
| **ENVIOS TELEFONIA MOVIL** | telefonía | Material, Texto breve, Cantidad de pedido, Por entregar (cantidad), Nombre 1, PESO, GUIA 1/2 |
| **BASE** | ignorada | — |

**Nota:** Estado de Gestión NO tiene columna PEDIDO ni AGENCIA; se obtienen
cruzando GUIA 1/2/3 con las hojas de especialidad (en `data_loader._build_enrichment`).

---

## ✅ Funcionalidades implementadas

### Tabs (orden): Gestión · Por Estado · Mapa · Detalle · [3 especialidad] · Empates · Usuarios · Info

- **Login + roles**: admin (todo), operador (ver + empates), viewer (solo ver)
- **Empates de guías**: guía no entregada → nueva guía; la original sale de reportes
- **Anulación de guías**: excluir del flujo
- **Persistencia** de empates/anulaciones en GitHub (sobreviven redeploys)
- **Gestión de usuarios** (tab admin): crear/eliminar/resetear contraseña → commit a GitHub
- **Cruces por GUIA** (lookup desde hojas especialidad):
  - N° Pedido, Agencia/Centro, Estado Guía 1, Recibido por, Fecha/Hora recepción
- **Mapa Ecuador**: códigos de agencia (UIO, GYE...) → provincias (en `cleaner.AGENCIA_CODE_TO_PROVINCIA`)
- **Búsqueda** por guía/pedido (ignora filtros; encuentra empatadas/anuladas vía `df_full`)
- **Tablas en MAYÚSCULAS** (`charts.uppercase_table`)
- **Auto-refresh cada 2h** (streamlit-autorefresh)
- **Relabeling de estados** (`cleaner.STATE_RELABEL`): "Pick UP (Manual)" → "Pendiente Recolección"
- **Tabla Detalle por Guía**: pendientes arriba, entregados al medio, devoluciones al final
- **Tabla dedicada "Devoluciones al Shipper"**
- **Top 10 pendientes** (excluye entregadas y devoluciones)
- **Buscador guía/pedido** en tabla de especialidad logística

### Optimizaciones aplicadas
- Enriquecimiento dentro del caché + vectorizado (zip, no iterrows)
- KPIs y gráficos pesados cacheados (`@st.cache_data ttl=60`)
- Mapas con itertuples/zip
- Cache TTL 60s

---

## 👥 Usuarios actuales (en users.json)

| Usuario | Rol | Empresa |
|---|---|---|
| admin | admin | LogikTel |
| operador | operador | — |
| consulta | viewer | — |
| alexander_eras | viewer | CNT EP |
| mario_cadena | viewer | CNT EP |
| fredda_zabala | operador | LogikTel |
| richard_manguia | operador | LogikTel |
| jorge_rada | viewer | — |
| daysi_parra | viewer | — |

---

## 🔧 Convenciones técnicas

- Python 3.13, Streamlit, Pandas, Plotly, openpyxl, bcrypt, streamlit-authenticator
- Columnas lógicas se detectan por nombre flexible en `cleaner.COLUMN_MAPPINGS`
- Las guías del Excel traen espacios al final → siempre `.str.strip()`
- `df_raw` = con overrides (reportes) · `df_full` = sin overrides (búsqueda)
- Cambios se prueban: `python -c "import ast; ast.parse(open('app.py',encoding='utf-8').read())"`
- Para descargar el Excel en pruebas: GET a la URL de OneDrive + `&download=1`
