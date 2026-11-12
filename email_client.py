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

# Correo al que los destinatarios deben escribir para cualquier aclaración.
# Cada tipo de correo tiene el suyo: cámbialo aquí si necesitas otro.
CORREO_CONTACTO_FACTURAS = "otapia@supre.com.co"   # correo a los aliados (facturas)
CORREO_CONTACTO_SOPORTES = "ccamano@supre.com.co"   # correo a los particulares (soportes)

COLUMNAS_EXCEL = {
    "fecha_factura": "Fecha Factura",
    "factura_comision": "Factura Comisión",
    "cedula_cliente": "Cédula Cliente",
    "nombre_cliente": "Nombre Cliente",
    "factura_aliado": "Factura Aliado",
    "nit_aliado": "NIT Aliado",
    "nombre_aliado": "Nombre Aliado",
}


def limpiar_factura_aliado(factura: str, cedula: str) -> str:
    """
    Quita del número de factura del aliado la cédula/NIT del cliente que viene
    pegada al final (ej. 'FEV-12148-1000397021' -> 'FEV-12148').

    1) Si termina en '-' + cedula_cliente, se quita exactamente eso.
    2) Respaldo: si el último tramo tras el guion son 7 o más dígitos
       (parece una cédula), también se quita.
    Un número corto al final (ej. 'FEV-12148') no se toca.
    """
    factura = str(factura).strip()
    cedula = str(cedula).strip()

    if cedula and factura.endswith("-" + cedula):
        return factura[: -(len(cedula) + 1)]

    inicio, _, ultimo = factura.rpartition("-")
    if inicio and ultimo.isdigit() and len(ultimo) >= 7:
        return inicio

    return factura


def _excel_bytes(facturas: pd.DataFrame) -> bytes:
    """Arma el Excel del aliado (sin columnas internas como validacion o estado)."""
    df = facturas[list(COLUMNAS_EXCEL)].copy()
    df["factura_aliado"] = [
        limpiar_factura_aliado(f, c)
        for f, c in zip(df["factura_aliado"], df["cedula_cliente"])
    ]
    df = df.rename(columns=COLUMNAS_EXCEL)
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
        f"le agradecemos comunicarse con nosotros a través del correo {CORREO_CONTACTO_FACTURAS}.\n\n"
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
            le agradecemos comunicarse con nosotros a través del correo
            <a href="mailto:{CORREO_CONTACTO_FACTURAS}" style="color:#1e3a5f;">{CORREO_CONTACTO_FACTURAS}</a>.
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


# ---------- Soportes de pago a particulares ----------

# Gmail admite ~25 MB por correo y los adjuntos crecen ~33% al codificarse,
# así que se deja un margen: máximo ~18 MB de PDF por correo.
LIMITE_BYTES_ADJUNTOS = 18 * 1024 * 1024


MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def _frase_meses(archivos: list[dict]) -> str:
    """
    Frase con el/los mes(es) de los soportes, lista para insertar en el correo:
    ' correspondientes al mes de octubre' / ' correspondientes a los meses de
    enero y febrero'. Si los archivos no traen mes, devuelve ''.
    """
    meses = sorted({a["mes"] for a in archivos if a.get("mes") in MESES_ES})
    nombres = [MESES_ES[m].lower() for m in meses]
    if not nombres:
        return ""
    if len(nombres) == 1:
        return f" correspondientes al mes de {nombres[0]}"
    return " correspondientes a los meses de " + ", ".join(nombres[:-1]) + " y " + nombres[-1]


def _armar_mensaje_soporte(remitente: str, cc: list[str], envio: dict) -> EmailMessage:
    nombre = str(envio["nombre"]).strip()
    identificacion = str(envio["identificacion"]).strip()
    archivos = envio["archivos"]  # lista de {"nombre": str, "bytes": bytes}
    total = len(archivos)
    hoy = date.today()

    msg = EmailMessage()
    msg["Subject"] = f"Suprecredito | Soporte de pago de intereses | {hoy:%d/%m/%Y}"
    msg["From"] = f"Suprecredito <{remitente}>"
    msg["To"] = envio["correo"]
    if cc:
        msg["Cc"] = ", ".join(cc)

    soporte = "el soporte" if total == 1 else "los soportes"
    frase_meses = _frase_meses(archivos)
    lista_txt = "\n".join(f"  - {a['nombre']}" for a in archivos)
    msg.set_content(
        f"Estimado(a) {nombre}:\n\n"
        f"Reciba un cordial saludo de parte de Suprecredito.\n\n"
        f"Adjuntamos {soporte} de pago de los intereses cancelados{frase_meses}, "
        f"para su conocimiento y control.\n\n"
        f"  - Identificación: {identificacion}\n"
        f"  - Número de soportes adjuntos: {total}\n\n"
        f"Archivos adjuntos:\n{lista_txt}\n\n"
        f"Si requiere alguna aclaración sobre la información, "
        f"le agradecemos comunicarse con nosotros a través del correo {CORREO_CONTACTO_SOPORTES}.\n\n"
        f"Cordialmente,\n\n"
        f"Equipo Contable\n"
        f"Suprecredito SAS\n"
    )

    lista_html = "".join(
        f'<li style="margin:2px 0;">{html.escape(a["nombre"])}</li>' for a in archivos
    )
    html_cuerpo = f"""\
<html>
  <body style="margin:0; padding:0; background-color:#f4f6f8;">
    <div style="max-width:620px; margin:0 auto; padding:24px; font-family:Arial, Helvetica, sans-serif; color:#1f2937; font-size:14px; line-height:1.6;">
      <div style="background-color:#ffffff; border:1px solid #e5e7eb; border-radius:8px; overflow:hidden;">
        <div style="background-color:#1e3a5f; color:#ffffff; padding:16px 24px; font-size:16px; font-weight:bold;">
          Suprecredito
        </div>
        <div style="padding:24px;">
          <p style="margin:0 0 14px 0;">Estimado(a) <strong>{html.escape(nombre)}</strong>:</p>
          <p style="margin:0 0 14px 0;">Reciba un cordial saludo de parte de Suprecredito.</p>
          <p style="margin:0 0 14px 0;">
            Adjuntamos {soporte} de pago de los intereses cancelados{frase_meses}, para su conocimiento y control.
          </p>
          <table style="border-collapse:collapse; margin:0 0 18px 0; width:100%;">
            <tr>
              <td style="padding:8px 12px; background-color:#f1f5f9; border:1px solid #e5e7eb; width:45%;"><strong>Identificación</strong></td>
              <td style="padding:8px 12px; border:1px solid #e5e7eb;">{html.escape(identificacion)}</td>
            </tr>
            <tr>
              <td style="padding:8px 12px; background-color:#f1f5f9; border:1px solid #e5e7eb;"><strong>Número de soportes adjuntos</strong></td>
              <td style="padding:8px 12px; border:1px solid #e5e7eb;">{total}</td>
            </tr>
          </table>
          <p style="margin:0 0 6px 0;"><strong>Archivos adjuntos:</strong></p>
          <ul style="margin:0 0 16px 18px; padding:0;">{lista_html}</ul>
          <p style="margin:0 0 14px 0;">
            Si requiere alguna aclaración sobre la información, le agradecemos
            comunicarse con nosotros a través del correo
            <a href="mailto:{CORREO_CONTACTO_SOPORTES}" style="color:#1e3a5f;">{CORREO_CONTACTO_SOPORTES}</a>.
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

    for a in archivos:
        msg.add_attachment(
            a["bytes"],
            maintype="application",
            subtype="pdf",
            filename=a["nombre"],
        )
    return msg


def enviar_soportes_particulares(envios: list[dict]) -> dict:
    """
    Envía un correo por particular, con todos sus PDF adjuntos, reutilizando
    una sola conexión a Gmail. Cada envío debe traer: identificacion, nombre,
    correo y archivos (lista de {"nombre", "bytes"}).
    Devuelve {identificacion: (ok, mensaje_de_error)}.
    """
    try:
        remitente = st.secrets["gmail_address"]
        clave_app = st.secrets["gmail_app_password"]
        cc = list(st.secrets.get("cc_emails", []))
    except KeyError as e:
        return {env["identificacion"]: (False, f"Falta configurar {e} en secrets") for env in envios}

    resultados: dict = {}
    try:
        contexto = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=contexto) as server:
            server.login(remitente, clave_app)
            for envio in envios:
                ident = envio["identificacion"]
                peso = sum(len(a["bytes"]) for a in envio["archivos"])
                if peso > LIMITE_BYTES_ADJUNTOS:
                    resultados[ident] = (
                        False,
                        f"Los adjuntos pesan {peso / 1024 / 1024:.1f} MB y superan el límite "
                        f"de {LIMITE_BYTES_ADJUNTOS // 1024 // 1024} MB por correo.",
                    )
                    continue
                try:
                    server.send_message(_armar_mensaje_soporte(remitente, cc, envio))
                    resultados[ident] = (True, "")
                except Exception as e:
                    resultados[ident] = (False, str(e))
    except Exception as e:
        for envio in envios:
            resultados.setdefault(envio["identificacion"], (False, str(e)))
    return resultados