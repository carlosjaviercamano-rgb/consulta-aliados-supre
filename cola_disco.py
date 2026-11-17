"""
Cola de soportes (PDF) guardada en el disco del servidor.

Sirve para que la lista de envío de Soporte Particulares y Soportes Proveedores
no se pierda al recargar la página, cerrar el navegador o cerrar sesión.
Solo se borra al enviar (lo que salió bien), al quitar un archivo o al vaciar.

Límite conocido: en Streamlit Community Cloud el disco NO es permanente; si la
app se reinicia (git push, Reboot o cuando se duerme por inactividad) la cola
se pierde.

Estructura:
    .cola_soportes/<nombre_cola>/indice.json   -> {destinatario: [item, ...]}
    .cola_soportes/<nombre_cola>/<id>.pdf      -> contenido de cada archivo
    item = {"id", "nombre", "mes", "peso", "fecha"}

La carpeta .cola_soportes/ está en .gitignore: nunca se sube a GitHub.
"""

import json
import os
import threading
import uuid
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_COLAS = os.path.join(BASE_DIR, ".cola_soportes")

AVISO_COLA = (
    "La lista se guarda en el servidor: no se pierde al recargar la página ni al cerrar sesión. "
    "Se borra al enviar, al quitar o vaciar, o si la app se reinicia (por ejemplo, tras un git push)."
)

_candados: dict[str, threading.Lock] = {}
_candado_global = threading.Lock()


def _candado(nombre: str) -> threading.Lock:
    with _candado_global:
        return _candados.setdefault(nombre, threading.Lock())


class ColaSoportes:
    """Cola de PDF por destinatario (identificación o NIT), persistida en disco."""

    def __init__(self, nombre: str):
        self.nombre = nombre
        self.dir = os.path.join(DIR_COLAS, nombre)
        self.ruta_indice = os.path.join(self.dir, "indice.json")
        self._lock = _candado(nombre)

    # ---------- utilidades internas ----------
    def _ruta_pdf(self, item_id: str) -> str:
        return os.path.join(self.dir, f"{item_id}.pdf")

    def _leer_indice(self) -> dict:
        try:
            with open(self.ruta_indice, encoding="utf-8") as f:
                datos = json.load(f)
            return datos if isinstance(datos, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _guardar_indice(self, indice: dict) -> None:
        os.makedirs(self.dir, exist_ok=True)
        indice = {k: v for k, v in indice.items() if v}  # sin destinatarios vacíos
        temporal = self.ruta_indice + ".tmp"
        with open(temporal, "w", encoding="utf-8") as f:
            json.dump(indice, f, ensure_ascii=False, indent=1)
        os.replace(temporal, self.ruta_indice)  # escritura atómica

    def _borrar_pdf(self, item_id: str) -> None:
        try:
            os.remove(self._ruta_pdf(item_id))
        except FileNotFoundError:
            pass

    # ---------- lectura ----------
    def leer(self) -> dict[str, list[dict]]:
        """{destinatario: [item, ...]} solo con archivos que existen en disco (sin bytes)."""
        with self._lock:
            indice = self._leer_indice()
        limpio = {}
        for ident, items in indice.items():
            vivos = [dict(it) for it in items if os.path.exists(self._ruta_pdf(it["id"]))]
            if vivos:
                limpio[ident] = vivos
        return limpio

    def con_bytes(self, items: list[dict]) -> list[dict]:
        """Copia de los items con su contenido en 'bytes' (para enviar el correo)."""
        salida = []
        for it in items:
            with open(self._ruta_pdf(it["id"]), "rb") as f:
                salida.append({**it, "bytes": f.read()})
        return salida

    # ---------- escritura ----------
    def agregar(self, ident: str, archivos: list[tuple[str, bytes]], mes: int) -> list[str]:
        """
        Agrega PDF al destinatario. Un archivo con el mismo nombre y tamaño que
        ya esté en su lista no se repite. Devuelve los nombres omitidos.
        """
        ident = str(ident)
        repetidos = []
        with self._lock:
            os.makedirs(self.dir, exist_ok=True)
            indice = self._leer_indice()
            lista = indice.setdefault(ident, [])
            existentes = {(it["nombre"], it["peso"]) for it in lista}
            for nombre, contenido in archivos:
                if (nombre, len(contenido)) in existentes:
                    repetidos.append(nombre)
                    continue
                item_id = uuid.uuid4().hex
                with open(self._ruta_pdf(item_id), "wb") as f:
                    f.write(contenido)
                lista.append({
                    "id": item_id,
                    "nombre": nombre,
                    "mes": mes,
                    "peso": len(contenido),
                    "fecha": datetime.now().isoformat(timespec="seconds"),
                })
                existentes.add((nombre, len(contenido)))
            self._guardar_indice(indice)
        return repetidos

    def quitar(self, ident: str, item_id: str) -> None:
        """Quita un archivo de la lista de un destinatario."""
        with self._lock:
            indice = self._leer_indice()
            lista = indice.get(str(ident), [])
            indice[str(ident)] = [it for it in lista if it["id"] != item_id]
            self._guardar_indice(indice)
            self._borrar_pdf(item_id)

    def quitar_destinatario(self, ident: str) -> None:
        """Quita todos los archivos de un destinatario (p. ej. tras enviarle el correo)."""
        with self._lock:
            indice = self._leer_indice()
            for it in indice.pop(str(ident), []):
                self._borrar_pdf(it["id"])
            self._guardar_indice(indice)

    def vaciar(self) -> None:
        """Borra toda la cola (índice y PDF, incluidos huérfanos)."""
        with self._lock:
            if os.path.isdir(self.dir):
                for archivo in os.listdir(self.dir):
                    if archivo.endswith(".pdf") or archivo.startswith("indice.json"):
                        os.remove(os.path.join(self.dir, archivo))
