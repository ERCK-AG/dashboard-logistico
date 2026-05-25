# Dashboard Logístico — BUSINESSPOINT S.A.
**Transporte de Carga Liviana | Jefatura Logística**

Dashboard interactivo que lee automáticamente el archivo Excel de la carpeta y
cruza la hoja **Consolidado** con **Estado de Gestión** para generar KPIs,
gráficos y alertas en tiempo real.

---

## Requisitos

- Python 3.10 o superior
- Las librerías listadas en `requirements.txt`

---

## Instalación rápida

Abre una terminal en la carpeta `MEJORAS` y ejecuta:

```bash
# 1. Crear entorno virtual (recomendado)
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Mac/Linux

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Lanzar el dashboard
streamlit run app.py
```

El navegador se abrirá automáticamente en `http://localhost:8501`.

---

## Estructura del proyecto

```
MEJORAS/
├── app.py                  ← Aplicación principal Streamlit
├── requirements.txt        ← Dependencias Python
├── README.md               ← Este archivo
├── CONSOLIDADO JEFATURA LOGISTICA.xlsx   ← Excel fuente
└── modules/
    ├── __init__.py
    ├── data_loader.py      ← Carga, caché y cruce de hojas Excel
    ├── cleaner.py          ← Normalización de datos y columnas
    ├── kpis.py             ← Cálculo de todos los KPIs
    ├── charts.py           ← Visualizaciones Plotly
    └── alerts.py           ← Sistema de alertas y detección de retrasos
```

---

## Funcionamiento del Excel

El sistema detecta **automáticamente** el archivo `.xlsx` más reciente de la
carpeta. Cada 30 segundos (configurable) verifica si el archivo cambió y
recarga los datos sin reiniciar.

### Hojas requeridas
| Hoja | Rol |
|---|---|
| `Consolidado` | **Fuente principal** — define qué pedidos se analizan |
| `Estado de Gestión` | Complementaria — se cruza por N° Guía/Pedido |

### Cruce de datos
El sistema busca la columna de **N° Guía o Pedido** en ambas hojas (por nombre,
sin importar mayúsculas ni tildes) y hace un LEFT JOIN: todos los pedidos del
Consolidado, enriquecidos con la info de Estado de Gestión cuando existe.

### Detección flexible de columnas
El sistema reconoce columnas por nombre sin importar tildes, mayúsculas ni
pequeñas variaciones. Por ejemplo, todas estas son equivalentes:

- `Guía`, `GUIA`, `N° Guia`, `Numero Pedido`, `Nro. Guía`, `tracking`
- `Provincia Destino`, `PROV. DESTINO`, `ciudad_destino`
- `Fecha Creación`, `FECHA PEDIDO`, `fecha_ingreso`

---

## KPIs calculados

| # | KPI |
|---|---|
| 1 | Total de pedidos |
| 2 | Pedidos entregados |
| 3 | Pedidos pendientes |
| 4 | Pedidos con incidencia |
| 5 | Tiempo promedio de entrega (días) |
| 6 | % Cumplimiento SLA |
| 7 | Provincia con más incidencias |
| 8 | Provincia con mayor retraso |
| 9 | Tiempo promedio por estado logístico |
| 10 | Tiempo promedio origen → destino |

---

## Visualizaciones

- **Tendencia** diaria o semanal de pedidos
- **Distribución** por estado logístico (dona)
- **Entregas** por provincia destino (barras)
- **Heatmap** de incidencias por provincia y tipo
- **Top retrasos** por provincia
- **Embudo** logístico (recibido → despachado → entregado)
- **Ranking** de tiempos min/prom/max por provincia
- **Mapa** geográfico de Ecuador con burbujas de incidencias / retrasos
- **Gauge SLA** con semáforo visual
- **Tabla** interactiva con búsqueda por guía y exportación

---

## Filtros disponibles

- Rango de fechas
- Provincia origen / destino
- Estado logístico
- Tipo de incidencia
- Responsable
- Cliente
- Transportista
- Búsqueda libre por N° Guía

---

## Configuración del SLA

El SLA (tiempo máximo de entrega) se configura en el panel lateral.
Por defecto: **3 días**. Afecta el gauge, las alertas y los reportes de pedidos
retrasados.

---

## Exportación

Desde el sidebar y las pestañas puedes descargar:
- **CSV** — todos los pedidos con filtros aplicados
- **Excel** — misma data en formato `.xlsx`
- **CSV de retrasados** — solo pedidos fuera de SLA

---

## Solución de problemas

| Problema | Causa probable | Solución |
|---|---|---|
| `PermissionError` al leer Excel | Archivo abierto en Excel | El sistema intenta una copia temporal automáticamente |
| "No se encontró hoja Consolidado" | Nombre distinto en el Excel | Verificar nombre exacto de la hoja |
| KPIs en "—" | Columnas no detectadas | Revisar advertencias en pantalla |
| Mapa sin datos | Provincias no reconocidas | Verificar que los nombres coincidan con provincias de Ecuador |

---

*Desarrollado con Python + Streamlit + Plotly | BUSINESSPOINT S.A.*
