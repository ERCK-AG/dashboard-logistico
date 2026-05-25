"""
generate_password_hashes.py — Genera hashes bcrypt para tus usuarios.

USO:
    1. Edita la lista USERS abajo con tus contraseñas reales
    2. Ejecuta:  python generate_password_hashes.py
    3. Copia la salida a tu archivo `.streamlit/secrets.toml`
       o al panel "Secrets" de Streamlit Community Cloud
"""

# ⚠️ EDITA AQUÍ las contraseñas reales antes de ejecutar el script
USERS = [
    # (username, password, full_name, role, email)
    ("admin",    "admin123",   "Erick Aguirre",        "admin",    "erick@businesspoint.com"),
    ("operador", "oper123",    "Operador Logístico",   "operador", ""),
    ("consulta", "consul123",  "Usuario Consulta",     "viewer",   ""),
]


def main():
    try:
        import bcrypt
    except ImportError:
        print("❌ Falta el paquete `bcrypt`. Instálalo con:")
        print("   pip install bcrypt")
        return

    print()
    print("=" * 70)
    print("📋 Copia este bloque completo en tu archivo `.streamlit/secrets.toml`")
    print("   (o en el panel Secrets de Streamlit Community Cloud)")
    print("=" * 70)
    print()

    # Cookie config
    import secrets
    cookie_key = secrets.token_urlsafe(32)

    print(f"""[auth.cookie]
name        = "logiktel_auth"
key         = "{cookie_key}"
expiry_days = 30

[auth.credentials.usernames]
""")

    for username, password, full_name, role, email in USERS:
        # Generar hash bcrypt
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        print(f'[auth.credentials.usernames.{username}]')
        print(f'name     = "{full_name}"')
        print(f'email    = "{email}"')
        print(f'role     = "{role}"')
        print(f'password = "{hashed}"')
        print()

    print("=" * 70)
    print("✅ Listo. Recuerda:")
    print("   • Cambia las contraseñas en USERS antes de usar en producción")
    print("   • NO subas el archivo secrets.toml a GitHub (está en .gitignore)")
    print("   • Para Streamlit Cloud: pega este bloque en el panel Secrets")
    print("=" * 70)


if __name__ == "__main__":
    main()
