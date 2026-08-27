"""
Cliente de Google Sheets para Consulta Aliados Supre.
Centraliza la conexión y las operaciones de lectura/escritura sobre
las hojas 'Facturas' y 'Proveedores'.
"""

import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Nombres de las pestañas dentro del Google Sheet
HOJA_FACTURAS = "Facturas"
HOJA_PROVEEDORES = "Proveedores"

# Columnas esperadas (deben coincidir con los encabezados reales del Sheet)
COLUMNAS_FACTURAS = [
    "fecha_factura",
    "factura_comision",
    "cedula_cliente",
    "nombre_cliente",
    "factura_aliado",
    "nit_aliado",
    "nombre_aliado",
    "validacion",
]

COLUMNAS_PROVEEDORES = ["nit", "nombre", "correo", "fecha_alta"]


@st.cache_resource(show_spinner=False)
def get_client() -> gspread.Client:
    """Autentica contra Google usando la cuenta de servicio guardada en secrets."""
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_resource(show_spinner=False)
def get_spreadsheet():
    """Abre el Google Sheet por su ID (guardado en secrets)."""
    client = get_client()
    sheet_id = st.secrets["google_sheet_id"]
    return client.open_by_key(sheet_id)


def _worksheet(nombre_hoja: str):
    ss = get_spreadsheet()
    return ss.worksheet(nombre_hoja)


@st.cache_data(ttl=60, show_spinner=False)
def cargar_facturas() -> pd.DataFrame:
    """Lee todas las facturas del Sheet como DataFrame."""
    ws = _worksheet(HOJA_FACTURAS)
    registros = ws.get_all_records()
    df = pd.DataFrame(registros)
    if df.empty:
        df = pd.DataFrame(columns=COLUMNAS_FACTURAS)
    # Normaliza el NIT a texto sin espacios, para que el filtro por login sea exacto
    if "nit_aliado" in df.columns:
        df["nit_aliado"] = df["nit_aliado"].astype(str).str.strip()
    return df


@st.cache_data(ttl=60, show_spinner=False)
def cargar_proveedores() -> pd.DataFrame:
    """Lee todos los proveedores registrados como DataFrame."""
    ws = _worksheet(HOJA_PROVEEDORES)
    registros = ws.get_all_records()
    df = pd.DataFrame(registros)
    if df.empty:
        df = pd.DataFrame(columns=COLUMNAS_PROVEEDORES)
    if "nit" in df.columns:
        df["nit"] = df["nit"].astype(str).str.strip()
    return df


def validar_login(nit: str) -> dict | None:
    """
    Valida el login del proveedor. Usuario y contraseña son ambos el NIT.
    Devuelve los datos del proveedor si el NIT existe, o None si no.
    """
    nit = str(nit).strip()
    df = cargar_proveedores()
    coincidencia = df[df["nit"] == nit]
    if coincidencia.empty:
        return None
    return coincidencia.iloc[0].to_dict()


def facturas_por_nit(nit: str) -> pd.DataFrame:
    """Filtra las facturas correspondientes a un NIT específico."""
    nit = str(nit).strip()
    df = cargar_facturas()
    return df[df["nit_aliado"] == nit].copy()


def nit_existe(nit: str) -> bool:
    nit = str(nit).strip()
    df = cargar_proveedores()
    return not df[df["nit"] == nit].empty


def agregar_proveedor(nit: str, nombre: str, correo: str) -> None:
    """Agrega una nueva fila a la hoja de Proveedores."""
    from datetime import date

    ws = _worksheet(HOJA_PROVEEDORES)
    ws.append_row([str(nit).strip(), nombre.strip(), correo.strip(), date.today().isoformat()])
    # Limpia la caché para que el nuevo proveedor se vea de inmediato
    cargar_proveedores.clear()


def cargar_facturas_masivo(df_csv: pd.DataFrame) -> dict:
    """
    Procesa un CSV de facturas diarias y las agrega a la hoja Facturas.

    Reglas:
    - Filas SIN nit_aliado -> no se guardan (no hay con qué asociarlas).
    - Filas con validacion = "Validar" -> tampoco se guardan, sin importar si
      traen NIT o no. Muchas de estas traen por error la cédula del cliente
      en el campo de NIT, así que guardarlas contaminaría los datos.
    - Ambos casos anteriores van a 'por_revisar' para que se revisen y,
      si corresponde, se corrijan y se vuelvan a subir.
    - Filas cuya factura_comision ya existe -> se cuentan como duplicado, no se recrean.
    - El resto (con NIT, sin "Validar") SÍ se guarda, exista o no ese proveedor
      en Proveedores. Si el NIT aún no está registrado, se reporta aparte en
      'nits_no_encontrados' solo de forma informativa, pero la factura ya
      queda en el Sheet y aparecerá sola en cuanto el proveedor se registre.
    """
    ws = _worksheet(HOJA_FACTURAS)

    existentes = set(cargar_facturas().get("factura_comision", pd.Series(dtype=str)).astype(str))
    nits_validos = set(cargar_proveedores().get("nit", pd.Series(dtype=str)).astype(str))

    filas_nuevas = []
    filas_por_revisar = []
    filas_nit_no_encontrado = []
    duplicados = 0

    for _, row in df_csv.iterrows():
        nit = str(row.get("nit_aliado", "")).strip()
        factura = str(row.get("factura_comision", "")).strip()
        validacion = str(row.get("validacion", "")).strip().lower()

        if not nit or validacion == "validar":
            filas_por_revisar.append(row.to_dict())
            continue

        if factura and factura in existentes:
            duplicados += 1
            continue

        if nit not in nits_validos:
            filas_nit_no_encontrado.append(row.to_dict())
            # No hacemos "continue": esta fila SÍ se guarda igual, solo se reporta.

        filas_nuevas.append([
            str(row.get("fecha_factura", "")),
            factura,
            str(row.get("cedula_cliente", "")),
            str(row.get("nombre_cliente", "")),
            str(row.get("factura_aliado", "")),
            nit,
            str(row.get("nombre_aliado", "")),
            str(row.get("validacion", "")),
        ])
        if factura:
            existentes.add(factura)  # evita duplicados dentro del mismo archivo

    if filas_nuevas:
        ws.append_rows(filas_nuevas, value_input_option="USER_ENTERED")
        cargar_facturas.clear()

    return {
        "total": len(df_csv),
        "cargadas": len(filas_nuevas),
        "duplicados": duplicados,
        "por_revisar": pd.DataFrame(filas_por_revisar),
        "nits_no_encontrados": pd.DataFrame(filas_nit_no_encontrado),
    }


def obtener_pendientes_actuales() -> dict:
    """
    Revisa TODAS las facturas que hay hasta ahora en el Sheet (acumulado
    histórico, no solo la última carga) y devuelve las que están sin NIT
    o con un NIT que todavía no está registrado en Proveedores.
    """
    df = cargar_facturas()
    nits_validos = set(cargar_proveedores().get("nit", pd.Series(dtype=str)).astype(str))

    if df.empty:
        vacio = pd.DataFrame(columns=COLUMNAS_FACTURAS)
        return {"por_revisar": vacio, "nits_no_encontrados": vacio}

    sin_nit = df[df["nit_aliado"].astype(str).str.strip() == ""]
    con_nit_no_valido = df[
        (df["nit_aliado"].astype(str).str.strip() != "")
        & (~df["nit_aliado"].astype(str).str.strip().isin(nits_validos))
    ]

    return {
        "por_revisar": sin_nit,
        "nits_no_encontrados": con_nit_no_valido,
    }