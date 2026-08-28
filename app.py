"""
Consulta Aliados Supre
Punto de entrada de la app. Define la navegación (nombres e íconos del
menú lateral) y aplica estilos visuales globales.
"""

import streamlit as st

st.set_page_config(
    page_title="Consulta Aliados Supre",
    page_icon="📄",
    layout="wide",
)

# Estilo del menú lateral: texto más grande y con color de marca,
# para que "Aliados" y "Administración" se destaquen bien.
st.markdown(
    """
    <style>
    [data-testid="stSidebarNav"] a,
    [data-testid="stSidebarNav"] span {
        font-size: 1.15rem !important;
        font-weight: 600 !important;
        color: #4F8BF9 !important;
    }
    [data-testid="stSidebarNav"] a:hover span {
        color: #7db0ff !important;
    }

    /* Oculta los elementos de la barra superior de Streamlit Cloud (Share,
       GitHub, editar, etc.) para que los proveedores externos no vean ni
       puedan llegar al código fuente. Ojo: NO ocultamos el header completo,
       porque ahí también vive el botón de abrir/cerrar el menú lateral
       (colapsar/expandir) — si se oculta todo el header, ese botón deja de
       verse y el usuario no puede volver a abrir el menú.
    */
    header[data-testid="stHeader"] {
        background: transparent;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stDecoration"] {visibility: hidden;}
    [data-testid="stStatusWidget"] {visibility: hidden;}
    .stAppDeployButton {visibility: hidden;}
    #GithubIcon {visibility: hidden;}
    .viewerBadge_container__1QSob {display: none;}
    .viewerBadge_link__1S137 {display: none;}

    /* El botón para reabrir el menú lateral vive dentro de stToolbar junto
       con otros íconos que sí queremos ocultar (deploy, github, etc.).
       En vez de ocultar todo stToolbar (lo que también tapaba este botón),
       ocultamos stToolbar por defecto pero forzamos que ESTE control
       específico se mantenga siempre visible. */
    [data-testid="stToolbar"] {visibility: hidden;}
    [data-testid="collapsedControl"] {
        visibility: visible !important;
        display: flex !important;
        opacity: 1 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

pagina_aliados = st.Page("vista_aliados.py", title="Aliados", icon="🤝", default=True)
pagina_admin = st.Page("pages/1_Administracion.py", title="Administración", icon="🔐")

pg = st.navigation([pagina_aliados, pagina_admin])
pg.run()