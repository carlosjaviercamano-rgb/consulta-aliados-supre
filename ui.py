"""Elementos visuales compartidos por los módulos."""

import html

import streamlit as st


def encabezado(icono: str, titulo: str, subtitulo: str) -> None:
    """Banner azul con el título del módulo (estilo App Supre)."""
    # Todo en una línea: con sangría, Markdown lo trataría como bloque de código.
    st.markdown(
        '<div style="background:linear-gradient(135deg,#1e3a5f 0%,#1e40af 100%);'
        'border-radius:12px;padding:1.2rem 1.6rem;margin-bottom:1.2rem;'
        'display:flex;align-items:center;gap:1rem;">'
        f'<div style="font-size:2rem;">{icono}</div>'
        '<div>'
        f'<div style="color:#ffffff;font-size:1.4rem;font-weight:700;">{html.escape(titulo)}</div>'
        f'<div style="color:#93c5fd;font-size:0.85rem;margin-top:0.2rem;">{html.escape(subtitulo)}</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )
