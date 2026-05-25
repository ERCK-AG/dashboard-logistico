# 🚀 Guía de despliegue — Dashboard Logístico

Esta guía te lleva paso a paso desde **0** hasta tener el dashboard
**online**, **autenticado** y **accesible vía link** — totalmente gratis.

---

## ⏱️ Lo que vas a hacer (15-20 minutos)

```
1. Probar localmente con login          → 2 min
2. Crear cuenta de GitHub               → 3 min
3. Subir el código a GitHub             → 5 min
4. Conectar Streamlit Community Cloud   → 3 min
5. Configurar secretos en el panel      → 5 min
6. Obtener el link público y compartir  → 1 min
```

---

## 🔐 Usuarios y contraseñas iniciales

| Usuario   | Contraseña  | Rol      | Puede |
|-----------|-------------|----------|-------|
| `admin`   | `admin123`  | admin    | Todo: ver, crear empates, anular guías |
| `operador`| `oper123`   | operador | Ver + crear empates / anulaciones |
| `consulta`| `consul123` | viewer   | Solo ver (sin acceso al tab Empates) |

> ⚠️ **CAMBIA estas contraseñas antes de compartir el link.**
> Para cambiarlas: edita `generate_password_hashes.py` con las nuevas
> contraseñas, ejecútalo, y pega el resultado en el panel Secrets de
> Streamlit Cloud.

---

## Paso 1️⃣ — Probar localmente

Ya está corriendo en http://localhost:8501.

Verás una pantalla de login. Ingresa con `admin / admin123` y confirma:

- [ ] El sidebar muestra tu nombre y rol "👑 Admin"
- [ ] Aparece un botón "🚪 Cerrar sesión"
- [ ] Todos los tabs cargan, incluyendo "🔄 Empates y Anulaciones"
- [ ] Si cierras sesión y entras como `consulta / consul123`:
      - [ ] El tab "Empates" muestra un mensaje de "🔒 sin permisos"

Cuando todo funcione, sigue al paso 2.

---

## Paso 2️⃣ — Crear cuenta de GitHub

Si **no tienes** cuenta:

1. Ve a https://github.com/signup
2. Usa un email permanente (puedes usar el de Businesspoint)
3. Elige un username corto (ej: `erick-bp`, `businesspoint-logistica`)
4. Verifica el email

---

## Paso 3️⃣ — Crear el repositorio y subir el código

### 3.1 — Instalar Git (si no lo tienes)

Verifica si lo tienes:
```powershell
git --version
```

Si no lo tienes, descárgalo de: https://git-scm.com/download/win
(instalación con valores por defecto está bien).

### 3.2 — Crear el repositorio en GitHub

1. Ve a https://github.com/new
2. **Repository name**: `dashboard-logistico`
3. **Description**: `Dashboard Logístico — BUSINESSPOINT S.A.`
4. **Public** ✅ (recomendado; el código no contiene datos sensibles)
5. NO marques "Add a README file" (ya tenemos uno)
6. Click **"Create repository"**

GitHub te mostrará comandos para subir código. Anota la **URL** del repo:
```
https://github.com/TU_USUARIO/dashboard-logistico.git
```

### 3.3 — Subir el código desde tu máquina

Abre PowerShell **en la carpeta del proyecto** (carpeta MEJORAS) y ejecuta:

```powershell
# Inicializar repositorio
git init
git branch -M main

# Configurar tu identidad (solo la primera vez)
git config user.email "tu_email@ejemplo.com"
git config user.name "Tu Nombre"

# Agregar archivos respetando .gitignore (NO sube secretos ni Excel)
git add .
git commit -m "Initial commit: dashboard logístico con auth"

# Conectar con GitHub (reemplaza TU_USUARIO)
git remote add origin https://github.com/TU_USUARIO/dashboard-logistico.git
git push -u origin main
```

> ⚠️ Si te pide login, usa tu username de GitHub y un **Personal Access
> Token** como contraseña (NO tu contraseña normal). Para crear el token:
> GitHub → Settings → Developer settings → Personal access tokens →
> Tokens (classic) → Generate new token → scope "repo" → copia el token.

### 3.4 — Verifica que todo subió

Ve a `https://github.com/TU_USUARIO/dashboard-logistico` y confirma:

- [ ] Aparecen los archivos `app.py`, `modules/`, `requirements.txt`
- [ ] **NO aparece** `.streamlit/secrets.toml` (debe estar gitignored)
- [ ] **NO aparece** `CONSOLIDADO JEFATURA LOGISTICA.xlsx`
- [ ] **NO aparece** `overrides.xlsx`

Si algún archivo sensible se subió por error: ¡detente y avísame!

---

## Paso 4️⃣ — Conectar Streamlit Community Cloud

1. Ve a https://streamlit.io/cloud
2. Click **"Sign up"** o **"Sign in"** → usa GitHub para conectar
3. Autoriza a Streamlit a acceder a tus repos
4. Click **"Create app"** (o "New app")
5. Configura:
   - **Repository**: `TU_USUARIO/dashboard-logistico`
   - **Branch**: `main`
   - **Main file path**: `app.py`
   - **App URL (opcional)**: deja el que asigne automáticamente
6. **NO hagas click en "Deploy" todavía** — primero configura los Secrets

---

## Paso 5️⃣ — Configurar Secrets

1. En la página de configuración de la app, click **"Advanced settings"**
2. En el campo **"Secrets"** pega el **contenido completo** de tu
   archivo local `.streamlit/secrets.toml` (la versión actualizada con
   los hashes que generaste)
3. Si vas a usar OneDrive para el Excel (recomendado más adelante):
   - Sube el archivo Excel a OneDrive
   - Genera un share link → conviértelo a download directo
   - Pega la URL en la línea `excel_url = "..."`
4. Click **"Save"**

### 🔧 Si NO usas OneDrive aún

Sin la URL de OneDrive, la app no tendrá Excel para cargar.
**Opciones temporales:**

- **A.** Commitea el Excel al repo (solo si el repo es privado): quita
  la línea `*.xlsx` del `.gitignore` y haz `git add CONSOLIDADO*.xlsx`
- **B.** Mejor: configura OneDrive en el siguiente paso

---

## Paso 6️⃣ — Deploy y obtén el link

1. Click **"Deploy"**
2. Espera 2-5 minutos (verás el log de instalación)
3. Cuando termine, Streamlit te dará una URL tipo:
   ```
   https://dashboard-logistico-xxxxx.streamlit.app
   ```
4. Ábrela en otra pestaña → debería pedirte login
5. Ingresa con `admin / admin123` → entras al dashboard ✅
6. **Comparte ese link** con quien necesite acceso

---

## 🔄 Después del deploy

### Para actualizar el código

Cada vez que cambies algo en tu computadora:

```powershell
git add .
git commit -m "Descripción del cambio"
git push
```

Streamlit Cloud detecta el push y **re-despliega automáticamente** en
~1 minuto.

### Para cambiar contraseñas

1. Edita `generate_password_hashes.py` con las nuevas contraseñas
2. Ejecuta `python generate_password_hashes.py`
3. Copia el output al panel Secrets de Streamlit Cloud
4. Click "Save" → la app se reinicia con las nuevas contraseñas

### Para actualizar el Excel

**Opción A (sin OneDrive):** sube un Excel nuevo al repo:
```powershell
git add "CONSOLIDADO JEFATURA LOGISTICA.xlsx"
git commit -m "Datos actualizados"
git push
```

**Opción B (con OneDrive):** simplemente edita el archivo en OneDrive
— la app lo descarga cada vez que se carga.

### Para configurar OneDrive (cuando lo necesites)

1. Sube el Excel a OneDrive
2. Click derecho → "Compartir" → "Cualquier persona con el enlace"
3. Copia el link
4. Necesitarás convertirlo a **direct download link** (te ayudo cuando
   llegues a este paso)
5. Pega la URL en `excel_url` del panel Secrets

---

## 🆘 Problemas comunes

### "ImportError: streamlit_authenticator"
→ El paquete está en `requirements.txt`. Si Streamlit Cloud no lo
instala, revisa que el archivo esté en el commit.

### "Sin datos cargados"
→ No hay Excel disponible. Configura `excel_url` en Secrets o sube el
Excel al repo.

### "El login no funciona después del deploy"
→ Verifica que pegaste los Secrets COMPLETOS (toda la sección `[auth]`).

### "Olvidé la contraseña"
→ Genera hashes nuevos con `generate_password_hashes.py` y reemplaza en
Secrets.

---

¿Listo para empezar? **Cuéntame cuando hayas hecho el paso 1 (probar
localmente con login)** y seguimos.
