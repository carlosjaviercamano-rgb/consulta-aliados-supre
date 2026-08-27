"""
Vista de Aliados: login y consulta de facturas.
Este archivo es cargado por app.py a través de st.navigation.
"""

import pandas as pd
import streamlit as st
from sheets_client import validar_login, facturas_por_nit

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

# Estilo visual del formulario de login, inspirado en App Supre Financiero
st.markdown(
    """
    <style>
    [data-testid="stForm"] {
        background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #16323d 100%);
        border-radius: 20px;
        padding: 2.5rem 2.5rem 1.5rem 2.5rem;
        border: 1px solid rgba(255,255,255,0.08);
        max-width: 460px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.35);
    }
    [data-testid="stForm"] h3 {
        color: #ffffff !important;
        font-weight: 700;
    }
    [data-testid="stForm"] label p {
        color: #7dd3c0 !important;
        font-weight: 600;
        font-size: 0.95rem;
    }
    [data-testid="stForm"] input {
        background-color: rgba(255,255,255,0.06) !important;
        border: none !important;
        border-bottom: 1px solid rgba(255,255,255,0.25) !important;
        border-radius: 6px !important;
        color: #ffffff !important;
    }
    [data-testid="stForm"] button {
        background-color: rgba(79,139,249,0.15) !important;
        border: 1px solid #4F8BF9 !important;
        border-radius: 10px !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        letter-spacing: 0.03em;
    }
    [data-testid="stForm"] button:hover {
        background-color: rgba(79,139,249,0.3) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Estado de sesión ----------
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.proveedor = None

# Si la sesión no está activa pero la URL trae ?nit=..., intenta recuperar
# la sesión automáticamente (esto es lo que evita que un F5 cierre sesión).
if not st.session_state.autenticado and "nit" in st.query_params:
    proveedor_recordado = validar_login(st.query_params["nit"])
    if proveedor_recordado is not None:
        st.session_state.autenticado = True
        st.session_state.proveedor = proveedor_recordado


def cerrar_sesion():
    st.session_state.autenticado = False
    st.session_state.proveedor = None
    if "nit" in st.query_params:
        del st.query_params["nit"]


# ---------- Pantalla de login ----------
def pantalla_login():
    st.title("📄 Consulta Aliados Supre")
    st.caption("Portal de consulta de facturas de comisión para aliados de Suprecredito")

    with st.form("form_login"):
        st.subheader("Iniciar sesión")
        nit = st.text_input("NIT", placeholder="Ingrese su NIT")
        clave = st.text_input("Contraseña", type="password", placeholder="Su NIT también es la contraseña")
        enviar = st.form_submit_button("Ingresar", use_container_width=True)

    if enviar:
        if not nit or not clave:
            st.error("Por favor complete NIT y contraseña.")
            return
        if nit.strip() != clave.strip():
            st.error("NIT y contraseña no coinciden.")
            return
        proveedor = validar_login(nit)
        if proveedor is None:
            st.error("No encontramos un proveedor registrado con ese NIT. Si es su primera vez, comuníquese con Suprecredito.")
            return
        st.session_state.autenticado = True
        st.session_state.proveedor = proveedor
        st.query_params["nit"] = proveedor["nit"]
        st.rerun()


# ---------- Pantalla de facturas ----------
def pantalla_facturas():
    proveedor = st.session_state.proveedor

    col_titulo, col_logout = st.columns([5, 1])
    with col_titulo:
        st.title("📄 Mis Facturas")
        st.caption(f"{proveedor.get('nombre', '')} · NIT {proveedor.get('nit', '')}")
    with col_logout:
        st.write("")
        st.button("Cerrar sesión", on_click=cerrar_sesion, use_container_width=True)

    df = facturas_por_nit(proveedor["nit"])

    if df.empty:
        st.info("Aún no tiene facturas registradas.")
        st.caption(
            "ℹ️ Las facturas quedan visibles a partir del día hábil siguiente a su "
            "emisión. Si emitió una factura hoy, no la verá reflejada hasta entonces."
        )
        return

    # Columna auxiliar de fecha parseada, solo para poder filtrar (no se muestra)
    df["_fecha_dt"] = pd.to_datetime(df["fecha_factura"], errors="coerce")

    modo_filtro = st.radio(
        "Filtrar facturas por:",
        ["Todas", "Mes", "Rango de fechas"],
        horizontal=True,
    )

    df_filtrado = df

    if modo_filtro == "Mes":
        periodos = (
            df["_fecha_dt"].dropna().dt.to_period("M").drop_duplicates().sort_values(ascending=False)
        )
        opciones = {f"{MESES_ES[p.month]} {p.year}": p for p in periodos}
        if opciones:
            seleccion = st.selectbox("Selecciona el mes", list(opciones.keys()))
            periodo = opciones[seleccion]
            df_filtrado = df[df["_fecha_dt"].dt.to_period("M") == periodo]
        else:
            st.info("No hay fechas válidas para filtrar por mes.")

    elif modo_filtro == "Rango de fechas":
        fecha_min = df["_fecha_dt"].min()
        fecha_max = df["_fecha_dt"].max()
        if pd.isna(fecha_min) or pd.isna(fecha_max):
            st.info("No hay fechas válidas para filtrar por rango.")
        else:
            with st.container(border=True):
                col_desde, col_guion, col_hasta = st.columns([5, 1, 5])
                desde = col_desde.date_input(
                    "Desde",
                    value=fecha_min.date(),
                    min_value=fecha_min.date(),
                    max_value=fecha_max.date(),
                    key="fecha_desde_facturas",
                )
                col_guion.markdown(
                    "<div style='text-align:center; padding-top:2.1rem; color:#7dd3c0; "
                    "font-weight:700;'>→</div>",
                    unsafe_allow_html=True,
                )
                hasta = col_hasta.date_input(
                    "Hasta",
                    value=fecha_max.date(),
                    min_value=fecha_min.date(),
                    max_value=fecha_max.date(),
                    key="fecha_hasta_facturas",
                )

            if desde > hasta:
                st.error("La fecha 'Desde' no puede ser posterior a la fecha 'Hasta'.")
            elif (hasta - desde).days > 30:
                st.error(
                    "El rango no puede superar 30 días. Ajusta las fechas o usa el filtro por Mes."
                )
            else:
                df_filtrado = df[
                    (df["_fecha_dt"].dt.date >= desde) & (df["_fecha_dt"].dt.date <= hasta)
                ]

    df_filtrado = df_filtrado.drop(columns=["_fecha_dt"])

    if df_filtrado.empty:
        st.warning("No hay facturas para el filtro seleccionado.")
        return

    # La columna 'validacion' es de uso interno y no se muestra al proveedor
    columnas_visibles = [c for c in df_filtrado.columns if c != "validacion"]
    df_visible = df_filtrado[columnas_visibles].rename(columns={
        "fecha_factura": "Fecha Factura",
        "factura_comision": "Factura Comisión",
        "cedula_cliente": "Cédula Cliente",
        "nombre_cliente": "Nombre Cliente",
        "factura_aliado": "Factura Aliado",
        "nit_aliado": "NIT Aliado",
        "nombre_aliado": "Nombre Aliado",
    })

    st.metric("Total facturas", len(df_visible))
    st.dataframe(df_visible, use_container_width=True, hide_index=True)

    csv = df_visible.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Descargar CSV",
        data=csv,
        file_name=f"facturas_{proveedor['nit']}.csv",
        mime="text/csv",
    )

    st.caption(
        "ℹ️ Las facturas quedan visibles a partir del día hábil siguiente a su "
        "emisión. Si emitió una factura hoy, no la verá reflejada hasta entonces."
    )


# ---------- Enrutamiento interno ----------
if st.session_state.autenticado:
    pantalla_facturas()
else:
    pantalla_login()