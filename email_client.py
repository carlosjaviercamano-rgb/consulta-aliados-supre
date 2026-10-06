"""
Envío de facturas a los aliados por correo (Gmail SMTP, cuenta institucional).
Cada aliado recibe un Excel adjunto con sus facturas, con copia a los
correos configurados en secrets (cc_emails).
"""

import io
import smtplib
import ssl
from datetime import date
from email.message import EmailMessage

import pandas as pd
import streamlit as st
from openpyxl.utils import get_column_letter

COLUMNAS_EXCEL = {
    "fecha_factura": "Fecha Factura",
    "factura_comision": "Factura Comisión",
    "cedula_cliente": "Cédula Cliente",
    "nombre_cliente": "Nombre Cliente",
    "factura_aliado": "Factura Aliado",
    "nit_aliado": "NIT Aliado",
    "nombre_aliado": "Nombre Aliado",
}


def _excel_bytes(facturas: pd.DataFrame) -> bytes:
    """Arma el Excel del aliado (sin columnas internas como validacion o estado)."""
    df = facturas[list(COLUMNAS_EXCEL)].rename(columns=COLUMNAS_EXCEL)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Facturas")
        hoja = writer.sheets["Facturas"]
        for i, col in enumerate(df.columns, start=1):
            ancho = max(len(str(col)), int(df[col].astype(str).str.len().max())) + 2
            hoja.column_dimensions[get_column_letter(i)].width = min(ancho, 45)
    return buffer.getvalue()


def _armar_mensaje(remitente: str, cc: list[str], envio: dict) -> EmailMessage:
    facturas = envio["facturas"]
    fechas = pd.to_datetime(facturas["fecha_factura"], errors="coerce").dropna()
    if not fechas.empty:
        periodo = f"del {fechas.min():%d-%m-%Y} al {fechas.max():%d-%m-%Y}"
    else:
        periodo = ""

    hoy = date.today()
    msg = EmailMessage()
    msg["Subject"] = f"Relación de facturas de comisión - {hoy:%d-%m-%Y}"
    msg["From"] = remitente
    msg["To"] = envio["correo"]
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg.set_content(
        f"Hola {envio['nombre']},\n\n"
        f"Adjuntamos la relación de facturas de comisión asociadas al NIT {envio['nit']}.\n"
        f"Total de facturas: {len(facturas)}"
        f"{' (' + periodo + ')' if periodo else ''}.\n\n"
        f"Si tiene alguna inquietud, puede responder este correo.\n\n"
        f"Saludos,\nEquipo Suprecredito\n"
    )
    msg.add_attachment(
        _excel_bytes(facturas),
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"facturas_{envio['nit']}_{hoy:%Y%m%d}.xlsx",
    )
    return msg


def enviar_correos_facturas(envios: list[dict]) -> dict:
    """
    Envía un correo por aliado, reutilizando una sola conexión a Gmail.
    Devuelve {nit: (ok, mensaje_de_error)} para cada envío.
    """
    try:
        remitente = st.secrets["gmail_address"]
        clave_app = st.secrets["gmail_app_password"]
        cc = list(st.secrets.get("cc_emails", []))
    except KeyError as e:
        return {env["nit"]: (False, f"Falta configurar {e} en secrets") for env in envios}

    resultados: dict = {}
    try:
        contexto = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=contexto) as server:
            server.login(remitente, clave_app)
            for envio in envios:
                try:
                    server.send_message(_armar_mensaje(remitente, cc, envio))
                    resultados[envio["nit"]] = (True, "")
                except Exception as e:
                    resultados[envio["nit"]] = (False, str(e))
    except Exception as e:
        # Falla de conexión o login: los que no alcanzaron a salir quedan como fallidos
        for envio in envios:
            resultados.setdefault(envio["nit"], (False, str(e)))
    return resultados
