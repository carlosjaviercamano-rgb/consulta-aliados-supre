"""
Módulo Soportes Proveedores (gastos fijos mensuales).

- Pestaña "Proveedores de gastos": registra a cada proveedor (nombre, NIT y
  correo) en la hoja 'ProveedoresGastos' del Google Sheet.
- Pestaña "Adjuntar y enviar soportes": se van adjuntando PDF a cada
  proveedor (puede ser más de uno) y al final un botón envía un correo por
  proveedor con todos sus soportes de pago.

Es una copia adaptada de Soporte Particulares; sus claves de sesión empiezan
por "soportesprov" para no mezclarse con las de particulares (y se limpian
igual al cerrar sesión, porque empiezan por "soportes").
"""

import pandas as pd
import streamlit as st

from email_client import LIMITE_BYTES_ADJUNTOS, MESES_ES, enviar_soportes_proveedores
from sheets_client import (
    ESTADO_LISTO,
    actualizar_proveedor_gasto,
    agregar_proveedor_gasto,
    cargar_proveedores_gastos,
    obtener_proveedor_gasto,
    proveedor_gasto_existe,
)
from ui import correo_valido, editor_registro, encabezado

_LIMITE_MB = LIMITE_BYTES_ADJUNTOS // 1024 // 1024
_P = "soportesprov"  # prefijo de las claves de sesión de este módulo


def render():
    encabezado(
        "🧾",
        "Soportes Proveedores",
        "Soportes de pago de gastos fijos enviados por correo a cada proveedor",
    )
    tab_acta, tab_envio = st.tabs(["🏢 Proveedores de gastos", "📎 Adjuntar y enviar soportes"])
    with tab_acta:
        _acta()
    with tab_envio:
        _adjuntar_y_enviar()


# =====================================================================
# Proveedores de gastos
# =====================================================================
def _acta():
    accion = st.radio(
        "¿Qué deseas hacer?",
        ["Nuevo proveedor", "Editar proveedor"],
        horizontal=True,
        key="provg_accion",
    )

    if accion == "Nuevo proveedor":
        with st.form("alta_proveedor_gasto", clear_on_submit=True):
            st.subheader("Nuevo proveedor")
            nombre = st.text_input("Nombre o razón social")
            nit = st.text_input("NIT (o cédula si es persona natural)")
            correo = st.text_input("Correo electrónico (aquí recibirá los soportes)")
            enviar_alta = st.form_submit_button("Dar de alta")

        if enviar_alta:
            if not (nombre.strip() and nit.strip() and correo.strip()):
                st.error("Todos los campos son obligatorios.")
            elif not correo_valido(correo):
                st.error("El correo no parece válido.")
            elif proveedor_gasto_existe(nit):
                st.warning(f"El NIT {nit} ya está registrado. No se creó un duplicado.")
            else:
                agregar_proveedor_gasto(nit=nit, nombre=nombre, correo=correo)
                st.success(f"Proveedor '{nombre.strip()}' ({nit.strip()}) registrado correctamente.")

    else:
        editor_registro(
            prefijo="provg",
            etiqueta_busqueda="NIT del proveedor a editar",
            etiqueta_id="NIT",
            etiqueta_nombre="Nombre o razón social",
            obtener=obtener_proveedor_gasto,
            actualizar=actualizar_proveedor_gasto,
        )

    st.subheader("Proveedores registrados")
    st.dataframe(cargar_proveedores_gastos(), use_container_width=True, hide_index=True)


# =====================================================================
# Adjuntar soportes y enviar
# =====================================================================
def _mostrar_mensajes_previos():
    """Muestra el resultado del último envío y avisos guardados antes de un rerun."""
    ss = st.session_state

    aviso = ss.pop(f"{_P}_aviso", None)
    if aviso:
        st.warning(aviso)

    resultado = ss.pop(f"{_P}_resultado", None)
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
    ss.setdefault(_P, {})  # {nit: [{"nombre": str, "bytes": bytes, "mes": int}, ...]}
    ss.setdefault(f"{_P}_uploader_n", 0)
    ss.setdefault(f"{_P}_sel_n", 0)
    cola = ss[_P]

    _mostrar_mensajes_previos()

    proveedores = cargar_proveedores_gastos()
    if proveedores.empty:
        st.info("Primero registra al menos un proveedor en la pestaña «Proveedores de gastos».")
        return

    por_nit = {str(r["nit"]): r for _, r in proveedores.iterrows()}
    opciones = {f"{r['nombre']} — {nit}": nit for nit, r in por_nit.items()}

    # ---------- 1. Adjuntar ----------
    st.subheader("1. Adjuntar soportes")
    st.caption(
        "Elige el mes y el proveedor, sube sus PDF (puedes subir varios) y agrégalos a la lista. "
        "Repite con cada proveedor. La lista se conserva mientras no recargues la página."
    )
    mes = st.selectbox(
        "Mes al que corresponde el pago",
        list(range(1, 13)),
        index=None,
        format_func=lambda m: MESES_ES[m],
        placeholder="Selecciona el mes",
        key=f"{_P}_mes",
    )
    elegido = st.selectbox(
        "Proveedor",
        list(opciones),
        index=None,
        placeholder="Selecciona un proveedor",
        key=f"{_P}_proveedor_{ss[f'{_P}_sel_n']}",
    )
    archivos = st.file_uploader(
        "PDF del soporte de pago",
        type=["pdf"],
        accept_multiple_files=True,
        key=f"{_P}_uploader_{ss[f'{_P}_uploader_n']}",
    )

    listo_para_agregar = bool(archivos) and mes is not None and elegido is not None
    if archivos and not listo_para_agregar:
        st.caption("Elige el mes y el proveedor para poder agregar los PDF.")

    if st.button("Agregar a la lista", key=f"{_P}_btn_agregar", disabled=not listo_para_agregar):
        nit = opciones[elegido]
        lista = cola.setdefault(nit, [])
        existentes = {(a["nombre"], len(a["bytes"])) for a in lista}
        repetidos = []
        for f in archivos:
            contenido = f.getvalue()
            if (f.name, len(contenido)) in existentes:
                repetidos.append(f.name)
                continue
            lista.append({"nombre": f.name, "bytes": contenido, "mes": mes})
            existentes.add((f.name, len(contenido)))
        if not lista:
            del cola[nit]
        if repetidos:
            ss[f"{_P}_aviso"] = "Ya estaban en la lista y no se agregaron de nuevo: " + ", ".join(repetidos)
        ss[f"{_P}_uploader_n"] += 1  # limpia el cargador de archivos
        ss[f"{_P}_sel_n"] += 1  # deja el proveedor en blanco otra vez (el mes se conserva)
        st.rerun()

    # ---------- 2. Lista de envío ----------
    st.divider()
    st.subheader("2. Lista de envío")

    if not cola:
        st.info("Aún no has adjuntado soportes.")
        return

    envios = []
    resumen = []
    for nit, lista in cola.items():
        proveedor = por_nit.get(nit)
        peso = sum(len(a["bytes"]) for a in lista)
        if proveedor is None:
            nombre, correo = nit, ""
            estado = "Proveedor no encontrado en el Sheet"
        else:
            nombre, correo = str(proveedor["nombre"]), str(proveedor["correo"]).strip()
            if not correo_valido(correo):
                estado = "Sin correo válido"
            elif peso > LIMITE_BYTES_ADJUNTOS:
                estado = f"Excede {_LIMITE_MB} MB"
            else:
                estado = ESTADO_LISTO
                envios.append({"nit": nit, "nombre": nombre, "correo": correo, "archivos": lista})
        resumen.append({
            "Proveedor": nombre,
            "NIT": nit,
            "Correo": correo,
            "Mes": ", ".join(MESES_ES[m] for m in sorted({a["mes"] for a in lista if a.get("mes")})),
            "Soportes": len(lista),
            "Peso (MB)": round(peso / 1024 / 1024, 2),
            "Estado": estado,
        })

    resumen.sort(key=lambda r: r["Proveedor"].lower())
    m1, m2, m3 = st.columns(3)
    m1.metric("Proveedores en la lista", len(resumen))
    m2.metric("Soportes adjuntos", sum(r["Soportes"] for r in resumen))
    m3.metric("Correos listos", len(envios))
    st.dataframe(pd.DataFrame(resumen), use_container_width=True, hide_index=True)

    if len(envios) < len(resumen):
        st.warning(
            "Los proveedores que no están «Listo para enviar» no recibirán correo ahora; "
            "corrige el problema o quita sus soportes."
        )

    # Detalle de archivos por proveedor, con opción de quitar
    for nit in sorted(cola, key=lambda n: str(por_nit[n]["nombre"]).lower() if n in por_nit else n):
        lista = cola[nit]
        titulo = por_nit[nit]["nombre"] if nit in por_nit else nit
        with st.expander(f"{titulo} — {len(lista)} soporte(s)"):
            for i, a in enumerate(lista):
                c1, c2 = st.columns([6, 1])
                c1.write(f"📄 {a['nombre']}  ·  {MESES_ES.get(a.get('mes'), 'sin mes')}  ·  {len(a['bytes']) / 1024:.0f} KB")
                if c2.button("Quitar", key=f"{_P}_quitar_{nit}_{i}"):
                    lista.pop(i)
                    if not lista:
                        del cola[nit]
                    st.rerun()

    # ---------- 3. Enviar ----------
    b1, b2 = st.columns([3, 1])
    enviar = b1.button(f"Enviar {len(envios)} correos", type="primary", disabled=not envios, key=f"{_P}_btn_enviar")
    if b2.button("Vaciar lista", key=f"{_P}_btn_vaciar"):
        ss[_P] = {}
        st.rerun()

    if enviar:
        with st.spinner("Enviando correos..."):
            resultados = enviar_soportes_proveedores(envios)

        ok = [e for e in envios if resultados.get(e["nit"], (False, ""))[0]]
        fallidos = [e for e in envios if not resultados.get(e["nit"], (False, ""))[0]]

        for e in ok:
            cola.pop(e["nit"], None)

        ss[f"{_P}_resultado"] = {
            "ok": [e["nombre"] for e in ok],
            "fallidos": [
                {
                    "Proveedor": e["nombre"],
                    "Correo": e["correo"],
                    "Error": resultados.get(e["nit"], (False, "Sin respuesta"))[1],
                }
                for e in fallidos
            ],
        }
        st.rerun()
