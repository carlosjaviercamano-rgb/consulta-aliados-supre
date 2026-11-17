"""
Página de inicio (bienvenida) de Supre Aliados.

- Se muestra al abrir la app: saludo, mensaje, carrusel de imágenes y accesos rápidos.
- La configuración es COMPARTIDA: vive en el repositorio, no en config.json (que es local
  de cada computador):
      assets/inicio/            -> las imágenes
      inicio_config.json        -> título, mensaje, orden y textos de las imágenes
  Se edita desde  Configuración -> Página de inicio  y, para que todos la vean,
  se suben los cambios a GitHub (git add assets/inicio inicio_config.json).
"""
import base64
import html
import io
import json
import os
import re
from datetime import datetime, timedelta, timezone

import streamlit as st
import streamlit.components.v1 as components

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
DIR_IMAGENES  = os.path.join(BASE_DIR, "assets", "inicio")
RUTA_CONFIG   = os.path.join(BASE_DIR, "inicio_config.json")

EXT_PERMITIDAS = ["png", "jpg", "jpeg", "webp", "gif"]
MAX_IMAGENES   = 8
MAX_MB_SUBIDA  = 8
ANCHO_MAX_PX   = 1600
ALTO_CARRUSEL  = 380

CONFIG_POR_DEFECTO = {
    "titulo": "Bienvenido a Supre Aliados",
    "mensaje": "Envío de facturas y soportes por correo a aliados y particulares. Elige un módulo en el menú lateral para empezar.",
    "mostrar_accesos": True,
    "fondo_burbujas": True,   # fondo azul con burbujas (interruptor general)
    "fondo_modulos": None,    # claves de módulos con fondo; None = todos (ver MODULOS_FONDO)
    "carrusel_segundos": 6,
    "imagenes": [],          # [{"archivo": "img_xxx.jpg", "titulo": "", "texto": ""}]
}

# Módulos donde puede aparecer el fondo de burbujas (Configuración queda siempre sin fondo para poder desactivarlo).
MODULOS_FONDO = {
    "inicio": "Inicio", "facturas": "Facturas Aliados", "particulares": "Soporte Particulares",
}

DESCRIPCIONES = {
    "facturas":     "Facturas de comisión por correo a cada aliado, filtradas por NIT",
    "particulares": "Acta de particulares y envío de soportes adjuntos por correo",
}


# ══════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN (lectura / escritura)
# ══════════════════════════════════════════════════════════════════════════
def _ruta_imagen(nombre):
    # solo el nombre del archivo: evita rutas fuera de assets/inicio
    return os.path.join(DIR_IMAGENES, os.path.basename(str(nombre)))


def cargar_config_inicio():
    cfg = json.loads(json.dumps(CONFIG_POR_DEFECTO))
    try:
        with open(RUTA_CONFIG, "r", encoding="utf-8") as f:
            guardada = json.load(f)
        if isinstance(guardada, dict):
            for k in ("titulo", "mensaje", "mostrar_accesos", "fondo_burbujas", "carrusel_segundos"):
                if k in guardada:
                    cfg[k] = guardada[k]
            fm = guardada.get("fondo_modulos")
            if isinstance(fm, list):
                cfg["fondo_modulos"] = [m for m in fm if m in MODULOS_FONDO]
            imgs = guardada.get("imagenes", [])
            if isinstance(imgs, list):
                cfg["imagenes"] = [
                    {"archivo": os.path.basename(str(i.get("archivo", ""))),
                     "titulo": str(i.get("titulo", "") or ""),
                     "texto":  str(i.get("texto", "") or "")}
                    for i in imgs if isinstance(i, dict) and i.get("archivo")
                ]
    except (OSError, ValueError):
        pass
    try:
        cfg["carrusel_segundos"] = max(2, min(30, int(cfg["carrusel_segundos"])))
    except (TypeError, ValueError):
        cfg["carrusel_segundos"] = 6
    return cfg


def _imagenes_existentes(cfg):
    """Imágenes de la configuración cuyo archivo sí está en la carpeta."""
    return [i for i in cfg["imagenes"] if os.path.isfile(_ruta_imagen(i["archivo"]))]


def guardar_config_inicio(cfg):
    """Guarda inicio_config.json y borra de assets/inicio las imágenes que ya no se usan."""
    os.makedirs(DIR_IMAGENES, exist_ok=True)
    limpia = {
        "titulo": str(cfg.get("titulo", "")).strip(),
        "mensaje": str(cfg.get("mensaje", "")).strip(),
        "mostrar_accesos": bool(cfg.get("mostrar_accesos", True)),
        "fondo_burbujas": bool(cfg.get("fondo_burbujas", True)),
        "fondo_modulos": [m for m in (cfg.get("fondo_modulos") or list(MODULOS_FONDO)) if m in MODULOS_FONDO],
        "carrusel_segundos": int(cfg.get("carrusel_segundos", 6)),
        "imagenes": [
            {"archivo": os.path.basename(i["archivo"]),
             "titulo": str(i.get("titulo", "")).strip(),
             "texto": str(i.get("texto", "")).strip()}
            for i in cfg.get("imagenes", []) if os.path.isfile(_ruta_imagen(i["archivo"]))
        ],
    }
    tmp = RUTA_CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(limpia, f, ensure_ascii=False, indent=2)
    os.replace(tmp, RUTA_CONFIG)

    usadas = {i["archivo"] for i in limpia["imagenes"]}
    for nombre in os.listdir(DIR_IMAGENES):
        if nombre.startswith("img_") and nombre not in usadas:
            try:
                os.remove(os.path.join(DIR_IMAGENES, nombre))
            except OSError:
                pass
    return limpia


def procesar_y_guardar_imagen(nombre_original, contenido):
    """
    Valida la imagen, la ajusta (máx. 1600 px de ancho) y la comprime para que el repositorio
    no engorde. Devuelve el nombre del archivo guardado en assets/inicio.
    """
    from PIL import Image, ImageOps

    if len(contenido) > MAX_MB_SUBIDA * 1024 * 1024:
        raise ValueError(f"«{nombre_original}» pesa más de {MAX_MB_SUBIDA} MB.")
    try:
        img = Image.open(io.BytesIO(contenido))
        img.load()
    except Exception:
        raise ValueError(f"«{nombre_original}» no es una imagen válida.")
    img = ImageOps.exif_transpose(img)

    if img.width > ANCHO_MAX_PX:
        alto = round(img.height * ANCHO_MAX_PX / img.width)
        img = img.resize((ANCHO_MAX_PX, alto), Image.LANCZOS)

    tiene_alfa = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    os.makedirs(DIR_IMAGENES, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d%H%M%S%f")
    base = re.sub(r"[^a-z0-9]+", "-", os.path.splitext(nombre_original)[0].lower()).strip("-")[:24] or "imagen"
    if tiene_alfa:
        nombre = f"img_{marca}_{base}.png"
        img.convert("RGBA").save(_ruta_imagen(nombre), format="PNG", optimize=True)
    else:
        nombre = f"img_{marca}_{base}.jpg"
        img.convert("RGB").save(_ruta_imagen(nombre), format="JPEG", quality=82, optimize=True)
    return nombre


# ══════════════════════════════════════════════════════════════════════════
# PÁGINA DE INICIO
# ══════════════════════════════════════════════════════════════════════════
def _saludo():
    hora = datetime.now(timezone(timedelta(hours=-5))).hour       # hora de Colombia
    if hora < 12:
        return "Buenos días"
    if hora < 19:
        return "Buenas tardes"
    return "Buenas noches"


@st.cache_data(show_spinner=False)
def _imagen_base64(ruta, mtime):
    with open(ruta, "rb") as f:
        datos = base64.b64encode(f.read()).decode("ascii")
    mime = "image/png" if ruta.lower().endswith(".png") else "image/jpeg"
    return f"data:{mime};base64,{datos}"


def _html_carrusel(imagenes, segundos, translucido=False):
    slides = []
    for n, i in enumerate(imagenes):
        ruta = _ruta_imagen(i["archivo"])
        src = _imagen_base64(ruta, os.path.getmtime(ruta))
        cap = ""
        if i.get("titulo") or i.get("texto"):
            cap = ('<div class="cap">' +
                   (f'<b>{html.escape(i["titulo"])}</b>' if i.get("titulo") else "") +
                   (f'<span>{html.escape(i["texto"])}</span>' if i.get("texto") else "") + "</div>")
        slides.append(f'<div class="slide{" on" if n == 0 else ""}"><img src="{src}" alt="">{cap}</div>')
    # Burbujas decorativas (posiciones/tamaños fijos para que no cambien en cada recarga)
    burbujas = "".join(
        f'<b style="left:{x}%;width:{d}px;height:{d}px;animation-duration:{t}s;animation-delay:-{r}s;'
        f'--dx:{dx}px"></b>'
        for x, d, t, r, dx in (
            (3, 46, 17, 2, 18), (7, 18, 12, 9, -14), (11, 72, 24, 5, 26), (16, 28, 15, 11, -10),
            (21, 14, 11, 4, 12), (27, 54, 21, 14, -22), (73, 36, 18, 7, 16), (78, 16, 13, 1, -12),
            (83, 80, 26, 12, -28), (88, 24, 14, 8, 14), (92, 50, 20, 3, -18), (96, 20, 12, 10, 10),
            (69, 22, 16, 15, -16), (35, 12, 10, 6, 8), (62, 12, 10, 13, -8),
        ))
    fx_display = "none" if translucido else "block"
    css_trans = (".car{background:rgba(255,255,255,.03)!important;border:1px solid rgba(147,197,253,.22);"
                 "box-shadow:none!important}") if translucido else ""
    varias = len(imagenes) > 1
    controles = ""
    if varias:
        controles = ('<button class="nav prev" aria-label="Anterior">&#10094;</button>'
                     '<button class="nav next" aria-label="Siguiente">&#10095;</button>'
                     '<div class="dots">' + "".join(f'<i class="{"on" if n == 0 else ""}"></i>'
                                                    for n in range(len(imagenes))) + "</div>")
    return f"""
<style>
  html,body{{margin:0;background:transparent;font-family:Inter,system-ui,Segoe UI,Arial,sans-serif}}
  {css_trans}
  .car{{position:relative;height:{ALTO_CARRUSEL - 16}px;border-radius:14px;overflow:hidden;
        background:linear-gradient(135deg,#0f2447 0%,#1e3a5f 48%,#1e40af 100%);
        box-shadow:0 2px 8px rgba(15,23,42,.22)}}
  .fx{{position:absolute;inset:0;overflow:hidden;pointer-events:none;display:{fx_display}}}
  .fx::before,.fx::after{{content:"";position:absolute;width:340px;height:340px;border-radius:50%;
        background:radial-gradient(circle,rgba(96,165,250,.30),rgba(96,165,250,0) 68%);
        animation:orb 18s ease-in-out infinite alternate}}
  .fx::before{{left:-90px;top:-70px}}
  .fx::after{{right:-90px;bottom:-110px;animation-duration:23s;animation-direction:alternate-reverse}}
  .fx b{{position:absolute;bottom:-100px;display:block;border-radius:50%;
        background:radial-gradient(circle at 30% 28%,rgba(255,255,255,.34),rgba(147,197,253,.10) 46%,rgba(147,197,253,.04) 70%);
        border:1px solid rgba(191,219,254,.30);box-shadow:inset 0 0 10px rgba(255,255,255,.08);
        animation:subir linear infinite}}
  @keyframes subir{{0%{{transform:translate(0,0) scale(.9);opacity:0}} 12%{{opacity:1}}
        50%{{transform:translate(var(--dx),-210px) scale(1)}}
        88%{{opacity:.9}} 100%{{transform:translate(calc(var(--dx) * -.6),-520px) scale(1.08);opacity:0}}}}
  @keyframes orb{{from{{transform:translate(0,0)}} to{{transform:translate(70px,40px)}}}}
  @media (prefers-reduced-motion:reduce){{.fx b,.fx::before,.fx::after{{animation:none}}}}
  .slide{{position:absolute;inset:0;opacity:0;transition:opacity .7s ease}}
  .slide.on{{opacity:1}}
  .slide img{{position:absolute;top:0;left:50%;transform:translateX(-50%);height:100%;width:auto;max-width:100%;display:block}}
  .car.lb .slide img{{-webkit-mask-image:linear-gradient(90deg,transparent,#000 5%,#000 95%,transparent);
        mask-image:linear-gradient(90deg,transparent,#000 5%,#000 95%,transparent)}}
  .cap{{position:absolute;left:0;right:0;bottom:0;padding:34px 26px 20px;color:#fff;
        background:linear-gradient(to top,rgba(10,20,40,.82),rgba(10,20,40,0))}}
  .cap b{{display:block;font-size:1.35rem;margin-bottom:2px}}
  .cap span{{font-size:.95rem;opacity:.92}}
  .nav{{position:absolute;top:50%;transform:translateY(-50%);border:0;width:38px;height:38px;border-radius:50%;
        background:rgba(15,23,42,.55);color:#fff;font-size:16px;cursor:pointer;opacity:0;transition:.2s}}
  .car:hover .nav{{opacity:1}} .nav:hover{{background:rgba(30,64,175,.9)}}
  .prev{{left:12px}} .next{{right:12px}}
  .dots{{position:absolute;right:16px;top:14px;display:flex;gap:6px}}
  .dots i{{width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,.5);display:block;cursor:pointer}}
  .dots i.on{{background:#fff;transform:scale(1.25)}}
</style>
<div class="car" id="car"><div class="fx">{burbujas}</div>{''.join(slides)}{controles}</div>
<script>
(function(){{
  var car=document.getElementById('car'), slides=car.querySelectorAll('.slide'),
      dots=car.querySelectorAll('.dots i'), n=slides.length, k=0, t=null, ms={int(segundos) * 1000};
  function show(i){{
    k=(i+n)%n;
    for(var j=0;j<n;j++){{ slides[j].classList.toggle('on',j===k); if(dots[j]) dots[j].classList.toggle('on',j===k); }}
    fit();
  }}
  function play(){{ if(n>1){{ clearInterval(t); t=setInterval(function(){{show(k+1)}}, ms); }} }}
  function stop(){{ clearInterval(t); }}
  function fit(){{ var im=car.querySelector('.slide.on img'); car.classList.toggle('lb', !!im && im.getBoundingClientRect().width < car.clientWidth - 4); }}
  slides.forEach(function(s){{ var im=s.querySelector('img'); if(im) im.addEventListener('load',fit); }});
  window.addEventListener('resize',fit); fit(); setTimeout(fit,300);
  var p=car.querySelector('.prev'), x=car.querySelector('.next');
  if(p) p.onclick=function(){{show(k-1);play()}};
  if(x) x.onclick=function(){{show(k+1);play()}};
  dots.forEach(function(d,j){{ d.onclick=function(){{show(j);play()}}; }});
  car.onmouseenter=stop; car.onmouseleave=play;
  play();
}})();
</script>"""


# ══════════════════════════════════════════════════════════════════════════
# PANEL ANIMADO DE MÓDULOS (reemplaza a los "accesos rápidos")
# ══════════════════════════════════════════════════════════════════════════
_ARTE = {
    # Facturas Aliados: una factura entra al sobre y aparece la marca de enviado
    "facturas": '''<svg viewBox="0 0 160 90"><rect class="paper" x="38" y="38" width="84" height="46" rx="7"/>
      <g class="inv"><rect x="58" y="6" width="44" height="52" rx="5" fill="#fff" stroke="#93c5fd" stroke-width="1.5"/>
        <rect class="ln2" x="65" y="15" width="30" height="5" rx="2.5"/><rect class="ln2" x="65" y="26" width="22" height="5" rx="2.5"/>
        <rect class="ln2" x="65" y="37" width="26" height="5" rx="2.5"/><circle cx="92" cy="47" r="6" fill="#fbbf24"/></g>
      <polygon class="col" points="38,38 80,66 122,38 122,84 38,84"/><polygon class="flap" points="38,38 80,64 122,38"/>
      <g class="okb"><circle cx="122" cy="40" r="11" fill="#10b981"/><path d="M116 40l4.4 4.4 8-8.4" fill="none" stroke="#fff" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/></g></svg>''',
    # Soporte Particulares: documentos que se abren en abanico y un clip que los sujeta
    "particulares": '''<svg viewBox="0 0 160 90"><g class="doc d1"><rect x="48" y="14" width="46" height="62" rx="5"/></g>
      <g class="doc d2"><rect x="48" y="14" width="46" height="62" rx="5"/></g>
      <g class="doc d3"><rect x="48" y="14" width="46" height="62" rx="5"/><rect class="ln2" x="56" y="26" width="30" height="5" rx="2.5"/><rect class="ln2" x="56" y="37" width="24" height="5" rx="2.5"/><rect class="ln2" x="56" y="48" width="28" height="5" rx="2.5"/></g>
      <path class="clip" d="M104 8v36a9 9 0 0 1-18 0V14a6 6 0 0 1 12 0v28a3 3 0 0 1-6 0V18"/>
      <g class="mail"><circle cx="124" cy="62" r="13" fill="#2563eb"/><path d="M117 58h14v9h-14z M117 58l7 5.5 7-5.5" fill="none" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/></g></svg>''',
}

_CSS_PANEL = '''
html,body{margin:0;background:transparent;font-family:Inter,system-ui,"Segoe UI",Arial,sans-serif;overflow-x:hidden}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px;padding:4px 2px 10px}
.card{position:relative;overflow:hidden;border-radius:16px;padding:14px 16px 16px;color:#fff;
  background:linear-gradient(145deg,#0f2447 0%,#1e3a8a 100%);border:1px solid rgba(147,197,253,.22);
  box-shadow:0 2px 8px rgba(15,23,42,.22);opacity:0;animation:entra .6s ease forwards;animation-delay:var(--d);
  transition:transform .25s ease,box-shadow .25s ease,border-color .25s ease}
.card:hover{transform:translateY(-5px);box-shadow:0 12px 26px rgba(30,64,175,.38);border-color:rgba(147,197,253,.55)}
.card::before{content:"";position:absolute;right:-60px;top:-60px;width:170px;height:170px;border-radius:50%;
  background:radial-gradient(circle,rgba(96,165,250,.30),rgba(96,165,250,0) 68%);animation:orb 9s ease-in-out infinite alternate}
.art{position:relative;height:118px;display:flex;align-items:center;justify-content:center;
  background:rgba(255,255,255,.06);border-radius:12px;margin-bottom:12px}
.art svg{height:100%;width:auto;max-width:100%;overflow:visible}
.emo{font-size:3rem}
h3{position:relative;margin:0 0 4px;font-size:1.05rem;font-weight:700}
p{position:relative;margin:0;font-size:.86rem;line-height:1.35;color:#bfdbfe}
@keyframes entra{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@keyframes orb{from{transform:translate(0,0)}to{transform:translate(-30px,24px)}}
/* ilustraciones */
svg .paper{fill:#f1f5f9}svg .col{fill:#dbeafe}svg .btn{fill:#3b82f6}svg .ln,svg .ln2{fill:#93c5fd}
svg .lbl{fill:#bfdbfe;font-size:8px;font-weight:700;letter-spacing:.06em}
svg .lbl2{fill:#1e3a8a;font-size:10px;font-weight:800}
svg .ln{transform-box:fill-box;transform-origin:left center;animation:llena 4s ease-in-out infinite}
@keyframes llena{0%{transform:scaleX(.05)}35%,85%{transform:scaleX(1)}100%{transform:scaleX(.05)}}
svg .coin circle{fill:#fbbf24;stroke:#f59e0b;stroke-width:2}svg .coin text{fill:#92400e;font-size:11px;font-weight:800}
svg .coin{opacity:0;animation:moneda 2.6s ease-in infinite}
@keyframes moneda{0%{transform:translate(20px,16px);opacity:0}15%{opacity:1}70%{transform:translate(62px,46px);opacity:1}100%{transform:translate(66px,46px) scale(.3);opacity:0}}
svg .file rect:first-child{fill:#fff}svg .file{opacity:0;animation:sube 3s ease-in-out infinite}
@keyframes sube{0%{transform:translateY(22px) scale(1);opacity:0}20%{opacity:1}70%{transform:translateY(-12px) scale(.85);opacity:1}100%{transform:translateY(-22px) scale(.5);opacity:0}}
svg .link{stroke:#60a5fa;stroke-width:2.5;stroke-linecap:round;stroke-dasharray:44;stroke-dashoffset:44;animation:traza 3.6s ease-in-out infinite}
@keyframes traza{0%{stroke-dashoffset:44}25%,85%{stroke-dashoffset:0}100%{stroke-dashoffset:44}}
svg .ok{transform-box:fill-box;transform-origin:center;opacity:0;animation:pop 3.6s ease-in-out infinite}
svg .ok circle{fill:#10b981}svg .ok path{fill:none;stroke:#fff;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
@keyframes pop{0%,15%{opacity:0;transform:scale(.2)}28%{opacity:1;transform:scale(1.15)}34%,85%{opacity:1;transform:scale(1)}100%{opacity:0;transform:scale(.2)}}
svg .axis{stroke:#93c5fd;stroke-width:1.5}svg .bar{fill:#60a5fa;transform-box:fill-box;transform-origin:bottom;animation:crece 3.2s ease-in-out infinite}
@keyframes crece{0%{transform:scaleY(.15)}30%,80%{transform:scaleY(1)}100%{transform:scaleY(.15)}}
svg .trend{fill:none;stroke:#34d399;stroke-width:3;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:140;stroke-dashoffset:140;animation:traza2 3.2s ease-in-out infinite}
@keyframes traza2{0%,10%{stroke-dashoffset:140}55%,85%{stroke-dashoffset:0}100%{stroke-dashoffset:140}}
svg .dot{fill:#34d399;opacity:0;animation:punto 3.2s ease-in-out infinite}
@keyframes punto{0%,50%{opacity:0}60%,85%{opacity:1}100%{opacity:0}}
svg .xl{fill:#f1f5f9}svg .xh{fill:#10b981}svg .gl{stroke:#cbd5e1;stroke-width:1}
svg .arrow{fill:none;stroke:#93c5fd;stroke-width:3;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:3 5;animation:flujo 1s linear infinite}
@keyframes flujo{to{stroke-dashoffset:-8}}
svg .pk{fill:#fbbf24;opacity:0;animation:viaja 1.8s ease-in-out infinite}
@keyframes viaja{0%{transform:translateX(-4px) scale(.6);opacity:0}20%{opacity:1}80%{opacity:1}100%{transform:translateX(46px) scale(.6);opacity:0}}
svg .box{fill:#fff;stroke:#93c5fd;stroke-width:1.8}
svg .tick{fill:none;stroke:#10b981;stroke-width:2.6;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:18;stroke-dashoffset:18;animation:marca 3.6s ease-in-out infinite}
@keyframes marca{0%,8%{stroke-dashoffset:18}22%,88%{stroke-dashoffset:0}100%{stroke-dashoffset:18}}
@media (prefers-reduced-motion:reduce){.card,.card::before,svg *{animation:none!important}.card{opacity:1}svg .ln,svg .ok,svg .link,svg .tick,svg .trend,svg .dot{opacity:1;transform:none;stroke-dashoffset:0}svg .coin,svg .file,svg .pk{opacity:0}}
svg .flap{fill:#bfdbfe}
svg .inv{animation:entraSobre 4s ease-in-out infinite}
@keyframes entraSobre{0%{transform:translateY(-6px);opacity:0}15%{opacity:1}55%,100%{transform:translateY(34px);opacity:1}}
svg .okb{transform-box:fill-box;transform-origin:center;opacity:0;animation:popOk 4s ease-in-out infinite}
@keyframes popOk{0%,55%{opacity:0;transform:scale(.2)}68%{opacity:1;transform:scale(1.2)}76%,92%{opacity:1;transform:scale(1)}100%{opacity:0;transform:scale(.2)}}
svg .doc rect:first-child{fill:#f1f5f9;stroke:#cbd5e1;stroke-width:1}
svg .doc{transform-box:fill-box;transform-origin:50% 90%;animation:abanico 4.2s ease-in-out infinite}
svg .d1{--r:-16deg}svg .d2{--r:-7deg;animation-delay:.12s}svg .d3{--r:3deg;animation-delay:.24s}
@keyframes abanico{0%,10%{transform:rotate(0)}40%,80%{transform:rotate(var(--r))}100%{transform:rotate(0)}}
svg .clip{fill:none;stroke:#fbbf24;stroke-width:3.2;stroke-linecap:round;stroke-linejoin:round;transform-box:fill-box;transform-origin:50% 100%;animation:clip 4.2s ease-in-out infinite}
@keyframes clip{0%,100%{transform:rotate(-6deg)}50%{transform:rotate(7deg)}}
svg .mail{transform-box:fill-box;transform-origin:center;animation:latido 4.2s ease-in-out infinite}
@keyframes latido{0%,100%{transform:scale(1)}50%{transform:scale(1.12)}}
'''


def _html_panel_modulos(modulos, translucido=False):
    tarjetas = []
    for n, (clave, icono, etiqueta) in enumerate(modulos):
        arte = _ARTE.get(clave) or f'<div class="emo">{html.escape(icono)}</div>'
        desc = html.escape(DESCRIPCIONES.get(clave, ""))
        tarjetas.append(f'<div class="card" style="--d:{n * 0.09:.2f}s"><div class="art">{arte}</div>'
                        f'<h3>{html.escape(etiqueta)}</h3><p>{desc}</p></div>')
    extra = ".card{background:linear-gradient(145deg,rgba(15,36,71,.78),rgba(30,58,138,.78))}" if translucido else ""
    return f'<style>{_CSS_PANEL}{extra}</style><div class="grid">{"".join(tarjetas)}</div>'


# ══════════════════════════════════════════════════════════════════════════
# FONDO DE BURBUJAS (solo en la página de inicio)
# ══════════════════════════════════════════════════════════════════════════
# (izquierda %, diámetro px, duración s, desfase s, deriva px)
_BURBUJAS_FONDO = (
    (3, 46, 26, 2, 24), (6, 90, 34, 9, -30), (10, 18, 19, 14, 14), (14, 62, 29, 5, 26), (19, 28, 22, 18, -16),
    (24, 110, 38, 11, 30), (29, 16, 17, 3, -12), (34, 40, 25, 21, 20), (40, 24, 20, 7, -18), (45, 76, 33, 16, 28),
    (50, 14, 18, 1, 10), (55, 52, 27, 24, -24), (60, 30, 22, 12, 16), (65, 96, 36, 6, -32), (70, 20, 19, 19, 12),
    (75, 58, 28, 4, 22), (80, 34, 23, 15, -20), (84, 84, 35, 10, 30), (88, 22, 20, 22, -14), (92, 48, 26, 8, 18),
    (96, 68, 31, 13, -26), (98, 16, 18, 17, 10), (37, 12, 16, 26, 8), (67, 12, 17, 28, -8),
)


def fondo_activo(modulo, cfg=None):
    """True si el fondo de burbujas debe verse en ese módulo."""
    cfg = cfg or cargar_config_inicio()
    activos = cfg.get("fondo_modulos")
    if activos is None:
        activos = list(MODULOS_FONDO)
    return bool(cfg.get("fondo_burbujas")) and modulo in activos and modulo in MODULOS_FONDO


def _tema_streamlit():
    """'dark', 'light' o None si esta versión de Streamlit no lo informa."""
    try:
        t = getattr(st.context, "theme", None)
        return getattr(t, "type", None) if t is not None else None
    except Exception:
        return None


def _html_fondo_burbujas(panel=False):
    """Capa fija detrás del contenido: degradado azul + burbujas translúcidas que suben.
    panel=False (Inicio): el contenido va directo sobre el fondo, con textos claros.
    panel=True (demás módulos): el contenido va dentro de un panel sólido (oscuro o claro según el tema),
    así tablas, formularios y gráficos se ven exactamente igual que sin fondo."""
    b = "".join(f'<i style="left:{x}%;width:{d}px;height:{d}px;animation-duration:{t}s;animation-delay:-{r}s;--dx:{dx}px"></i>'
                for x, d, t, r, dx in _BURBUJAS_FONDO)
    css = (
        '.stApp{background:linear-gradient(135deg,#0a1630 0%,#10285a 50%,#1b3a9c 100%)!important;isolation:isolate}'
        '[data-testid="stHeader"]{background:transparent!important}'
        '[data-testid="stMain"] .block-container{isolation:isolate}'
        '.fondo-burbujas{position:fixed;inset:0;z-index:-1;overflow:hidden;pointer-events:none}'
        '.fondo-burbujas::before,.fondo-burbujas::after{content:"";position:absolute;width:560px;height:560px;border-radius:50%;'
        'background:radial-gradient(circle,rgba(96,165,250,.30),rgba(96,165,250,0) 68%);animation:fbOrb 22s ease-in-out infinite alternate}'
        '.fondo-burbujas::before{left:-120px;top:8%}'
        '.fondo-burbujas::after{right:-140px;bottom:-160px;animation-duration:28s;animation-direction:alternate-reverse}'
        '.fondo-burbujas i{position:absolute;bottom:-130px;display:block;border-radius:50%;'
        'background:radial-gradient(circle at 30% 28%,rgba(255,255,255,.30),rgba(147,197,253,.10) 46%,rgba(147,197,253,.03) 70%);'
        'border:1px solid rgba(191,219,254,.28);animation:fbSube linear infinite}'
        '@keyframes fbSube{0%{transform:translate(0,0);opacity:0}10%{opacity:1}'
        '50%{transform:translate(var(--dx),-60vh)}88%{opacity:.9}'
        '100%{transform:translate(calc(var(--dx) * -.6),-125vh);opacity:0}}'
        '@keyframes fbOrb{from{transform:translate(0,0)}to{transform:translate(110px,60px)}}'
        '@media (prefers-reduced-motion:reduce){.fondo-burbujas i,.fondo-burbujas::before,.fondo-burbujas::after{animation:none}}'
    )
    if not panel:
        css += ('[data-testid="stMain"] .stMarkdown p,[data-testid="stMain"] .stMarkdown h4,'
                '[data-testid="stMain"] [data-testid="stCaptionContainer"]{color:#e2e8f0!important}')
    else:
        base = ('[data-testid="stMain"] .block-container{border:1px solid rgba(147,197,253,.22);border-radius:16px;'
                'padding:2rem 2.2rem 2.6rem!important;margin:1.2rem auto 1.6rem!important;'
                'width:calc(100% - 2.6rem)!important;max-width:none!important;min-height:calc(100vh - 2.8rem);'
                'flex:0 0 auto!important;height:auto!important;box-sizing:border-box;'
                'box-shadow:0 10px 40px rgba(2,6,23,.35);__BG__}')
        oscuro, claro = "background:rgba(11,18,32,.985)", "background:rgba(255,255,255,.985)"
        tema = _tema_streamlit()
        if tema == "dark":
            css += base.replace("__BG__", oscuro)
        elif tema == "light":
            css += base.replace("__BG__", claro)
        else:  # versión sin st.context.theme: se guía por el modo del sistema
            css += (base.replace("__BG__", claro) + "@media (prefers-color-scheme:dark){"
                    + base.replace("__BG__", oscuro) + "}")
    return f'<style>{css}</style><div class="fondo-burbujas">{b}</div>'


def render_fondo(modulo):
    """Se llama desde app.py antes de dibujar el módulo activo (no hace nada si el fondo está apagado)."""
    if modulo != "config" and fondo_activo(modulo):
        st.markdown(_html_fondo_burbujas(panel=(modulo != "inicio")), unsafe_allow_html=True)


def render(config=None, modulos=None):
    """
    modulos: lista de (clave, icono, nombre) de los módulos del menú, para las tarjetas de
    acceso rápido. Al hacer clic se cambia st.session_state.modulo.
    """
    cfg = cargar_config_inicio()
    fondo = fondo_activo("inicio", cfg)   # el fondo en sí lo dibuja render_fondo() desde app.py
    nombre = (st.session_state.get("name") or "").strip()
    primer_nombre = nombre.split()[0] if nombre else ""
    saludo = f"{_saludo()}, {primer_nombre}" if primer_nombre else _saludo()   # sin nombre: solo el saludo

    from ui import encabezado   # banner azul de módulo de esta app
    encabezado("🏠", f"{saludo} 👋", cfg["titulo"])

    if cfg["mensaje"]:
        st.markdown(f"<p style='font-size:1.02rem;margin:0 0 1rem 0'>{html.escape(cfg['mensaje'])}</p>",
                    unsafe_allow_html=True)

    imagenes = _imagenes_existentes(cfg)
    if imagenes:
        components.html(_html_carrusel(imagenes, cfg["carrusel_segundos"], translucido=fondo), height=ALTO_CARRUSEL)
    else:
        pass   # sin imágenes no se muestra carrusel (se agregan en Configuración → Página de inicio)

    if cfg["mostrar_accesos"] and modulos:
        st.markdown("#### ¿Qué puedes hacer aquí?")
        filas = -(-len(modulos) // 3)
        components.html(_html_panel_modulos(modulos, translucido=fondo), height=filas * 236 + (filas - 1) * 14 + 16, scrolling=True)
        st.caption("Entra a cada módulo desde el menú de la izquierda.")


# ══════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN (se muestra dentro de la página Configuración)
# ══════════════════════════════════════════════════════════════════════════
_EST = "inicio_cfg_edicion"


def _estado_edicion():
    if _EST not in st.session_state:
        st.session_state[_EST] = cargar_config_inicio()
        st.session_state["inicio_uploader_n"] = st.session_state.get("inicio_uploader_n", 0)
    return st.session_state[_EST]


def render_configuracion():
    ed = _estado_edicion()

    st.markdown("### 🏠 Página de inicio")
    st.caption(
        "Es la pantalla de bienvenida que ven todos los usuarios al abrir la app. Esta configuración es "
        "**compartida**: se guarda en la carpeta `assets/inicio` y en `inicio_config.json` del proyecto. "
        "Después de guardar, sube los cambios a GitHub para que todos los vean."
    )

    c1, c2 = st.columns([2, 3])
    with c1:
        ed["titulo"] = st.text_input("Título de bienvenida", value=ed["titulo"], key="inicio_in_titulo")
        ed["carrusel_segundos"] = int(st.number_input(
            "Segundos por imagen", min_value=2, max_value=30, value=int(ed["carrusel_segundos"]),
            step=1, key="inicio_in_seg"))
        ed["mostrar_accesos"] = st.checkbox("Mostrar el panel animado de módulos",
                                            value=bool(ed["mostrar_accesos"]), key="inicio_in_acc")
        ed["fondo_burbujas"] = st.checkbox("Fondo azul con burbujas animadas",
                                           value=bool(ed["fondo_burbujas"]), key="inicio_in_fondo")
        if ed["fondo_burbujas"]:
            sel = ed.get("fondo_modulos")
            ed["fondo_modulos"] = st.multiselect(
                "Módulos que muestran el fondo", options=list(MODULOS_FONDO),
                default=list(MODULOS_FONDO) if sel is None else [m for m in sel if m in MODULOS_FONDO],
                format_func=lambda k: MODULOS_FONDO[k], key="inicio_in_fmod",
                help="En los módulos de trabajo el contenido va sobre un panel sólido para que tablas y formularios se lean igual.")
    with c2:
        ed["mensaje"] = st.text_area("Mensaje", value=ed["mensaje"], height=125, key="inicio_in_msg")

    st.markdown("**Imágenes de bienvenida**")
    st.caption(f"Tamaño recomendado: 1600 × 620 px (horizontal). Se ven completas, sin recortes, y si la "
               f"proporción es otra los lados se rellenan con un fondo azul con burbujas animadas. Se ajustan a un máximo de {ANCHO_MAX_PX} px "
               f"de ancho y se comprimen. Hasta {MAX_IMAGENES} imágenes de {MAX_MB_SUBIDA} MB cada una; "
               "se ven en el orden de esta lista.")

    imgs = ed["imagenes"]
    for n, i in enumerate(list(imgs)):
        existe = os.path.isfile(_ruta_imagen(i["archivo"]))
        k = f"{n}_{i['archivo']}"
        col_img, col_txt, col_btn = st.columns([2, 4, 1])
        with col_img:
            if existe:
                st.image(_ruta_imagen(i["archivo"]), use_container_width=True)
            else:
                st.warning("Archivo no encontrado")
        with col_txt:
            i["titulo"] = st.text_input("Título (opcional)", value=i.get("titulo", ""), key=f"inicio_t_{k}")
            i["texto"] = st.text_input("Texto (opcional)", value=i.get("texto", ""), key=f"inicio_x_{k}")
        with col_btn:
            if st.button("⬆️", key=f"inicio_up_{k}", disabled=n == 0, help="Subir"):
                imgs[n - 1], imgs[n] = imgs[n], imgs[n - 1]
                st.rerun()
            if st.button("⬇️", key=f"inicio_dn_{k}", disabled=n == len(imgs) - 1, help="Bajar"):
                imgs[n + 1], imgs[n] = imgs[n], imgs[n + 1]
                st.rerun()
            if st.button("🗑️", key=f"inicio_rm_{k}", help="Quitar (se borra al guardar)"):
                imgs.pop(n)
                st.rerun()

    if not imgs:
        st.info("Todavía no hay imágenes. Agrega la primera con el cuadro de abajo.")

    cupo = MAX_IMAGENES - len(imgs)
    subidas = st.file_uploader(
        "Agregar imágenes", type=EXT_PERMITIDAS, accept_multiple_files=True,
        key=f"inicio_uploader_{st.session_state.get('inicio_uploader_n', 0)}",
        disabled=cupo <= 0,
        help="PNG, JPG, WEBP o GIF (de los GIF se usa el primer cuadro)."
    )
    if cupo <= 0:
        st.warning(f"Ya tienes el máximo de {MAX_IMAGENES} imágenes. Quita alguna para agregar otra.")
    if subidas and st.button("➕  Agregar a la lista", key="inicio_btn_agregar"):
        errores, agregadas = [], 0
        for f in subidas[:max(cupo, 0)]:
            try:
                imgs.append({"archivo": procesar_y_guardar_imagen(f.name, f.getvalue()), "titulo": "", "texto": ""})
                agregadas += 1
            except Exception as e:
                errores.append(str(e))
        if len(subidas) > cupo:
            errores.append(f"Solo caben {MAX_IMAGENES} imágenes: se omitieron {len(subidas) - cupo}.")
        st.session_state["inicio_uploader_n"] = st.session_state.get("inicio_uploader_n", 0) + 1
        st.session_state["inicio_msg"] = (agregadas, errores)
        st.rerun()

    msg = st.session_state.pop("inicio_msg", None)
    if msg:
        agregadas, errores = msg
        if agregadas:
            st.success(f"✅ {agregadas} imagen(es) agregada(s). Recuerda guardar la página de inicio.")
        for e in errores:
            st.error(f"❌ {e}")

    b1, b2, _ = st.columns([2, 2, 3])
    with b1:
        if st.button("💾  Guardar página de inicio", type="primary", key="inicio_btn_guardar",
                     use_container_width=True):
            try:
                st.session_state[_EST] = guardar_config_inicio(ed)
                st.session_state["inicio_guardado"] = True
                st.rerun()
            except Exception as e:
                st.error(f"❌ No se pudo guardar: {e}")
    with b2:
        if st.button("↩️  Descartar cambios", key="inicio_btn_descartar", use_container_width=True):
            st.session_state.pop(_EST, None)
            for k in [k for k in st.session_state if str(k).startswith(("inicio_in_", "inicio_t_", "inicio_x_"))]:
                st.session_state.pop(k, None)
            st.rerun()

    if st.session_state.pop("inicio_guardado", False):
        st.success("✅ Página de inicio guardada.")
        st.info("Para que todos la vean, sube los cambios a GitHub (en la terminal del proyecto):\n\n"
                "`git add assets/inicio inicio_config.json`  →  `git commit -m \"Actualiza página de inicio\"`  →  `git push`")
