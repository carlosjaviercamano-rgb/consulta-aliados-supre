"""
Envío de correos de bienvenida a proveedores, vía Gmail SMTP
usando una cuenta institucional dedicada (no personal).
"""

import smtplib
import ssl
from email.message import EmailMessage

import streamlit as st


def enviar_correo_bienvenida(destinatario: str, nombre: str, nit: str) -> tuple[bool, str]:
    """
    Envía el correo de bienvenida con las credenciales de acceso al portal.
    Devuelve (True, "") si se envió bien, o (False, "mensaje de error") si falló.
    """
    try:
        remitente = st.secrets["gmail_address"]
        clave_app = st.secrets["gmail_app_password"]
        portal_url = st.secrets.get("portal_url", "http://localhost:8501")
        cc_emails = st.secrets.get("cc_emails", [])
    except KeyError as e:
        return False, f"Falta configurar {e} en secrets.toml"

    asunto = "Bienvenido al portal Consulta Aliados Supre"
    cuerpo = f"""Hola {nombre},

Ya tiene acceso al portal de Consulta Aliados Supre, donde podrá consultar sus facturas de comisión asociadas al NIT {nit}.

Ingrese aquí: {portal_url}

Usuario: {nit}
Contraseña: {nit}

Si tiene inconvenientes para ingresar, comuníquese con nosotros respondiendo este correo.

Saludos,
Equipo Suprecredito
"""

    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = remitente
    msg["To"] = destinatario
    if cc_emails:
        msg["Cc"] = ", ".join(cc_emails)
    msg.set_content(cuerpo)

    try:
        contexto = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=contexto) as server:
            server.login(remitente, clave_app)
            server.send_message(msg)
        return True, ""
    except Exception as e:
        return False, str(e)