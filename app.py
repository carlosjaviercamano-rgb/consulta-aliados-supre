"""
Aliados Supre — Envío de facturas por correo.
Página única de administración: alta de proveedores, carga del CSV diario
y envío de las facturas a cada aliado por correo (Excel adjunto).
"""

import hashlib

import pandas as pd
import streamlit as st

from email_client import enviar_correos_facturas
from sheets_client import (
    ESTADO_LISTO,
    agregar_proveedor,
    cargar_facturas_masivo,
    cargar_proveedores,
    marcar_enviadas,
    nit_existe,
    obtener_facturas_por_enviar,
    preparar_envios,
)

st.set_page_config(
    page_title="Envío de facturas a aliados",
    page_icon="📨",
    layout="wide",
)

# Oculta los elementos de la barra de Streamlit Cloud (Share, GitHub, etc.)
st.markdown(
    """
    <style>
    header[data-testid="stHeader"] {background: transparent;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden;}
    [data-testid="stDecoration"] {visibility: hidden;}
    [data-testid="stStatusWidget"] {visibility: hidden;}
    .stAppDeployButton {visibility: hidden;}
    #GithubIcon {visibility: hidden;}
    .viewerBadge_container__1QSob {display: none;}
    .viewerBadge_link__1S137 {display: none;}
    </style>
    """,
    unsafe_allow_html=True,
)

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


st.title("📨 Envío de facturas a aliados")

# ---------- Autenticación de administrador ----------
if "admin_autenticado" not in st.session_state:
    st.session_state.admin_autenticado = False

# Recupera la sesión si la URL trae un token válido (evita pedir la clave tras un F5)
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
    st.session_state.pop("revisar_envio", None)
    if "admin_token" in st.query_params:
        del st.query_params["admin_token"]


col_estado, col_logout = st.columns([5, 1])
with col_estado:
    st.success("Sesión de administrador activa.")
with col_logout:
    st.button("Cerrar sesión", on_click=_cerrar_sesion_admin, use_container_width=True)

# =====================================================================
# 1. ALTA DE PROVEEDORES
# =====================================================================
st.header("1. Proveedores")

with st.form("alta_proveedor", clear_on_submit=True):
    st.subheader("Nuevo proveedor")
    nombre = st.text_input("Nombre completo / Razón social")
    correo = st.text_input("Correo electrónico (aquí recibirá las facturas)")
    nit = st.text_input("NIT")
    enviar_alta = st.form_submit_button("Dar de alta")

if enviar_alta:
    if not (nombre and correo and nit):
        st.error("Todos los campos son obligatorios.")
    elif "@" not in correo:
        st.error("El correo no parece válido.")
    elif nit_existe(nit):
        st.warning(f"El NIT {nit} ya está registrado. No se creó un duplicado.")
    else:
        agregar_proveedor(nit=nit, nombre=nombre, correo=correo)
        st.success(f"Proveedor '{nombre}' (NIT {nit}) registrado correctamente.")

st.subheader("Proveedores registrados")
st.dataframe(cargar_proveedores(), use_container_width=True, hide_index=True)

# =====================================================================
# 2. CARGA MASIVA DEL CSV
# =====================================================================
st.divider()
st.header("2. Cargar facturas (CSV diario)")
st.caption(
    "Sube el reporte descargado de AWS. Las facturas nuevas quedan como 'por enviar'. "
    "Columnas requeridas: " + ", ".join(f"`{c}`" for c in COLUMNAS_ESPERADAS)
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
                try:
                    with st.spinner("Procesando y escribiendo en el Google Sheet..."):
                        resumen = cargar_facturas_masivo(df_csv)
                except RuntimeError as e:
                    st.error(str(e))
                else:
                    st.success("Carga procesada. Las facturas nuevas quedaron como 'por enviar'.")

                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Total filas", resumen["total"])
                    c2.metric("Cargadas (por enviar)", resumen["cargadas"])
                    c3.metric("Duplicadas (omitidas)", resumen["duplicados"])
                    c4.metric("No guardadas (por revisar)", len(resumen["por_revisar"]))

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
                        st.info(
                            f"{len(resumen['nits_no_encontrados'])} facturas son de NITs que aún no "
                            f"están registrados como proveedor. Quedaron guardadas como 'por enviar' "
                            f"y saldrán cuando registres al proveedor y envíes los correos."
                        )
                        st.dataframe(resumen["nits_no_encontrados"], use_container_width=True, hide_index=True)
                        st.download_button(
                            "Descargar filas con NIT no registrado (CSV)",
                            data=resumen["nits_no_encontrados"].to_csv(index=False).encode("utf-8-sig"),
                            file_name="nit_no_registrado.csv",
                            mime="text/csv",
                        )

# =====================================================================
# 3. ENVÍO DE CORREOS
# =====================================================================
st.divider()
st.header("3. Enviar facturas a los aliados")
st.caption(
    "Revisa qué se va a enviar antes de mandar nada. Cada aliado recibe un correo con un "
    "Excel adjunto con sus facturas 'por enviar'; luego esas facturas pasan a 'enviado'."
)

if st.button("Revisar pendientes de envío"):
    st.session_state.revisar_envio = True

if st.session_state.get("revisar_envio"):
    try:
        pendientes = obtener_facturas_por_enviar()
    except RuntimeError as e:
        st.error(str(e))
        st.stop()

    if pendientes.empty:
        st.success("No hay facturas por enviar. 🎉")
    else:
        envios = preparar_envios(pendientes, cargar_proveedores())
        listos = [e for e in envios if e["estado"] == ESTADO_LISTO]
        bloqueados = [e for e in envios if e["estado"] != ESTADO_LISTO]

        m1, m2, m3 = st.columns(3)
        m1.metric("Facturas por enviar", len(pendientes))
        m2.metric("Correos listos", len(listos))
        m3.metric("Aliados bloqueados", len(bloqueados))

        st.dataframe(
            pd.DataFrame([
                {
                    "NIT": e["nit"],
                    "Aliado": e["nombre"],
                    "Correo": e["correo"],
                    "Facturas": len(e["facturas"]),
                    "Estado": e["estado"],
                }
                for e in envios
            ]),
            use_container_width=True,
            hide_index=True,
        )

        if bloqueados:
            st.warning(
                "Los aliados bloqueados no recibirán correo ahora; sus facturas siguen "
                "'por enviar' y saldrán la próxima vez, cuando los registres o corrijas su correo."
            )

        if listos and st.button(f"Enviar {len(listos)} correos", type="primary"):
            with st.spinner("Enviando correos..."):
                resultados = enviar_correos_facturas(listos)

            ok = [e for e in listos if resultados[e["nit"]][0]]
            fallidos = [e for e in listos if not resultados[e["nit"]][0]]

            # Marca como 'enviado' solo lo que realmente salió
            filas_ok = [int(f) for e in ok for f in e["facturas"]["_fila"]]
            try:
                marcar_enviadas(filas_ok)
            except Exception as e:
                st.error(
                    f"Los correos se enviaron, pero NO se pudo marcar las facturas como "
                    f"'enviado' en el Sheet ({e}). Márcalas manualmente para evitar reenvíos."
                )

            r1, r2 = st.columns(2)
            r1.metric("Correos enviados", len(ok))
            r2.metric("Correos fallidos", len(fallidos))

            if ok:
                st.success(f"Se enviaron {len(ok)} correos y sus facturas quedaron como 'enviado'.")
            if fallidos:
                st.error("Estos correos fallaron; sus facturas siguen 'por enviar':")
                st.dataframe(
                    pd.DataFrame([
                        {"NIT": e["nit"], "Aliado": e["nombre"], "Error": resultados[e["nit"]][1]}
                        for e in fallidos
                    ]),
                    use_container_width=True,
                    hide_index=True,
                )
