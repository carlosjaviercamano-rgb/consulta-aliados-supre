"""Elementos visuales compartidos por los módulos."""

import html
import re

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


_REGEX_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def correo_valido(correo: str) -> bool:
    return bool(_REGEX_CORREO.match(str(correo).strip()))


def editor_registro(
    *,
    prefijo: str,
    etiqueta_busqueda: str,
    etiqueta_id: str,
    etiqueta_nombre: str,
    obtener,
    actualizar,
) -> None:
    """
    Buscar un registro por su NIT/identificación y editar su nombre y correo.
    El identificador no se puede cambiar (es lo que enlaza facturas y soportes).

    obtener(id) -> {"id", "nombre", "correo"} o None
    actualizar(id, nombre, correo) -> guarda en el Sheet
    """
    ss = st.session_state
    clave = f"{prefijo}_edit"
    ss.setdefault(f"{clave}_n", 0)

    with st.form(f"{prefijo}_buscar"):
        valor = st.text_input(etiqueta_busqueda)
        buscar = st.form_submit_button("Buscar")

    if buscar:
        registro = obtener(valor) if valor.strip() else None
        if registro is None:
            ss.pop(clave, None)
            st.error(f"No se encontró ningún registro con ese {etiqueta_id}.")
        else:
            ss[clave] = registro
            ss[f"{clave}_n"] += 1  # reinicia los campos con los datos recién cargados

    registro = ss.get(clave)
    if not registro:
        return

    n = ss[f"{clave}_n"]
    with st.form(f"{prefijo}_guardar"):
        st.markdown(f"Editando {etiqueta_id}: **{registro['id']}** (no se puede modificar)")
        nombre = st.text_input(etiqueta_nombre, value=registro["nombre"], key=f"{clave}_nombre_{n}")
        correo = st.text_input("Correo electrónico", value=registro["correo"], key=f"{clave}_correo_{n}")
        guardar = st.form_submit_button("Guardar cambios")

    if guardar:
        nombre, correo = nombre.strip(), correo.strip()
        if not nombre or not correo:
            st.error("El nombre y el correo son obligatorios.")
        elif not correo_valido(correo):
            st.error("El correo no parece válido.")
        elif nombre == registro["nombre"].strip() and correo == registro["correo"].strip():
            st.info("No hay cambios para guardar.")
        else:
            try:
                actualizar(registro["id"], nombre, correo)
            except LookupError:
                ss.pop(clave, None)
                st.error(f"Ese {etiqueta_id} ya no existe en el Sheet. Vuelve a buscarlo.")
            else:
                registro["nombre"], registro["correo"] = nombre, correo
                st.success("Datos actualizados correctamente.")