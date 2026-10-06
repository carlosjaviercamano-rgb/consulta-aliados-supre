"""
Cliente de Google Sheets para el envío de facturas a aliados.
Centraliza la conexión y las operaciones sobre las hojas 'Facturas' y 'Proveedores'.

La hoja Facturas necesita una columna llamada 'estado_envio' (valores:
'por enviar' / 'enviado') para controlar qué ya se mandó por correo.
"""

import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from gspread.utils import rowcol_to_a1

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

HOJA_FACTURAS = "Facturas"
HOJA_PROVEEDORES = "Proveedores"

COLUMNA_ESTADO = "estado_envio"
ESTADO_POR_ENVIAR = "por enviar"
ESTADO_ENVIADO = "enviado"

COLUMNAS_FACTURAS = [
    "fecha_factura",
    "factura_comision",
    "cedula_cliente",
    "nombre_cliente",
    "factura_aliado",
    "nit_aliado",
    "nombre_aliado",
    "validacion",
    COLUMNA_ESTADO,
]

COLUMNAS_PROVEEDORES = ["nit", "nombre", "correo", "fecha_alta"]

# Estados posibles de un aliado en la revisión previa al envío
ESTADO_LISTO = "Listo para enviar"
ESTADO_SIN_PROVEEDOR = "Sin proveedor registrado"
ESTADO_SIN_CORREO = "Sin correo válido"


@st.cache_resource(show_spinner=False)
def get_client() -> gspread.Client:
    """Autentica contra Google usando la cuenta de servicio guardada en secrets."""
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_resource(show_spinner=False)
def get_spreadsheet():
    """Abre el Google Sheet por su ID (guardado en secrets)."""
    return get_client().open_by_key(st.secrets["google_sheet_id"])


def _worksheet(nombre_hoja: str):
    return get_spreadsheet().worksheet(nombre_hoja)


def _encabezados_con_estado(ws) -> list[str]:
    """Devuelve los encabezados de la hoja y exige que exista 'estado_envio'."""
    encabezados = [h.strip() for h in ws.row_values(1)]
    if COLUMNA_ESTADO not in encabezados:
        raise RuntimeError(
            f"Falta la columna '{COLUMNA_ESTADO}' en la hoja '{ws.title}'. "
            f"Agrégala en la fila 1 (al final de los encabezados) y vuelve a intentar."
        )
    return encabezados


# ---------- Lecturas ----------

@st.cache_data(ttl=60, show_spinner=False)
def cargar_facturas() -> pd.DataFrame:
    """Lee todas las facturas del Sheet como DataFrame."""
    registros = _worksheet(HOJA_FACTURAS).get_all_records(numericise_ignore=["all"])
    df = pd.DataFrame(registros)
    if df.empty:
        df = pd.DataFrame(columns=COLUMNAS_FACTURAS)
    if "nit_aliado" in df.columns:
        df["nit_aliado"] = df["nit_aliado"].astype(str).str.strip()
    return df


@st.cache_data(ttl=60, show_spinner=False)
def cargar_proveedores() -> pd.DataFrame:
    """Lee todos los proveedores registrados como DataFrame."""
    registros = _worksheet(HOJA_PROVEEDORES).get_all_records(numericise_ignore=["all"])
    df = pd.DataFrame(registros)
    if df.empty:
        df = pd.DataFrame(columns=COLUMNAS_PROVEEDORES)
    if "nit" in df.columns:
        df["nit"] = df["nit"].astype(str).str.strip()
    return df


def nit_existe(nit: str) -> bool:
    nit = str(nit).strip()
    df = cargar_proveedores()
    return not df[df["nit"] == nit].empty


def agregar_proveedor(nit: str, nombre: str, correo: str) -> None:
    """Agrega una nueva fila a la hoja de Proveedores."""
    from datetime import date

    ws = _worksheet(HOJA_PROVEEDORES)
    ws.append_row([str(nit).strip(), nombre.strip(), correo.strip(), date.today().isoformat()])
    cargar_proveedores.clear()


# ---------- Carga masiva del CSV diario ----------

def cargar_facturas_masivo(df_csv: pd.DataFrame) -> dict:
    """
    Procesa un CSV de facturas diarias y las agrega a la hoja Facturas
    con estado 'por enviar'.

    Reglas:
    - Filas SIN nit_aliado, o con validacion = "Validar" -> no se guardan
      (van a 'por_revisar'; muchas traen la cédula del cliente en vez del NIT).
    - Filas cuya factura_comision ya existe -> duplicado, no se recrean.
    - Filas con NIT, exista o no ese proveedor en Proveedores -> SÍ se guardan.
      Si el proveedor aún no está registrado se reporta en 'nits_no_encontrados';
      la factura queda 'por enviar' y sale cuando se registre.
    """
    ws = _worksheet(HOJA_FACTURAS)
    encabezados = _encabezados_con_estado(ws)

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

        valores = {
            "fecha_factura": str(row.get("fecha_factura", "")),
            "factura_comision": factura,
            "cedula_cliente": str(row.get("cedula_cliente", "")),
            "nombre_cliente": str(row.get("nombre_cliente", "")),
            "factura_aliado": str(row.get("factura_aliado", "")),
            "nit_aliado": nit,
            "nombre_aliado": str(row.get("nombre_aliado", "")),
            "validacion": str(row.get("validacion", "")),
            COLUMNA_ESTADO: ESTADO_POR_ENVIAR,
        }
        # Se ordena según los encabezados reales del Sheet
        filas_nuevas.append([valores.get(h, "") for h in encabezados])
        if factura:
            existentes.add(factura)

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


# ---------- Envío de correos ----------

def obtener_facturas_por_enviar() -> pd.DataFrame:
    """
    Lee el Sheet (sin caché, siempre fresco) y devuelve solo las facturas con
    estado 'por enviar', con una columna '_fila' que indica su fila en el Sheet.
    Las filas con el estado vacío (cargas anteriores a este cambio) se ignoran.
    """
    ws = _worksheet(HOJA_FACTURAS)
    _encabezados_con_estado(ws)
    df = pd.DataFrame(ws.get_all_records(numericise_ignore=["all"]))
    if df.empty:
        return pd.DataFrame(columns=COLUMNAS_FACTURAS + ["_fila"])

    df["_fila"] = df.index + 2  # fila 1 = encabezados
    df["nit_aliado"] = df["nit_aliado"].astype(str).str.strip()
    estado = df[COLUMNA_ESTADO].astype(str).str.strip().str.lower()
    return df[estado == ESTADO_POR_ENVIAR].copy()


def preparar_envios(pendientes: pd.DataFrame, proveedores: pd.DataFrame) -> list[dict]:
    """
    Agrupa las facturas por enviar por NIT y determina, para cada aliado,
    si se puede enviar (proveedor registrado y con correo válido).
    """
    prov_por_nit = {str(r["nit"]).strip(): r for _, r in proveedores.iterrows()}

    envios = []
    for nit, grupo in pendientes.groupby("nit_aliado"):
        prov = prov_por_nit.get(nit)
        if prov is None:
            nombre = str(grupo["nombre_aliado"].iloc[0])
            correo = ""
            estado = ESTADO_SIN_PROVEEDOR
        else:
            nombre = str(prov["nombre"])
            correo = str(prov["correo"]).strip()
            estado = ESTADO_LISTO if "@" in correo else ESTADO_SIN_CORREO
        envios.append({
            "nit": nit,
            "nombre": nombre,
            "correo": correo,
            "facturas": grupo,
            "estado": estado,
        })

    return sorted(envios, key=lambda e: e["nombre"].lower())


def marcar_enviadas(filas: list[int]) -> None:
    """Pone estado 'enviado' en las filas indicadas, en una sola llamada."""
    if not filas:
        return
    ws = _worksheet(HOJA_FACTURAS)
    col = _encabezados_con_estado(ws).index(COLUMNA_ESTADO) + 1
    ws.batch_update([
        {"range": rowcol_to_a1(int(f), col), "values": [[ESTADO_ENVIADO]]}
        for f in filas
    ])
    cargar_facturas.clear()
