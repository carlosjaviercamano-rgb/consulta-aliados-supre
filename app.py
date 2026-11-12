"""
Supre Aliados — envío de facturas y soportes por correo.

Punto de entrada: login de administrador, menú lateral de módulos y enrutador.
  - Facturas Aliados:    modulo_facturas.py
  - Soporte Particulares: modulo_particulares.py
"""

import hashlib

import streamlit as st
import streamlit.components.v1 as components

import modulo_facturas
import modulo_particulares

st.set_page_config(
    page_title="Supre Aliados",
    page_icon="📨",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    /* Oculta la barra de Streamlit Cloud (Share, GitHub, etc.) */
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

    /* Menú lateral */
    [data-testid="stSidebar"] {
        background: #1a1f2e;
        border-right: 1px solid #2d3548;
    }
    .sidebar-logo {
        padding: 1rem 0.2rem 0.8rem 0.2rem;
        border-bottom: 1px solid #2d3548;
        margin-bottom: 0.8rem;
    }
    .sidebar-logo h2 {
        color: #ffffff;
        font-size: 1.1rem;
        font-weight: 700;
        margin: 0;
    }
    .sidebar-logo p {
        color: #64748b;
        font-size: 0.75rem;
        margin: 0.2rem 0 0 0;
    }
    [data-testid="stSidebar"] button[kind="secondary"],
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
        background: #1e40af !important;
        color: #ffffff !important;
        border: 1px solid #1e40af !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    [data-testid="stSidebar"] button[kind="secondary"]:hover,
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {
        background: #1d4ed8 !important;
        border-color: #1d4ed8 !important;
    }
    /* Módulo activo */
    [data-testid="stSidebar"] button[kind="primary"],
    [data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
        background: #2563eb !important;
        color: #ffffff !important;
        border: 2px solid #93c5fd !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

MODULOS = [
    ("facturas", "📨", "Facturas Aliados"),
    ("particulares", "📎", "Soporte Particulares"),
]


def _token_admin() -> str:
    """Token derivado de la contraseña de admin (no expone la clave en la URL)."""
    admin_password = st.secrets.get("admin_password", "")
    return hashlib.sha256(admin_password.encode()).hexdigest()[:16]


# ---------- Autenticación de administrador ----------
if "admin_autenticado" not in st.session_state:
    st.session_state.admin_autenticado = False

# Recupera la sesión si la URL trae un token válido (evita pedir la clave tras un F5)
if not st.session_state.admin_autenticado and st.query_params.get("admin_token") == _token_admin():
    st.session_state.admin_autenticado = True

if not st.session_state.admin_autenticado:
    st.title("🏦 Supre Aliados")
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
    for clave in list(st.session_state.keys()):
        if clave.startswith("soportes") or clave == "revisar_envio" or "_edit" in clave:
            del st.session_state[clave]
    if "admin_token" in st.query_params:
        del st.query_params["admin_token"]


if "modulo" not in st.session_state:
    st.session_state.modulo = "facturas"

# ---------- Menú lateral ----------
with st.sidebar:
    st.markdown(
        '<div class="sidebar-logo"><h2>🏦 Supre Aliados</h2>'
        "<p>Facturas y soportes por correo</p></div>",
        unsafe_allow_html=True,
    )
    st.caption("👤 Administrador")
    st.button("🚪 Cerrar sesión", on_click=_cerrar_sesion_admin, use_container_width=True)
    st.markdown("---")
    st.markdown("**MÓDULOS**")
    for clave, icono, etiqueta in MODULOS:
        activo = st.session_state.modulo == clave
        if st.button(
            f"{icono}  {etiqueta}",
            key=f"nav_{clave}",
            use_container_width=True,
            type="primary" if activo else "secondary",
        ):
            st.session_state.modulo = clave
            st.rerun()

# Botón flotante para abrir/cerrar el menú lateral: como la barra de Streamlit
# está oculta, este botón dispara por JavaScript el control nativo del sidebar.
components.html(
    """
    <script>
    (function() {
        function crearBotonFlotante() {
            var doc = window.parent.document;
            if (doc.getElementById('aliados-toggle-sidebar')) return;

            var btn = doc.createElement('button');
            btn.id = 'aliados-toggle-sidebar';
            btn.innerHTML = '&#9776;';
            btn.style.position = 'fixed';
            btn.style.top = '0.6rem';
            btn.style.left = '0.6rem';
            btn.style.zIndex = '999999';
            btn.style.background = '#1c1f26';
            btn.style.color = '#ffffff';
            btn.style.border = '1px solid #2d3548';
            btn.style.borderRadius = '6px';
            btn.style.padding = '0.35rem 0.6rem';
            btn.style.fontSize = '1rem';
            btn.style.cursor = 'pointer';
            btn.title = 'Mostrar / ocultar menú';

            btn.onclick = function() {
                var nativo = doc.querySelector('[data-testid="collapsedControl"] button')
                          || doc.querySelector('[data-testid="stSidebarCollapseButton"] button')
                          || doc.querySelector('[data-testid="collapsedControl"]')
                          || doc.querySelector('[data-testid="stSidebarCollapseButton"]');
                if (nativo) { nativo.click(); }
            };

            doc.body.appendChild(btn);
        }

        crearBotonFlotante();
        setInterval(crearBotonFlotante, 1000);
    })();
    </script>
    """,
    height=0,
)

# ---------- Enrutador ----------
if st.session_state.modulo == "particulares":
    modulo_particulares.render()
else:
    modulo_facturas.render()