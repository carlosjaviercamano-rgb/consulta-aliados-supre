"""
Módulo Soporte Particulares.

- Pestaña "Acta de particulares": registra a cada particular (nombre,
  identificación y correo) en la hoja 'Particulares' del Google Sheet.
- Pestaña "Adjuntar y enviar soportes": se van adjuntando PDF a cada
  particular (puede ser más de uno por particular) y al final un botón envía
  un correo por particular con todos sus soportes.
"""

import re

import pandas as pd
import streamlit as st

from email_client import LIMITE_BYTES_ADJUNTOS, enviar_soportes_particulares
from sheets_client import (
    ESTADO_LISTO,
    agregar_particular,
    cargar_particulares,
    particular_existe,
)
from ui import encabezado

_REGEX_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_LIMITE_MB = LIMITE_BYTES_ADJUNTOS // 1024 // 1024


def _correo_valido(correo: str) -> bool:
    return bool(_REGEX_CORREO.match(str(correo).strip()))


def render():
    encabezado(
        "📎",
        "Soporte Particulares",
        "Soportes de pago de intereses enviados por correo a cada particular",
    )
    tab_acta, tab_envio = st.tabs(["👥 Acta de particulares", "📎 Adjuntar y enviar soportes"])
    with tab_acta:
        _acta()
    with tab_envio:
        _adjuntar_y_enviar()


# =====================================================================
# Acta de particulares
# =====================================================================
def _acta():
    with st.form("alta_particular", clear_on_submit=True):
        st.subheader("Nuevo particular")
        nombre = st.text_input("Nombre completo")
        identificacion = st.text_input("Identificación (cédula o NIT)")
        correo = st.text_input("Correo electrónico (aquí recibirá los soportes)")
        enviar_alta = st.form_submit_button("Dar de alta")

    if enviar_alta:
        if not (nombre.strip() and identificacion.strip() and correo.strip()):
            st.error("Todos los campos son obligatorios.")
        elif not _correo_valido(correo):
            st.error("El correo no parece válido.")
        elif particular_existe(identificacion):
            st.warning(f"La identificación {identificacion} ya está registrada. No se creó un duplicado.")
        else:
            agregar_particular(identificacion=identificacion, nombre=nombre, correo=correo)
            st.success(f"Particular '{nombre.strip()}' ({identificacion.strip()}) registrado correctamente.")

    st.subheader("Particulares registrados")
    st.dataframe(cargar_particulares(), use_container_width=True, hide_index=True)


# =====================================================================
# Adjuntar soportes y enviar
# =====================================================================
def _mostrar_mensajes_previos():
    """Muestra el resultado del último envío y avisos guardados antes de un rerun."""
    ss = st.session_state

    aviso = ss.pop("soportes_aviso", None)
    if aviso:
        st.warning(aviso)

    resultado = ss.pop("soportes_resultado", None)
    if resultado:
        if resultado["ok"]:
            st.success(
                f"Se enviaron {len(resultado['ok'])} correos: " + ", ".join(resultado["ok"]) + ". "
                "Sus soportes salieron de la lista."
            )
        if resultado["fallidos"]:
            st.error("Estos correos fallaron; sus soportes siguen en la lista:")
            st.dataframe(pd.DataFrame(resultado["fallidos"]), use_container_width=True, hide_index=True)


def _adjuntar_y_enviar():
    ss = st.session_state
    ss.setdefault("soportes", {})  # {identificacion: [{"nombre": str, "bytes": bytes}, ...]}
    ss.setdefault("soportes_uploader_n", 0)

    _mostrar_mensajes_previos()

    particulares = cargar_particulares()
    if particulares.empty:
        st.info("Primero registra al menos un particular en la pestaña «Acta de particulares».")
        return

    por_id = {str(r["identificacion"]): r for _, r in particulares.iterrows()}
    opciones = {f"{r['nombre']} — {ident}": ident for ident, r in por_id.items()}

    # ---------- 1. Adjuntar ----------
    st.subheader("1. Adjuntar soportes")
    st.caption(
        "Elige el particular, sube sus PDF (puedes subir varios) y agrégalos a la lista. "
        "Repite con cada particular. La lista se conserva mientras no recargues la página."
    )
    elegido = st.selectbox("Particular", list(opciones), key="soportes_particular")
    archivos = st.file_uploader(
        "PDF del soporte de pago",
        type=["pdf"],
        accept_multiple_files=True,
        key=f"soportes_uploader_{ss.soportes_uploader_n}",
    )

    if st.button("Agregar a la lista", disabled=not archivos):
        ident = opciones[elegido]
        lista = ss.soportes.setdefault(ident, [])
        existentes = {(a["nombre"], len(a["bytes"])) for a in lista}
        repetidos = []
        for f in archivos:
            contenido = f.getvalue()
            if (f.name, len(contenido)) in existentes:
                repetidos.append(f.name)
                continue
            lista.append({"nombre": f.name, "bytes": contenido})
            existentes.add((f.name, len(contenido)))
        if repetidos:
            ss.soportes_aviso = "Ya estaban en la lista y no se agregaron de nuevo: " + ", ".join(repetidos)
        ss.soportes_uploader_n += 1  # limpia el cargador de archivos
        st.rerun()

    # ---------- 2. Lista de envío ----------
    st.divider()
    st.subheader("2. Lista de envío")

    if not ss.soportes:
        st.info("Aún no has adjuntado soportes.")
        return

    envios = []
    resumen = []
    for ident, lista in ss.soportes.items():
        particular = por_id.get(ident)
        peso = sum(len(a["bytes"]) for a in lista)
        if particular is None:
            nombre, correo = ident, ""
            estado = "Particular no encontrado en el Sheet"
        else:
            nombre, correo = str(particular["nombre"]), str(particular["correo"]).strip()
            if not _correo_valido(correo):
                estado = "Sin correo válido"
            elif peso > LIMITE_BYTES_ADJUNTOS:
                estado = f"Excede {_LIMITE_MB} MB"
            else:
                estado = ESTADO_LISTO
                envios.append({"identificacion": ident, "nombre": nombre, "correo": correo, "archivos": lista})
        resumen.append({
            "Particular": nombre,
            "Identificación": ident,
            "Correo": correo,
            "Soportes": len(lista),
            "Peso (MB)": round(peso / 1024 / 1024, 2),
            "Estado": estado,
        })

    resumen.sort(key=lambda r: r["Particular"].lower())
    m1, m2, m3 = st.columns(3)
    m1.metric("Particulares en la lista", len(resumen))
    m2.metric("Soportes adjuntos", sum(r["Soportes"] for r in resumen))
    m3.metric("Correos listos", len(envios))
    st.dataframe(pd.DataFrame(resumen), use_container_width=True, hide_index=True)

    if len(envios) < len(resumen):
        st.warning(
            "Los particulares que no están «Listo para enviar» no recibirán correo ahora; "
            "corrige el problema o quita sus soportes."
        )

    # Detalle de archivos por particular, con opción de quitar
    for ident in sorted(ss.soportes, key=lambda i: str(por_id[i]["nombre"]).lower() if i in por_id else i):
        lista = ss.soportes[ident]
        etiqueta = f"{por_id[ident]['nombre']} — {len(lista)} soporte(s)" if ident in por_id else f"{ident} — {len(lista)} soporte(s)"
        with st.expander(etiqueta):
            for i, a in enumerate(lista):
                c1, c2 = st.columns([6, 1])
                c1.write(f"📄 {a['nombre']}  ·  {len(a['bytes']) / 1024:.0f} KB")
                if c2.button("Quitar", key=f"quitar_{ident}_{i}"):
                    lista.pop(i)
                    if not lista:
                        del ss.soportes[ident]
                    st.rerun()

    # ---------- 3. Enviar ----------
    b1, b2 = st.columns([3, 1])
    enviar = b1.button(f"Enviar {len(envios)} correos", type="primary", disabled=not envios)
    if b2.button("Vaciar lista"):
        ss.soportes = {}
        st.rerun()

    if enviar:
        with st.spinner("Enviando correos..."):
            resultados = enviar_soportes_particulares(envios)

        ok = [e for e in envios if resultados.get(e["identificacion"], (False, ""))[0]]
        fallidos = [e for e in envios if not resultados.get(e["identificacion"], (False, ""))[0]]

        for e in ok:
            ss.soportes.pop(e["identificacion"], None)

        ss.soportes_resultado = {
            "ok": [e["nombre"] for e in ok],
            "fallidos": [
                {
                    "Particular": e["nombre"],
                    "Correo": e["correo"],
                    "Error": resultados.get(e["identificacion"], (False, "Sin respuesta"))[1],
                }
                for e in fallidos
            ],
        }
        st.rerun()
