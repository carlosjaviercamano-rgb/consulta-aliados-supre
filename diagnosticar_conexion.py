"""
Diagnóstico de conexión a Google Sheets.
Muestra el mensaje de error REAL de Google (gspread a veces lo oculta
detrás de un PermissionError genérico).

Uso: python diagnosticar_conexion.py
"""

import toml
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

data = toml.load(".streamlit/secrets.toml")
sheet_id = data["google_sheet_id"]
creds_dict = data["gcp_service_account"]

print(f"Usando cuenta de servicio: {creds_dict['client_email']}")
print(f"Proyecto: {creds_dict['project_id']}")
print(f"Intentando abrir Sheet ID: {sheet_id}\n")

creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)

try:
    ss = client.open_by_key(sheet_id)
    print("✅ ¡CONEXIÓN EXITOSA!")
    print(f"Nombre del Sheet: {ss.title}")
    print(f"Pestañas encontradas: {[ws.title for ws in ss.worksheets()]}")
except gspread.exceptions.APIError as e:
    print("❌ ERROR DE LA API DE GOOGLE (mensaje real):")
    print(e.response.text)
except Exception as e:
    print(f"❌ ERROR: {type(e).__name__}: {e}")
    causa = e.__cause__
    if causa is not None:
        print(f"\n--- Causa original (el error real de Google) ---")
        print(f"Tipo: {type(causa).__name__}")
        print(f"Detalle: {causa}")
        # Si la causa tiene una respuesta HTTP, la mostramos completa
        if hasattr(causa, "response") and causa.response is not None:
            print(f"\n--- Respuesta HTTP completa ---")
            print(f"Status code: {causa.response.status_code}")
            print(causa.response.text)