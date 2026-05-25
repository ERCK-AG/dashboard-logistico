"""
auth.py — Autenticación de usuarios para el dashboard.

Usa streamlit-authenticator con credenciales desde st.secrets.

En LOCAL: las credenciales se leen de `.streamlit/secrets.toml`
En CLOUD: se leen del panel "Secrets" de Streamlit Community Cloud

Roles:
    - admin    : acceso completo (incluyendo empates/anulaciones)
    - operador : ver + crear empates/anulaciones
    - viewer   : solo lectura (no ve el tab de empates)
"""

from __future__ import annotations

from typing import Optional

import streamlit as st


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_credentials_dict() -> dict:
    """Construye el dict de credenciales para streamlit-authenticator desde secrets."""
    try:
        users_secret = st.secrets["auth"]["credentials"]["usernames"]
    except (KeyError, FileNotFoundError):
        return {"usernames": {}}

    # Streamlit secrets es un AttrDict — convertir a dict normal
    usernames: dict = {}
    for username, user_data in users_secret.items():
        usernames[username] = {
            "name":     user_data.get("name", username),
            "email":    user_data.get("email", ""),
            "password": user_data.get("password", ""),
            "role":     user_data.get("role", "viewer"),
        }
    return {"usernames": usernames}


def _get_cookie_config() -> tuple[str, str, int]:
    """Retorna (cookie_name, cookie_key, expiry_days)."""
    try:
        c = st.secrets["auth"]["cookie"]
        return (
            c.get("name",        "logiktel_auth"),
            c.get("key",         "change-this-in-production-please"),
            int(c.get("expiry_days", 30)),
        )
    except (KeyError, FileNotFoundError):
        return ("logiktel_auth", "change-this-key", 30)


# ---------------------------------------------------------------------------
# UI de login
# ---------------------------------------------------------------------------

def require_login() -> Optional[dict]:
    """
    Muestra el login si el usuario no está autenticado.

    Retorna el dict del usuario logueado (con name, role, etc.) si la auth
    fue exitosa, o detiene la ejecución (st.stop) en caso contrario.
    """
    try:
        import streamlit_authenticator as stauth
    except ImportError:
        st.error(
            "❌ Falta el paquete `streamlit-authenticator`. "
            "Instálalo con: `pip install streamlit-authenticator`"
        )
        st.stop()

    credentials = _get_credentials_dict()

    if not credentials["usernames"]:
        st.error(
            "🔐 No hay usuarios configurados.\n\n"
            "Configura los usuarios en `.streamlit/secrets.toml` "
            "(o en el panel Secrets de Streamlit Cloud)."
        )
        st.stop()

    cookie_name, cookie_key, cookie_expiry = _get_cookie_config()

    authenticator = stauth.Authenticate(
        credentials=credentials,
        cookie_name=cookie_name,
        cookie_key=cookie_key,
        cookie_expiry_days=cookie_expiry,
    )

    # ── CSS para centrar el formulario de login ──────────────────────────
    st.markdown(
        """
        <style>
        .login-wrap {
            max-width: 420px;
            margin: 4rem auto;
            background: white;
            border-radius: 14px;
            padding: 2rem;
            box-shadow: 0 8px 28px rgba(13,51,32,0.18);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # En streamlit-authenticator >= 0.3, el método login() retorna None
    # y los valores se leen de st.session_state
    try:
        authenticator.login(location="main", fields={
            "Form name":     "🔐 Acceso al Dashboard Logístico",
            "Username":      "Usuario",
            "Password":      "Contraseña",
            "Login":         "Ingresar",
        })
    except Exception:
        # Fallback para versiones más viejas
        try:
            authenticator.login("Login", "main")
        except Exception as e:
            st.error(f"Error de autenticación: {e}")
            st.stop()

    auth_status = st.session_state.get("authentication_status")
    username    = st.session_state.get("username", "")
    name        = st.session_state.get("name", "")

    if auth_status is False:
        st.error("❌ Usuario o contraseña incorrectos.")
        st.stop()
    elif auth_status is None:
        st.warning("👋 Por favor ingresa tus credenciales.")
        st.caption(
            "💡 Si no tienes acceso, contacta al administrador del dashboard."
        )
        st.stop()

    # ── Usuario autenticado ──────────────────────────────────────────────
    user_data = credentials["usernames"].get(username, {})
    user_info = {
        "username": username,
        "name":     name or username,
        "role":     user_data.get("role", "viewer"),
        "email":    user_data.get("email", ""),
        "authenticator": authenticator,
    }
    return user_info


def logout_button(user_info: dict, location: str = "sidebar") -> None:
    """Botón de logout en sidebar o main."""
    auth = user_info.get("authenticator")
    if auth is None:
        return
    try:
        auth.logout(button_name="🚪 Cerrar sesión", location=location)
    except Exception:
        try:
            auth.logout("🚪 Cerrar sesión", location)
        except Exception:
            pass


def can_edit_overrides(user_info: dict) -> bool:
    """¿Este usuario puede crear empates/anulaciones?"""
    role = (user_info or {}).get("role", "viewer").lower()
    return role in ("admin", "operador")


def is_admin(user_info: dict) -> bool:
    return (user_info or {}).get("role", "viewer").lower() == "admin"
