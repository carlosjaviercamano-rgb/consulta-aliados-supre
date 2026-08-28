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

    [data-testid="stToolbar"] {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

# Botón flotante propio para abrir/cerrar el menú lateral: como ocultamos
# stToolbar (donde vive el control nativo), inyectamos un botón aparte que,
# al hacer clic, dispara el control nativo por JavaScript (esto funciona
# aunque el control nativo esté oculto por CSS). Misma técnica usada en
# App Supre Financiero.
import streamlit.components.v1 as _components

_components.html(
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

pagina_aliados = st.Page("vista_aliados.py", title="Aliados", icon="🤝", default=True)
pagina_admin = st.Page("pages/1_Administracion.py", title="Administración", icon="🔐")

pg = st.navigation([pagina_aliados, pagina_admin])
pg.run()