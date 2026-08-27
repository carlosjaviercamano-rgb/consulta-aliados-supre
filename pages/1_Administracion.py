"""
Página de administración: alta de proveedores.
Protegida con una contraseña de administrador (no es la misma app pública).
"""

import hashlib

import pandas as pd
import streamlit as st
from sheets_client import (
    agregar_proveedor,
    nit_existe,
    cargar_proveedores,
    cargar_facturas_masivo,
    obtener_pendientes_actuales,
)
from email_client import enviar_correo_bienvenida

COLUMNAS_ESPERADAS = [
    "fecha_factura",
    "factura_comision",
    "cedula_cliente",
    "nombre_cliente",
    "factura_aliado",
    "nit_aliado",
    "nombre_aliado",
    "validacion",
]


def _token_admin() -> str:
    """Token derivado de la contraseña de admin (no expone la clave en la URL)."""
    admin_password = st.secrets.get("admin_password", "")
    return hashlib.sha256(admin_password.encode()).hexdigest()[:16]


st.title("🔐 Administración de Proveedores")

# ---------- Autenticación de administrador ----------
if "admin_autenticado" not in st.session_state:
    st.session_state.admin_autenticado = False

# Si la sesión no está activa pero la URL trae un token válido, recupera
# la sesión automáticamente (esto es lo que evita que un F5 pida la clave de nuevo).
if not st.session_state.admin_autenticado and st.query_params.get("admin_token") == _token_admin():
    st.session_state.admin_autenticado = True

if not st.session_state.admin_autenticado:
    clave = st.text_input("Contraseña de administrador", type="password")
    if st.button("Ingresar"):
        if clave == st.secrets.get("admin_password", ""):
            st.session_state.admin_autenticado = True
            st.query_params["admin_token"] = _token_admin()
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")
    st.stop()


def _cerrar_sesion_admin():
    st.session_state.admin_autenticado = False
    if "admin_token" in st.query_params:
        del st.query_params["admin_token"]


# ---------- Formulario de alta ----------
col_estado, col_logout = st.columns([5, 1])
with col_estado:
    st.success("Sesión de administrador activa.")
with col_logout:
    st.button("Cerrar sesión", on_click=_cerrar_sesion_admin, use_container_width=True)

with st.form("alta_proveedor", clear_on_submit=True):
    st.subheader("Nuevo proveedor")
    nombre = st.text_input("Nombre completo / Razón social")
    correo = st.text_input("Correo electrónico")
    nit = st.text_input("NIT")
    enviar_correo_check = st.checkbox("Enviar correo de bienvenida automáticamente", value=True)
    enviar = st.form_submit_button("Dar de alta")

if enviar:
    if not (nombre and correo and nit):
        st.error("Todos los campos son obligatorios.")
    elif nit_existe(nit):
        st.warning(f"El NIT {nit} ya está registrado. No se creó un duplicado.")
    else:
        agregar_proveedor(nit=nit, nombre=nombre, correo=correo)
        st.success(f"Proveedor '{nombre}' (NIT {nit}) registrado correctamente.")

        if enviar_correo_check:
            with st.spinner("Enviando correo de bienvenida..."):
                ok, error = enviar_correo_bienvenida(destinatario=correo, nombre=nombre, nit=nit)
            if ok:
                st.success(f"Correo de bienvenida enviado a {correo}.")
            else:
                st.error(f"No se pudo enviar el correo automáticamente: {error}")
                st.info(
                    f"Puede comunicarle manualmente que su usuario y contraseña "
                    f"de acceso al portal son ambos su NIT: **{nit}**."
                )
        else:
            st.info(
                f"Su usuario y contraseña de acceso al portal son ambos su NIT: **{nit}**. "
                f"Recuerde comunicárselo por correo."
            )

st.divider()
st.subheader("Proveedores registrados")
df = cargar_proveedores()
st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Carga masiva de facturas (CSV diario)")
st.caption(
    "Sube el reporte descargado de AWS. El archivo debe tener las columnas: "
    + ", ".join(f"`{c}`" for c in COLUMNAS_ESPERADAS)
)

archivo = st.file_uploader("Archivo CSV", type=["csv"])

if archivo is not None:
    try:
        df_csv = pd.read_csv(archivo, dtype=str).fillna("")
    except Exception as e:
        st.error(f"No se pudo leer el archivo: {e}")
        df_csv = None

    if df_csv is not None:
        faltantes = [c for c in COLUMNAS_ESPERADAS if c not in df_csv.columns]
        if faltantes:
            st.error(f"Al archivo le faltan estas columnas: {', '.join(faltantes)}")
        else:
            st.write(f"Se detectaron **{len(df_csv)}** filas en el archivo.")
            if st.button("Procesar carga", type="primary"):
                with st.spinner("Procesando y escribiendo en el Google Sheet..."):
                    resumen = cargar_facturas_masivo(df_csv)

                st.success("Carga procesada.")

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total filas", resumen["total"])
                c2.metric("Cargadas", resumen["cargadas"])
                c3.metric("Duplicadas (omitidas)", resumen["duplicados"])
                c4.metric(
                    "Por revisar / NIT no encontrado",
                    len(resumen["por_revisar"]) + len(resumen["nits_no_encontrados"]),
                )

                if not resumen["por_revisar"].empty:
                    st.warning(
                        f"{len(resumen['por_revisar'])} filas no se guardaron (sin NIT, o "
                        f"marcadas como 'Validar' porque suelen traer la cédula del cliente "
                        f"en vez del NIT real). Revísalas y, si corresponde, corrígelas y "
                        f"vuelve a subir el archivo."
                    )
                    st.dataframe(resumen["por_revisar"], use_container_width=True, hide_index=True)
                    st.download_button(
                        "Descargar filas por revisar (CSV)",
                        data=resumen["por_revisar"].to_csv(index=False).encode("utf-8-sig"),
                        file_name="por_revisar.csv",
                        mime="text/csv",
                    )

                if not resumen["nits_no_encontrados"].empty:
                    st.warning(
                        f"{len(resumen['nits_no_encontrados'])} filas con NIT que no está "
                        f"registrado en Proveedores ya se guardaron. Cuando des de alta a ese "
                        f"proveedor, sus facturas aparecerán automáticamente sin resubir el archivo."
                    )
                    st.dataframe(resumen["nits_no_encontrados"], use_container_width=True, hide_index=True)
                    st.download_button(
                        "Descargar filas con NIT no encontrado (CSV)",
                        data=resumen["nits_no_encontrados"].to_csv(index=False).encode("utf-8-sig"),
                        file_name="nit_no_encontrado.csv",
                        mime="text/csv",
                    )

st.divider()
st.subheader("Facturas pendientes de revisión (acumulado hasta ahora)")
st.caption(
    "Esto revisa TODO lo que hay guardado en el Sheet hasta el momento, no solo la "
    "última carga — útil para ver de un vistazo todo lo que sigue pendiente."
)

if st.button("Consultar pendientes actuales"):
    with st.spinner("Consultando el Google Sheet..."):
        pendientes = obtener_pendientes_actuales()

    total_pendientes = len(pendientes["por_revisar"]) + len(pendientes["nits_no_encontrados"])
    st.metric("Total pendientes", total_pendientes)

    if not pendientes["por_revisar"].empty:
        st.warning(f"{len(pendientes['por_revisar'])} facturas sin NIT.")
        st.dataframe(pendientes["por_revisar"], use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar todas las facturas sin NIT (CSV)",
            data=pendientes["por_revisar"].to_csv(index=False).encode("utf-8-sig"),
            file_name="por_revisar_acumulado.csv",
            mime="text/csv",
        )

    if not pendientes["nits_no_encontrados"].empty:
        st.warning(f"{len(pendientes['nits_no_encontrados'])} facturas con NIT no registrado.")
        st.dataframe(pendientes["nits_no_encontrados"], use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar todas las facturas con NIT no encontrado (CSV)",
            data=pendientes["nits_no_encontrados"].to_csv(index=False).encode("utf-8-sig"),
            file_name="nit_no_encontrado_acumulado.csv",
            mime="text/csv",
        )

    if total_pendientes == 0:
        st.success("No hay facturas pendientes de revisión en este momento. 🎉")