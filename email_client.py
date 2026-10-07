"""
Envío de facturas a los aliados por correo (Gmail SMTP, cuenta institucional).
Cada aliado recibe un Excel adjunto con sus facturas, con copia a los
correos configurados en secrets (cc_emails).
"""

import html
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
    nombre = str(envio["nombre"]).strip()
    nit = envio["nit"]

    fechas = pd.to_datetime(facturas["fecha_factura"], errors="coerce").dropna()
    if not fechas.empty:
        periodo = f"{fechas.min():%d/%m/%Y} al {fechas.max():%d/%m/%Y}"
    else:
        periodo = "No disponible"

    hoy = date.today()
    total = len(facturas)
    nombre_archivo = f"facturas_{nit}_{hoy:%Y%m%d}.xlsx"

    msg = EmailMessage()
    msg["Subject"] = f"Suprecredito | Relación de facturas de comisión | NIT {nit} | {hoy:%d/%m/%Y}"
    msg["From"] = f"Suprecredito <{remitente}>"
    msg["To"] = envio["correo"]
    if cc:
        msg["Cc"] = ", ".join(cc)

    # Versión de texto plano (respaldo)
    msg.set_content(
        f"Estimado aliado {nombre}:\n\n"
        f"Reciba un cordial saludo de parte de Suprecredito.\n\n"
        f"Adjuntamos la relación de las facturas de comisión asociadas a su NIT {nit}, "
        f"para su revisión y control.\n\n"
        f"  - Número de facturas: {total}\n"
        f"  - Periodo de las facturas: {periodo}\n"
        f"  - Archivo adjunto: {nombre_archivo}\n\n"
        f"Si encuentra alguna diferencia o requiere una aclaración sobre la información, "
        f"le agradecemos comunicarse con nosotros respondiendo a este mensaje.\n\n"
        f"Cordialmente,\n\n"
        f"Equipo Contable\n"
        f"Suprecredito SAS\n"
    )

    # Versión HTML
    nombre_h = html.escape(nombre)
    html_cuerpo = f"""\
<html>
  <body style="margin:0; padding:0; background-color:#f4f6f8;">
    <div style="max-width:620px; margin:0 auto; padding:24px; font-family:Arial, Helvetica, sans-serif; color:#1f2937; font-size:14px; line-height:1.6;">
      <div style="background-color:#ffffff; border:1px solid #e5e7eb; border-radius:8px; overflow:hidden;">
        <div style="background-color:#1e3a5f; color:#ffffff; padding:16px 24px; font-size:16px; font-weight:bold;">
          Suprecredito
        </div>
        <div style="padding:24px;">
          <p style="margin:0 0 14px 0;">Estimado aliado <strong>{nombre_h}</strong>:</p>
          <p style="margin:0 0 14px 0;">Reciba un cordial saludo de parte de Suprecredito.</p>
          <p style="margin:0 0 14px 0;">
            Adjuntamos la relación de las facturas de comisión asociadas a su NIT
            <strong>{html.escape(str(nit))}</strong>, para su revisión y control.
          </p>
          <table style="border-collapse:collapse; margin:0 0 18px 0; width:100%;">
            <tr>
              <td style="padding:8px 12px; background-color:#f1f5f9; border:1px solid #e5e7eb; width:45%;"><strong>Número de facturas</strong></td>
              <td style="padding:8px 12px; border:1px solid #e5e7eb;">{total}</td>
            </tr>
            <tr>
              <td style="padding:8px 12px; background-color:#f1f5f9; border:1px solid #e5e7eb;"><strong>Periodo de las facturas</strong></td>
              <td style="padding:8px 12px; border:1px solid #e5e7eb;">{html.escape(periodo)}</td>
            </tr>
            <tr>
              <td style="padding:8px 12px; background-color:#f1f5f9; border:1px solid #e5e7eb;"><strong>Archivo adjunto</strong></td>
              <td style="padding:8px 12px; border:1px solid #e5e7eb;">{html.escape(nombre_archivo)}</td>
            </tr>
          </table>
          <p style="margin:0 0 14px 0;">
            Si encuentra alguna diferencia o requiere una aclaración sobre la información,
            le agradecemos comunicarse con nosotros respondiendo a este mensaje.
          </p>
          <p style="margin:24px 0 0 0;">Cordialmente,</p>
          <p style="margin:12px 0 0 0;">
            <strong>Equipo Contable</strong><br>
            Suprecredito SAS
          </p>
        </div>
      </div>
    </div>
  </body>
</html>
"""
    msg.add_alternative(html_cuerpo, subtype="html")

    msg.add_attachment(
        _excel_bytes(facturas),
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=nombre_archivo,
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