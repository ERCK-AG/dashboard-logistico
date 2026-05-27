"""
user_store.py — Lectura y escritura de usuarios en users.json.

Modo automático (cloud):
    Si hay un GitHub Personal Access Token en st.secrets["github"]["token"],
    los cambios se commitean directamente al repositorio via GitHub Contents API.
    Streamlit Cloud detecta el commit y redespliega la app (~1 min).

Modo manual (local / sin PAT):
    Solo se modifica el archivo users.json en disco. Para que persista en cloud
    hay que commitearlo manualmente con git push.

Fallback de lectura:
    Si users.json no existe, lee desde st.secrets["auth"]["credentials"]["usernames"]
    (backwards compat con la configuración inicial via Secrets).
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Optional

import streamlit as st


USERS_FILE = Path(__file__).parent.parent / "users.json"
REMOTE_FILE_PATH = "users.json"   # ruta dentro del repo de GitHub


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------

def _load_from_file() -> dict:
    """Lee users.json local. Retorna {} si no existe o está corrupto."""
    if not USERS_FILE.exists():
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("users", {})
    except Exception:
        return {}


def _load_from_secrets() -> dict:
    """Fallback: lee usuarios desde st.secrets (config inicial)."""
    try:
        users_secret = st.secrets["auth"]["credentials"]["usernames"]
        return {
            u: {
                "name":     data.get("name", u),
                "email":    data.get("email", ""),
                "role":     data.get("role", "viewer"),
                "password": data.get("password", ""),
            }
            for u, data in users_secret.items()
        }
    except (KeyError, FileNotFoundError):
        return {}


def get_all_users() -> dict:
    """
    Retorna todos los usuarios. Prioridad:
      1. users.json local (siempre actualizado tras un commit + redeploy)
      2. st.secrets (fallback)
    """
    users = _load_from_file()
    if users:
        return users
    return _load_from_secrets()


# ---------------------------------------------------------------------------
# GitHub Contents API
# ---------------------------------------------------------------------------

def _get_github_config() -> Optional[dict]:
    """Lee la config de GitHub desde st.secrets. Retorna None si no está completa."""
    try:
        gh = st.secrets["github"]
        token  = gh["token"]
        owner  = gh["owner"]
        repo   = gh["repo"]
        branch = gh.get("branch", "main")
    except (KeyError, FileNotFoundError):
        return None
    if not (token and owner and repo):
        return None
    return {"token": token, "owner": owner, "repo": repo, "branch": branch}


def is_github_configured() -> bool:
    """¿Está configurado el auto-commit a GitHub?"""
    return _get_github_config() is not None


# ---------------------------------------------------------------------------
# Funciones públicas para que OTROS módulos (overrides) usen GitHub
# ---------------------------------------------------------------------------

def github_commit_binary(path: str, content_bytes: bytes,
                         commit_msg: str) -> tuple[bool, str]:
    """
    Commitea un archivo binario (como xlsx) al repo de GitHub.
    Retorna (success, message).
    """
    import requests
    cfg = _get_github_config()
    if cfg is None:
        return False, "GitHub no configurado"

    try:
        # Obtener sha si el archivo existe
        url = (f"https://api.github.com/repos/{cfg['owner']}/{cfg['repo']}"
               f"/contents/{path}")
        params = {"ref": cfg["branch"]}
        resp = requests.get(url, headers=_gh_headers(cfg["token"]),
                            params=params, timeout=20)
        sha = resp.json().get("sha") if resp.status_code == 200 else None

        # PUT con contenido base64
        body = {
            "message": commit_msg,
            "content": base64.b64encode(content_bytes).decode("utf-8"),
            "branch":  cfg["branch"],
        }
        if sha:
            body["sha"] = sha
        resp = requests.put(url, headers=_gh_headers(cfg["token"]),
                            json=body, timeout=30)
        resp.raise_for_status()
        return True, "OK"
    except Exception as e:
        return False, f"Error commit binario: {e}"


def github_download_binary(path: str) -> Optional[bytes]:
    """Descarga un archivo binario desde el repo de GitHub. Retorna bytes o None."""
    import requests
    cfg = _get_github_config()
    if cfg is None:
        return None
    try:
        url = (f"https://api.github.com/repos/{cfg['owner']}/{cfg['repo']}"
               f"/contents/{path}")
        params = {"ref": cfg["branch"]}
        resp = requests.get(url, headers=_gh_headers(cfg["token"]),
                            params=params, timeout=20)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        content_b64 = resp.json().get("content", "")
        return base64.b64decode(content_b64)
    except Exception:
        return None


def _gh_headers(token: str) -> dict:
    return {
        "Authorization": f"token {token}",
        "Accept":        "application/vnd.github.v3+json",
        "User-Agent":    "dashboard-logistico-user-store",
    }


def _gh_get_file(cfg: dict, path: str) -> tuple[Optional[str], Optional[str]]:
    """Retorna (content_str, sha) o (None, None) si no existe."""
    import requests
    url = f"https://api.github.com/repos/{cfg['owner']}/{cfg['repo']}/contents/{path}"
    params = {"ref": cfg["branch"]}
    resp = requests.get(url, headers=_gh_headers(cfg["token"]),
                        params=params, timeout=20)
    if resp.status_code == 404:
        return None, None
    resp.raise_for_status()
    data = resp.json()
    content = base64.b64decode(data["content"]).decode("utf-8")
    return content, data["sha"]


def _gh_put_file(cfg: dict, path: str, content: str,
                 commit_msg: str, sha: Optional[str] = None) -> dict:
    """Commitea (crea o actualiza) un archivo. Retorna la respuesta de GitHub."""
    import requests
    url = f"https://api.github.com/repos/{cfg['owner']}/{cfg['repo']}/contents/{path}"
    body = {
        "message": commit_msg,
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
        "branch":  cfg["branch"],
    }
    if sha:
        body["sha"] = sha
    resp = requests.put(url, headers=_gh_headers(cfg["token"]),
                        json=body, timeout=20)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Operaciones públicas (add / update / remove)
# ---------------------------------------------------------------------------

def _save_to_github(users: dict, commit_msg: str) -> tuple[bool, str]:
    """Guarda el dict completo de usuarios al repo via API."""
    cfg = _get_github_config()
    if cfg is None:
        return False, "GitHub no configurado"

    try:
        content = json.dumps({"users": users}, indent=2, ensure_ascii=False)
        _existing, sha = _gh_get_file(cfg, REMOTE_FILE_PATH)
        _gh_put_file(cfg, REMOTE_FILE_PATH, content, commit_msg, sha=sha)
        # También guardar localmente para que esté disponible inmediatamente
        # (Streamlit Cloud lo sobreescribirá tras el redeploy)
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        return True, "OK"
    except Exception as e:
        return False, f"Error al commitear a GitHub: {e}"


def add_or_update_user(username: str, name: str, email: str,
                       role: str, hashed_password: str) -> tuple[bool, str]:
    """
    Agrega o actualiza un usuario.
    Returns (success, message).
    """
    users = get_all_users()
    is_update = username in users
    users[username] = {
        "name":     name,
        "email":    email,
        "role":     role,
        "password": hashed_password,
    }

    if not is_github_configured():
        # Solo guardar localmente
        try:
            content = json.dumps({"users": users}, indent=2, ensure_ascii=False)
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                f.write(content)
            return False, (
                "⚠️ Usuario guardado solo localmente. "
                "Configura GitHub PAT en Secrets para auto-commit a la nube."
            )
        except Exception as e:
            return False, f"Error al guardar local: {e}"

    action = "Actualizar" if is_update else "Crear"
    ok, msg = _save_to_github(users, f"{action} usuario: {username}")
    if ok:
        return True, (
            f"✅ Usuario `{username}` "
            f"{'actualizado' if is_update else 'creado'} en GitHub. "
            "La app se redesplegará en ~1 minuto."
        )
    return False, msg


def remove_user(username: str) -> tuple[bool, str]:
    """Elimina un usuario."""
    users = get_all_users()
    if username not in users:
        return False, f"Usuario `{username}` no encontrado."

    del users[username]

    if not is_github_configured():
        try:
            content = json.dumps({"users": users}, indent=2, ensure_ascii=False)
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                f.write(content)
            return False, (
                "⚠️ Usuario eliminado solo localmente. "
                "Configura GitHub PAT en Secrets para auto-commit a la nube."
            )
        except Exception as e:
            return False, f"Error al guardar local: {e}"

    ok, msg = _save_to_github(users, f"Eliminar usuario: {username}")
    if ok:
        return True, (
            f"✅ Usuario `{username}` eliminado de GitHub. "
            "La app se redesplegará en ~1 minuto."
        )
    return False, msg
