"""
Script de validación local para secrets.toml.
Corre esto ANTES de probar la app, para confirmar que la clave privada
quedó bien copiada, sin necesidad de compartirla con nadie.

Uso (desde la carpeta del proyecto, con el venv activado):
    python validar_secrets.py
"""

import sys

try:
    import toml
except ImportError:
    print("Instalando dependencia necesaria (toml)...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "toml", "--quiet"])
    import toml

try:
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
except ImportError:
    print("Instalando dependencia necesaria (cryptography)...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "cryptography", "--quiet"])
    from cryptography.hazmat.primitives.serialization import load_pem_private_key


def main():
    ruta = ".streamlit/secrets.toml"
    try:
        data = toml.load(ruta)
    except FileNotFoundError:
        print(f"❌ No se encontró el archivo {ruta}. Corre este script desde la raíz del proyecto.")
        return
    except Exception as e:
        print(f"❌ El archivo TOML tiene un error de formato: {e}")
        return

    print("✅ El archivo secrets.toml se pudo leer correctamente (formato TOML válido).\n")

    campos_top = ["google_sheet_id", "admin_password"]
    for campo in campos_top:
        if campo in data:
            print(f"✅ Campo '{campo}' presente.")
        else:
            print(f"⚠️  Falta el campo '{campo}'.")

    if "gcp_service_account" not in data:
        print("❌ Falta toda la sección [gcp_service_account].")
        return

    gcp = data["gcp_service_account"]
    campos_gcp = [
        "type", "project_id", "private_key_id", "private_key",
        "client_email", "client_id", "auth_uri", "token_uri",
        "auth_provider_x509_cert_url", "client_x509_cert_url",
    ]
    for campo in campos_gcp:
        if campo in gcp and gcp[campo]:
            print(f"✅ gcp_service_account.{campo} presente.")
        else:
            print(f"❌ Falta o está vacío: gcp_service_account.{campo}")

    print("\n--- Validando la clave privada (private_key) ---")
    private_key = gcp.get("private_key", "")
    try:
        load_pem_private_key(private_key.encode(), password=None)
        print("✅ ¡La clave privada es VÁLIDA! Está bien formada y lista para usarse.")
    except Exception as e:
        print(f"❌ La clave privada está CORRUPTA o mal formateada. Detalle técnico: {e}")
        print("   Vuelve a copiarla desde el archivo .json original, sin editar ningún carácter.")

    print("\n--- Otros campos ---")
    for campo in ["gmail_address", "gmail_app_password", "portal_url"]:
        if campo in data and data[campo]:
            print(f"✅ Campo '{campo}' presente.")
        else:
            print(f"⚠️  Falta el campo '{campo}' (necesario para el correo automático).")


if __name__ == "__main__":
    main()
