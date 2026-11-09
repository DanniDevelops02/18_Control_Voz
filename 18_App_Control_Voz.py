import json
import random
import string
import tempfile
import threading
import time
import unicodedata
from datetime import datetime
from html import escape
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

try:
    import paho.mqtt.client as mqtt
except ImportError:  # se avisa en pantalla; la app no puede conectarse sin esta librería
    mqtt = None

try:
    from zoneinfo import ZoneInfo

    ZONA = ZoneInfo("America/Bogota")
except Exception:  # sin base de zonas horarias se usa la hora del servidor
    ZONA = None

st.set_page_config(
    page_title="Control por voz · Daniel Flórez",
    page_icon="🎙️",
    layout="centered",
    initial_sidebar_state="expanded",
)

# =====================================================================
#  AJUSTES  (los valores por defecto coinciden con el sketch de Wokwi)
# =====================================================================
BROKER_DEFECTO = "broker.hivemq.com"
PUERTO_DEFECTO = 1883
PREFIJO_DEFECTO = "dflorez/voz18"   # debe ser idéntico a PREFIJO en el sketch de Wokwi

IDIOMA_VOZ = "es-CO"       # idioma del reconocimiento de voz (es-ES, es-MX, en-US…)
MAX_CONEXIONES = 4         # conexiones simultáneas permitidas en este servidor
INACTIVO_MAX = 900         # segundos sin uso tras los que se cierra una conexión
SIN_DATOS_AVISO = 10       # segundos sin noticias del ESP32 para mostrar una ayuda
REFRESCO_SEG = 2           # cada cuánto se actualiza el estado en pantalla
MAX_HISTORIAL_ORDENES = 15

# =====================================================================
#  ESTILO (paleta fría basada en #3f71a6)
# =====================================================================
PRIMARIO = "#3f71a6"
OSCURO = "#1b2f45"
CLARO = "#eaf2f9"
SUAVE = "#a9c7e3"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Playfair+Display:wght@500;600;700&display=swap');

:root, .stApp { color-scheme: light; }
html, body, [class*="css"], .stApp { font-family: 'Inter', sans-serif; font-size: 1.06rem; }
.stApp { background: linear-gradient(180deg, #f6fafd 0%, __CLARO__ 100%); }
header[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 860px; padding-top: 3rem; padding-bottom: 4rem; }
[data-testid="stHeaderActionElements"] { display: none !important; }

/* Texto de la página principal: siempre oscuro, aunque el navegador esté en modo oscuro */
.block-container p, .block-container li, .block-container label,
.block-container [data-testid="stMarkdownContainer"],
.block-container [data-testid="stWidgetLabel"] * { color: __OSCURO__; }
.block-container [data-testid="stCaptionContainer"] * { color: #4d6479 !important; }

/* Hero */
.hero { text-align: center; padding: 1rem 0 .5rem 0; }
.hero .etiqueta {
    color: __PRIMARIO__; letter-spacing: .25em; text-transform: uppercase;
    font-size: .85rem; font-weight: 600;
}
.hero h1 {
    font-family: 'Playfair Display', serif; font-size: 3.1rem; color: __OSCURO__;
    margin: .3rem 0 .6rem 0; line-height: 1.12;
}
.hero p { color: #4d6479 !important; font-size: 1.2rem; max-width: 640px; margin: 0 auto; }
.linea { width: 70px; height: 4px; border-radius: 4px; background: __PRIMARIO__; margin: 1.4rem auto; }
h2, h3 { font-family: 'Playfair Display', serif !important; color: __OSCURO__ !important; }

/* Tarjetas (contenedores con key="tarjeta_...") */
[class*="st-key-tarjeta"] {
    background: #ffffff !important;
    border: 1px solid __SUAVE__88 !important;
    border-radius: 18px !important;
    box-shadow: 0 8px 24px rgba(63, 113, 166, .08);
    padding: 1.4rem 1.5rem 1.3rem 1.5rem !important;
}
[class*="st-key-tarjeta"] p, [class*="st-key-tarjeta"] label, [class*="st-key-tarjeta"] li,
[class*="st-key-tarjeta"] [data-testid="stWidgetLabel"] * { color: __OSCURO__ !important; }

/*__CAMPOS__*/

/* Botones */
.stButton > button, .stDownloadButton > button {
    background: __PRIMARIO__; color: #ffffff !important; border: 1.5px solid __PRIMARIO__;
    border-radius: 999px; padding: .6rem 1.4rem; font-weight: 600; transition: all .2s ease;
}
.stButton > button p, .stDownloadButton > button p { color: #ffffff !important; }
.stButton > button:hover, .stDownloadButton > button:hover {
    background: __OSCURO__; border-color: __OSCURO__; transform: translateY(-2px);
}

/* Estado de la conexión */
.estado {
    display: inline-flex; align-items: center; gap: 10px; border-radius: 999px; padding: 7px 18px;
    font-weight: 600; font-size: .95rem; margin-bottom: .6rem;
}
.estado .punto { width: 11px; height: 11px; border-radius: 50%; background: currentColor; }
.estado.ok { background: #e8f6ef; color: #1f7a52 !important; }
.estado.espera { background: #fff6e0; color: #96630a !important; }
.estado.error { background: #fdecec; color: #b03030 !important; }
.estado.ok .punto { animation: pulso 1.6s ease-in-out infinite; }
@keyframes pulso { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: .35; transform: scale(.75); } }
@media (prefers-reduced-motion: reduce) { .estado.ok .punto { animation: none; } }
.dato-linea { color: #4d6479 !important; font-size: .92rem; margin: .1rem 0 .8rem 0; }

/* Medidas */
.medidas { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; margin: .4rem 0; }
.medida {
    background: linear-gradient(160deg, #f6fafd, __CLARO__); border: 1px solid __SUAVE__99;
    border-radius: 16px; padding: 1.1rem 1.2rem; text-align: center;
}
.medida .nombre { font-size: .8rem; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; color: #4d6479 !important; }
.medida .valor { font-family: 'Playfair Display', serif; font-size: 3.2rem; line-height: 1.15; color: __PRIMARIO__ !important; font-weight: 700; }
.medida .unidad { font-size: 1.3rem; font-weight: 500; color: __OSCURO__ !important; }
.medida .delta { font-size: .85rem; color: #4d6479 !important; min-height: 1.2em; }

/* Mando */
.subtitulo { font-size: .8rem; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: #4d6479 !important; margin: 1rem 0 .4rem 0; }
[class*="st-key-sec_"] button { background: #ffffff; border: 1.5px solid __PRIMARIO__; }
[class*="st-key-sec_"] button p { color: __PRIMARIO__ !important; }
[class*="st-key-sec_"] button:hover { background: __CLARO__; border-color: __PRIMARIO__; }
[class*="st-key-sec_"] button:hover p { color: __OSCURO__ !important; }

/* Piezas del dispositivo */
.piezas { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin: .4rem 0; }
.pieza { background: linear-gradient(160deg, #f6fafd, __CLARO__); border: 1px solid __SUAVE__99; border-radius: 16px; padding: 1.1rem 1.2rem; text-align: center; }
.pieza .nombre { font-size: .8rem; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; color: #4d6479 !important; }
.pieza .lectura { font-family: 'Playfair Display', serif; font-size: 1.9rem; font-weight: 700; color: __PRIMARIO__ !important; margin-top: .2rem; }
.lampara { height: 96px; display: flex; align-items: center; justify-content: center; }
.bombillo { width: 62px; height: 62px; border-radius: 50%; background: #cfdbe7; border: 3px solid #b3c4d4; transition: all .3s ease; }
.lampara.encendido .bombillo { background: #ffd34d; border-color: #f0a030; box-shadow: 0 0 0 8px #ffd34d55, 0 0 34px 10px #ffd34daa; }
.lampara { margin: 6px 0; }
.lampara.desconocido .bombillo { background: #eef3f8; border-style: dashed; }
.medidor { width: 100%; max-width: 230px; height: auto; margin-top: .2rem; }
.medidor.desconocido { opacity: .55; }

/* Puerta */
.escena { height: 128px; margin: 8px 0 4px 0; display: flex; align-items: center; justify-content: center; }
.marco { width: 74px; height: 108px; background: #1b2f45; border: 4px solid #4d6479; border-radius: 4px 4px 0 0; perspective: 320px; position: relative; }
.hoja { position: absolute; inset: 0; background: #c79a62; border: 2px solid #9c7440; transform-origin: left center; transition: transform .6s ease; }
.hoja.cerrada { transform: rotateY(0deg); }
.hoja.abierta { transform: rotateY(-72deg); }
.hoja.desconocido { background: #eef3f8; border: 2px dashed #b3c4d4; }
.pomo { position: absolute; right: 7px; top: 54%; width: 8px; height: 8px; border-radius: 50%; background: #f0d9a8; }
@media (prefers-reduced-motion: reduce) { .hoja { transition: none; } }

/* Sidebar */
[data-testid="stSidebar"] { background: __OSCURO__; }
[data-testid="stSidebar"] * { color: #e6f0f9 !important; }

#MainMenu, footer { visibility: hidden; }
</style>
"""


def inyectar_css() -> None:
    css = CSS.replace("/*__CAMPOS__*/", CSS_CAMPOS)
    for token, valor in {
        "__PRIMARIO__": PRIMARIO, "__OSCURO__": OSCURO, "__CLARO__": CLARO, "__SUAVE__": SUAVE,
    }.items():
        css = css.replace(token, valor)
    st.markdown(css, unsafe_allow_html=True)


CSS_CAMPOS = """
/* ---- Campos, selectores, desplegables y avisos: siempre claros (a prueba de modo oscuro) ---- */
[data-testid="stTextInput"] [data-baseweb="input"],
[data-testid="stNumberInput"] [data-baseweb="input"],
[data-testid="stTextArea"] [data-baseweb="textarea"] {
    background-color: #ffffff !important; border: 1px solid __SUAVE__ !important;
    border-radius: 12px !important; box-shadow: none !important;
}
[data-testid="stTextInput"] [data-baseweb="input"] *,
[data-testid="stNumberInput"] [data-baseweb="input"] *,
[data-testid="stTextArea"] [data-baseweb="textarea"] * {
    background-color: transparent !important; border-color: transparent !important; box-shadow: none !important;
    color: __OSCURO__ !important; -webkit-text-fill-color: __OSCURO__ !important; fill: __OSCURO__ !important;
}
[data-testid="stTextInput"] [data-baseweb="input"]:focus-within,
[data-testid="stNumberInput"] [data-baseweb="input"]:focus-within,
[data-testid="stTextArea"] [data-baseweb="textarea"]:focus-within {
    border-color: __PRIMARIO__ !important; box-shadow: 0 0 0 1px __PRIMARIO__ !important;
}
[data-testid="stTextInput"] input::placeholder { color: #7d93a8 !important; -webkit-text-fill-color: #7d93a8 !important; opacity: 1; }

/* Avisos (st.info, st.warning, st.error, st.success) */
[data-testid="stAlert"] { --alerta-fondo: __CLARO__; --alerta-borde: __SUAVE__; }
[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) { --alerta-fondo: #fff6e0; --alerta-borde: #f2d08a; }
[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) { --alerta-fondo: #fdecec; --alerta-borde: #f0b4b4; }
[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) { --alerta-fondo: #e8f6ef; --alerta-borde: #a6d8bf; }
[data-testid="stAlert"] {
    background-color: var(--alerta-fondo) !important; border: 1px solid var(--alerta-borde) !important;
    border-radius: 14px !important; overflow: hidden;
}
[data-testid="stAlert"] > div, [data-testid="stAlert"] [data-baseweb="notification"] {
    background-color: var(--alerta-fondo) !important; border: none !important; border-radius: 14px !important;
}
[data-testid="stAlert"] * { color: __OSCURO__ !important; -webkit-text-fill-color: __OSCURO__ !important; }
[data-testid="stAlert"] p, [data-testid="stAlert"] span, [data-testid="stAlert"] div { background-color: transparent !important; }

/* Desplegables (st.expander): la barra del título también es clara */
[data-testid="stExpander"] details {
    background-color: #ffffff !important; border: 1px solid __SUAVE__88 !important; border-radius: 16px !important;
    box-shadow: 0 8px 24px rgba(63, 113, 166, .08); overflow: hidden;
}
[data-testid="stExpander"] summary { background-color: #ffffff !important; }
[data-testid="stExpander"] summary:hover { background-color: __CLARO__ !important; }
[data-testid="stExpander"] summary * { background-color: transparent !important; color: __OSCURO__ !important; fill: __OSCURO__ !important; }
[data-testid="stExpander"] p, [data-testid="stExpander"] li, [data-testid="stExpander"] label { color: __OSCURO__ !important; }
[data-testid="stExpander"] svg { fill: __OSCURO__ !important; color: __OSCURO__ !important; }

/* Interruptor (st.toggle) */
[data-testid="stCheckbox"] label, [data-testid="stToggle"] label { color: __OSCURO__ !important; }

/* El menú con el cambio de tema se oculta: esta página está diseñada solo en claro */
[data-testid="stMainMenu"] { display: none !important; }
"""


# =====================================================================
#  RECONOCIMIENTO DE VOZ (en el NAVEGADOR, no en el servidor)
#
#  El navegador (Chrome, Edge, Safari) trae un reconocedor de voz propio: la "Web Speech API".
#  Un componente pequeño usa tu micrófono, convierte la voz en texto y se lo manda a Python.
#  Python decide qué orden es y la publica por MQTT.
# =====================================================================
VOZ_HTML = """
<!doctype html>
<html><head><meta charset="utf-8">
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; background: transparent; font-family: 'Inter', system-ui, sans-serif; color: __OSCURO__; }
  .caja { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 22px 4px 10px 4px; }
  #mic {
    width: 112px; height: 112px; border-radius: 50%; border: none; cursor: pointer;
    background: __PRIMARIO__; color: #fff; display: flex; align-items: center; justify-content: center;
    box-shadow: 0 10px 26px rgba(63,113,166,.35); transition: transform .15s ease, background .2s ease;
  }
  #mic:hover { transform: translateY(-2px); background: __OSCURO__; }
  #mic:focus-visible { outline: 3px solid __SUAVE__; outline-offset: 3px; }
  #mic svg { width: 46px; height: 46px; fill: currentColor; }
  #mic.escuchando { background: #c0392b; animation: latido 1.4s ease-in-out infinite; }
  @keyframes latido { 0%,100% { box-shadow: 0 0 0 0 rgba(192,57,43,.45); } 50% { box-shadow: 0 0 0 18px rgba(192,57,43,0); } }
  @media (prefers-reduced-motion: reduce) { #mic.escuchando { animation: none; } }
  #estado { font-weight: 600; font-size: .98rem; text-align: center; }
  #texto {
    width: 100%; min-height: 54px; background: #fff; border: 1px solid __SUAVE__; border-radius: 14px;
    padding: 12px 16px; text-align: center; font-size: 1.15rem; color: __OSCURO__;
  }
  #texto.vacio { color: #7d93a8; font-size: 1rem; }
  #texto.parcial { color: #4d6479; font-style: italic; }
  #aviso { color: #96630a; background: #fff6e0; border: 1px solid #f2d08a; border-radius: 12px; padding: 10px 14px; font-size: .92rem; display: none; text-align: center; }
</style></head>
<body>
<div class="caja">
  <button id="mic" type="button" aria-label="Activar o detener el micrófono">
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 15a4 4 0 0 0 4-4V6a4 4 0 0 0-8 0v5a4 4 0 0 0 4 4zm6-4a1 1 0 1 1 2 0 8 8 0 0 1-7 7.94V21h3a1 1 0 1 1 0 2H8a1 1 0 1 1 0-2h3v-2.06A8 8 0 0 1 4 11a1 1 0 1 1 2 0 6 6 0 0 0 12 0z"/></svg>
  </button>
  <div id="estado">Toca el micrófono y habla</div>
  <div id="texto" class="vacio">Aquí aparecerá lo que digas</div>
  <div id="aviso"></div>
</div>
<script>
  const IDIOMA = "__IDIOMA__";
  const mic = document.getElementById("mic");
  const estado = document.getElementById("estado");
  const texto = document.getElementById("texto");
  const aviso = document.getElementById("aviso");

  function mensaje(tipo, extra) {
    window.parent.postMessage(Object.assign({ isStreamlitMessage: true, type: tipo }, extra), "*");
  }
  const listo = () => mensaje("streamlit:componentReady", { apiVersion: 1 });
  const altura = () => mensaje("streamlit:setFrameHeight", { height: document.documentElement.scrollHeight });
  const enviar = (t) => mensaje("streamlit:setComponentValue", {
    value: { id: Date.now() + "-" + Math.random().toString(36).slice(2, 8), texto: t }, dataType: "json" });

  function mostrarAviso(t) { aviso.textContent = t; aviso.style.display = t ? "block" : "none"; altura(); }

  const Reconocedor = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rec = null, activo = false, quiereEscuchar = false;

  function ponerEstado(t, escuchando) {
    estado.textContent = t; mic.classList.toggle("escuchando", !!escuchando);
  }

  if (!Reconocedor) {
    mic.disabled = true; mic.style.opacity = .45; mic.style.cursor = "not-allowed";
    ponerEstado("Este navegador no tiene reconocimiento de voz", false);
    mostrarAviso("Usa Chrome, Edge o Safari, o los botones de abajo.");
  } else {
    rec = new Reconocedor();
    rec.lang = IDIOMA;
    rec.continuous = true;       // sigue escuchando después de cada frase
    rec.interimResults = true;   // muestra el texto mientras hablas
    rec.maxAlternatives = 1;

    rec.onstart = () => { activo = true; ponerEstado("Escuchando… habla ahora", true); mostrarAviso(""); };
    rec.onresult = (e) => {
      let parcial = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const frase = e.results[i][0].transcript.trim();
        if (e.results[i].isFinal) {
          if (frase) { texto.textContent = frase; texto.className = ""; enviar(frase); }
        } else { parcial += " " + frase; }
      }
      if (parcial.trim()) { texto.textContent = parcial.trim(); texto.className = "parcial"; }
    };
    rec.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        quiereEscuchar = false;
        mostrarAviso("El navegador no dio permiso al micrófono. Pulsa el candado junto a la dirección y permítelo.");
      } else if (e.error === "audio-capture") {
        quiereEscuchar = false; mostrarAviso("No se encontró ningún micrófono.");
      } else if (e.error === "network") {
        mostrarAviso("El reconocimiento de voz necesita conexión a internet.");
      }
    };
    rec.onend = () => {
      activo = false;
      if (quiereEscuchar) {            // Chrome corta tras unos segundos de silencio: se reanuda solo
        try { rec.start(); } catch (_) {}
      } else { ponerEstado("Micrófono apagado. Toca para hablar", false); }
    };
    mic.onclick = () => {
      if (quiereEscuchar) { quiereEscuchar = false; rec.stop(); return; }
      quiereEscuchar = true;
      try { rec.start(); } catch (_) {}
    };
  }
  listo(); altura();
  new ResizeObserver(altura).observe(document.body);
</script>
</body></html>
"""


@st.cache_resource
def preparar_voz():
    carpeta = Path(tempfile.gettempdir()) / "voz_mqtt_componente"
    carpeta.mkdir(exist_ok=True)
    html = (
        VOZ_HTML.replace("__PRIMARIO__", PRIMARIO).replace("__OSCURO__", OSCURO)
        .replace("__SUAVE__", SUAVE).replace("__IDIOMA__", IDIOMA_VOZ)
    )
    archivo = carpeta / "index.html"
    if not archivo.exists() or archivo.read_text(encoding="utf-8") != html:
        archivo.write_text(html, encoding="utf-8")
    return components.declare_component("voz_mqtt", path=str(carpeta))


componente_voz = preparar_voz()


# =====================================================================
#  DE TEXTO HABLADO A ORDEN
#  El navegador entrega frases libres ("Enciende las luces, por favor").
#  Aquí se buscan palabras clave, así no importan mayúsculas, tildes ni palabras extra.
# =====================================================================
ORDENES = {
    # clave: (texto que recibe el ESP32, descripción para la pantalla)
    "luces_on": ("enciende las luces", "Encender las luces"),
    "luces_off": ("apaga las luces", "Apagar las luces"),
    "puerta_abrir": ("abre la puerta", "Abrir la puerta"),
    "puerta_cerrar": ("cierra la puerta", "Cerrar la puerta"),
}
OBJETO_LUZ = ("luz", "luces", "luminaria", "bombillo", "bombillos", "foco", "focos")
OBJETO_PUERTA = ("puerta", "puertas", "porton")
VERBOS_ON = ("encend", "enciend", "prend", "activ")
VERBOS_OFF = ("apag", "desactiv")
VERBOS_ABRIR = ("abr",)
VERBOS_CERRAR = ("cierr", "cerr")


def normalizar(texto: str) -> list:
    """Minúsculas, sin tildes ni signos: 'Enciende LAS luces!' -> ['enciende','las','luces']."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    limpio = "".join(c if c.isalnum() else " " for c in sin_tildes)
    return limpio.split()


def interpretar_voz(texto: str):
    """Devuelve la clave de ORDENES o None si no se entiende una orden."""
    palabras = normalizar(texto)

    def tiene_verbo(verbos):
        return any(p.startswith(v) for p in palabras for v in verbos)

    if any(p in OBJETO_LUZ for p in palabras):
        if tiene_verbo(VERBOS_OFF):
            return "luces_off"
        if tiene_verbo(VERBOS_ON):
            return "luces_on"
    if any(p in OBJETO_PUERTA for p in palabras):
        if tiene_verbo(VERBOS_CERRAR):
            return "puerta_cerrar"
        if tiene_verbo(VERBOS_ABRIR):
            return "puerta_abrir"
    return None


# =====================================================================
#  CONEXIÓN MQTT
#    app --(publica)--> <prefijo>/voz     --> broker --> ESP32 (suscrito)
#    app <--(suscrita)-- <prefijo>/estado <-- broker <-- ESP32 (publica, retenido)
# =====================================================================
def crear_cliente_paho(id_cliente: str):
    """Crea el cliente MQTT; funciona igual con paho-mqtt 1.x y 2.x."""
    if mqtt is None:
        raise RuntimeError("Falta la librería paho-mqtt en requirements.txt")
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=id_cliente)  # paho 2.x
    except AttributeError:
        return mqtt.Client(client_id=id_cliente)  # paho 1.x


def prefijo_valido(prefijo: str) -> str:
    """Devuelve '' si el prefijo sirve, o el motivo por el que no."""
    if not prefijo:
        return "Escribe un prefijo de tópicos."
    if any(c in prefijo for c in "+#") or " " in prefijo:
        return "El prefijo no puede tener espacios ni los símbolos + o #."
    if prefijo.startswith(("/", "$")) or prefijo.endswith("/") or "//" in prefijo:
        return "El prefijo no debe empezar ni terminar con «/», ni empezar con «$»."
    if len(prefijo) > 100:
        return "El prefijo es demasiado largo."
    return ""


def interpretar_estado(texto: str) -> dict:
    """{'online': bool|None, 'led': 'ON'|'OFF'|None, 'puerta': 'abierta'|'cerrada'|None}."""
    salida = {"online": None, "led": None, "puerta": None}
    try:
        dato = json.loads(texto)
    except ValueError:
        return salida
    if not isinstance(dato, dict):
        return salida
    if isinstance(dato.get("online"), bool):
        salida["online"] = dato["online"]
    if str(dato.get("led", "")).upper() in ("ON", "OFF"):
        salida["led"] = str(dato["led"]).upper()
    if str(dato.get("puerta", "")).lower() in ("abierta", "cerrada"):
        salida["puerta"] = str(dato["puerta"]).lower()
    return salida


class Conexion:
    """Una conexión MQTT persistente: publica órdenes y guarda el último estado del ESP32."""

    def __init__(self, broker: str, puerto: int, prefijo: str, fabrica=None):
        self.broker, self.puerto, self.prefijo = broker, puerto, prefijo
        self.t_orden = f"{prefijo}/voz"
        self.t_estado = f"{prefijo}/estado"
        sufijo = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        self.id_cliente = f"streamlit-voz-{sufijo}"  # único: dos IDs iguales se expulsan entre sí
        self.conectado = False
        self.error = ""
        self.creado = time.time()
        self.ultimo_uso = self.creado
        self.dispositivo = {"online": None, "led": None, "puerta": None}
        self.estado_hora = 0.0
        self.estado_crudo = ""
        self.estado_retenido = False
        self.enviados = 0
        self._cerrojo = threading.Lock()

        self.cliente = (fabrica or crear_cliente_paho)(self.id_cliente)
        self.cliente.on_connect = self._al_conectar
        self.cliente.on_disconnect = self._al_desconectar
        self.cliente.on_connect_fail = self._al_fallar
        self.cliente.on_message = self._al_recibir
        self.cliente.reconnect_delay_set(min_delay=1, max_delay=15)
        self.cliente.connect_async(broker, puerto, keepalive=30)
        self.cliente.loop_start()

    # --- Hilo de paho ---
    def _al_conectar(self, cliente, userdata, flags, rc, *extra):
        codigo = getattr(rc, "value", rc)
        if codigo == 0:
            self.conectado = True
            self.error = ""
            cliente.subscribe(self.t_estado, qos=1)  # se repite en cada reconexión
        else:
            self.conectado = False
            self.error = f"El broker rechazó la conexión (código {codigo})."

    def _al_desconectar(self, cliente, userdata, *args):
        self.conectado = False

    def _al_fallar(self, cliente, userdata, *args):
        self.conectado = False
        self.error = (
            f"No se pudo conectar con {self.broker}:{self.puerto}. "
            "Revisa la dirección, el puerto o la conexión a internet."
        )

    def _al_recibir(self, cliente, userdata, mensaje):
        if mensaje.topic != self.t_estado:
            return
        texto = mensaje.payload.decode("utf-8", errors="replace")
        datos = interpretar_estado(texto)
        with self._cerrojo:
            self.estado_crudo = texto
            self.estado_hora = time.time()
            self.estado_retenido = bool(getattr(mensaje, "retain", False))
            if datos["online"] is False:  # testamento: se conservan los últimos valores conocidos
                self.dispositivo["online"] = False
            else:
                self.dispositivo = {
                    "online": datos["online"] if datos["online"] is not None else True,
                    "led": datos["led"] or self.dispositivo["led"],
                    "puerta": datos["puerta"] or self.dispositivo["puerta"],
                }

    # --- Desde Streamlit ---
    def estado(self) -> str:
        if self.conectado:
            return "conectado"
        return "error" if self.error else "conectando"

    def lectura(self) -> tuple:
        with self._cerrojo:
            return dict(self.dispositivo), self.estado_hora, self.estado_retenido, self.estado_crudo

    def publicar(self, carga: dict, espera: float = 3.0) -> tuple:
        """Publica con QoS 1 y espera la confirmación del broker. Devuelve (ok, texto)."""
        if not self.conectado:
            return False, "Todavía no hay conexión con el broker. Espera unos segundos y vuelve a intentar."
        try:
            info = self.cliente.publish(self.t_orden, json.dumps(carga), qos=1)
        except Exception as error:  # noqa: BLE001 - se muestra al usuario tal cual
            return False, f"No se pudo enviar: {error}"
        if info.rc != 0:
            return False, f"El envío falló (código {info.rc}). Revisa la conexión."
        limite = time.time() + espera
        while time.time() < limite:
            if info.is_published():
                self.enviados += 1
                return True, "El broker recibió la orden."
            time.sleep(0.05)
        return False, "El broker no confirmó la orden a tiempo. Intenta de nuevo."

    def detener(self) -> None:
        try:
            self.cliente.disconnect()
            self.cliente.loop_stop()
        except Exception:
            pass


@st.cache_resource
def registro() -> dict:
    return {"cerrojo": threading.Lock(), "conexiones": {}}


def obtener_conexion(broker: str, puerto: int, prefijo: str) -> Conexion:
    reg = registro()
    clave = (broker, puerto, prefijo)
    ahora = time.time()
    with reg["cerrojo"]:
        activas = reg["conexiones"]
        for k, c in list(activas.items()):
            if k != clave and ahora - c.ultimo_uso > INACTIVO_MAX:
                c.detener()
                del activas[k]
        conexion = activas.get(clave)
        if conexion is None:
            while len(activas) >= MAX_CONEXIONES:
                k_viejo = min(activas, key=lambda k: activas[k].ultimo_uso)
                activas.pop(k_viejo).detener()
            conexion = Conexion(broker, puerto, prefijo)
            activas[clave] = conexion
        conexion.ultimo_uso = ahora
        return conexion


# =====================================================================
#  DIBUJOS (lámpara y puerta)
# =====================================================================
def hace_cuanto(segundos: float) -> str:
    segundos = max(0, int(segundos))
    if segundos < 60:
        return f"hace {segundos} s"
    return f"hace {segundos // 60} min {segundos % 60} s"


def html_luz(estado) -> str:
    clase = {"ON": "encendido", "OFF": "apagado"}.get(estado, "desconocido")
    texto = {"ON": "Encendidas", "OFF": "Apagadas"}.get(estado, "Sin datos")
    return (
        '<div class="pieza"><div class="nombre">Luces (LED, GPIO 2)</div>'
        f'<div class="lampara {clase}"><span class="bombillo"></span></div>'
        f'<div class="lectura">{texto}</div></div>'
    )


def html_puerta(estado) -> str:
    clase = {"abierta": "abierta", "cerrada": "cerrada"}.get(estado, "desconocido")
    texto = {"abierta": "Abierta", "cerrada": "Cerrada"}.get(estado, "Sin datos")
    return (
        '<div class="pieza"><div class="nombre">Puerta (servo, GPIO 13)</div>'
        f'<div class="escena"><div class="marco"><div class="hoja {clase}"><span class="pomo"></span></div></div></div>'
        f'<div class="lectura">{texto}</div></div>'
    )


def describir_dispositivo(conexion: Conexion) -> tuple:
    """(clase CSS, texto del distintivo, ayuda o None) según lo que informa el ESP32."""
    estado = conexion.estado()
    ahora = time.time()
    if estado == "error":
        return "error", "Sin conexión con el broker", conexion.error
    if estado == "conectando":
        ayuda = None
        if ahora - conexion.creado > SIN_DATOS_AVISO:
            ayuda = "Está tardando más de lo normal. Revisa el broker y el puerto en «Ajustes de conexión»."
        return "espera", "Conectando al broker…", ayuda
    dispositivo, hora, _retenido, _crudo = conexion.lectura()
    if hora == 0.0:
        ayuda = None
        if ahora - conexion.creado > SIN_DATOS_AVISO:
            ayuda = (
                "Hay conexión con el broker, pero el ESP32 todavía no ha informado su estado. "
                "¿Está corriendo la simulación en Wokwi? ¿El PREFIJO del sketch es idéntico al de esta página?"
            )
        return "espera", "Broker conectado · esperando al ESP32", ayuda
    if dispositivo["online"] is False:
        return "error", "ESP32 desconectado", (
            "El broker avisó que el ESP32 se desconectó (apagaste la simulación o perdió la red). "
            "Los valores de abajo son los últimos que informó."
        )
    return "ok", "ESP32 en línea", None


# =====================================================================
#  ENVÍO DE ÓRDENES
# =====================================================================
def enviar_clave(clave: str, origen: str, escuchado: str = "") -> None:
    """Publica una orden de ORDENES y deja el resultado en session_state para mostrarlo."""
    texto_orden, descripcion = ORDENES[clave]
    conexion = obtener_conexion(*st.session_state["cfg"])
    ok, detalle = conexion.publicar({"Act1": texto_orden})
    historial = st.session_state.setdefault("historial", [])
    historial.insert(0, (time.time(), descripcion, origen, ok))
    del historial[MAX_HISTORIAL_ORDENES:]
    prefijo = f"Entendí «{escuchado}» → " if escuchado else ""
    st.session_state["resultado"] = (ok, f"{prefijo}{descripcion}: {detalle}")


def boton_manual(clave: str) -> None:  # on_click de los botones
    enviar_clave(clave, "botón")


def procesar_voz(texto: str) -> None:
    clave = interpretar_voz(texto)
    if clave is None:
        st.session_state["resultado"] = (
            False,
            f"Escuché «{texto}», pero no es una orden que conozca. "
            "Prueba con: «enciende las luces», «apaga las luces», «abre la puerta» o «cierra la puerta».",
        )
        return
    enviar_clave(clave, "voz", escuchado=texto)


# =====================================================================
#  PÁGINA
# =====================================================================
inyectar_css()

with st.sidebar:
    st.subheader("Cómo funciona")
    st.markdown(
        "1. Tu **navegador** escucha el micrófono y convierte la voz en texto.\n"
        "2. Esta página busca en el texto una orden (luces o puerta).\n"
        "3. La **publica** por MQTT en el tópico `…/voz` y el broker confirma.\n"
        "4. El ESP32 de Wokwi, **suscrito** a ese tópico, enciende el LED o mueve el servo.\n"
        "5. El ESP32 publica su **estado** y aquí lo ves."
    )
    st.subheader("Órdenes de voz")
    st.markdown("- «Enciende las luces»\n- «Apaga las luces»\n- «Abre la puerta»\n- «Cierra la puerta»")
    st.subheader("Privacidad")
    st.markdown(
        "El broker público es compartido: quien conozca el prefijo puede mandar órdenes. "
        "Usa uno propio. El reconocimiento de voz lo hace el servicio de voz de tu navegador."
    )

st.markdown(
    """
    <div class="hero">
        <div class="etiqueta">Interfaces multimodales</div>
        <h1>Control por voz</h1>
        <p>Habla y mueve un ESP32 simulado en Wokwi: enciende las luces o abre la puerta con tu voz.</p>
        <div class="linea"></div>
    </div>
    """,
    unsafe_allow_html=True,
)

if mqtt is None:
    st.error("Falta la librería `paho-mqtt`. Agrégala a `requirements.txt` y reinicia la app.")
    st.stop()

with st.container(key="tarjeta_conexion"):
    st.subheader("Conexión")
    st.caption(
        "Los valores por defecto ya funcionan con el sketch incluido. "
        "Si cambias el prefijo aquí, cámbialo igual en el sketch."
    )
    with st.expander("Ajustes de conexión"):
        broker = st.text_input("Broker MQTT", value=BROKER_DEFECTO, help="Dirección del servidor MQTT").strip()
        puerto = st.number_input("Puerto", value=PUERTO_DEFECTO, min_value=1, max_value=65535, step=1,
                                 help="1883 es el puerto estándar sin cifrado.")
        prefijo = st.text_input(
            "Prefijo de tópicos", value=PREFIJO_DEFECTO,
            help="Las órdenes van a «prefijo/voz» y el estado llega por «prefijo/estado».",
        ).strip()

error_prefijo = prefijo_valido(prefijo)
if not broker or " " in broker:
    st.error("Escribe una dirección de broker válida (sin espacios).")
    st.stop()
if error_prefijo:
    st.error(error_prefijo)
    st.stop()

try:
    conexion = obtener_conexion(broker, int(puerto), prefijo)
except Exception as error:
    st.error(f"No se pudo iniciar la conexión: {error}")
    st.stop()
st.session_state["cfg"] = (broker, int(puerto), prefijo)

st.write("")
with st.container(key="tarjeta_voz"):
    st.subheader("Habla")
    valor_voz = componente_voz(key="voz", default=None)
    if valor_voz and valor_voz.get("id") != st.session_state.get("voz_id_visto"):
        st.session_state["voz_id_visto"] = valor_voz["id"]  # cada frase se procesa una sola vez
        procesar_voz(str(valor_voz.get("texto", "")))

    resultado = st.session_state.get("resultado")
    if resultado:
        ok, texto = resultado
        (st.success if ok else st.warning)(texto)
    else:
        st.caption("Aquí verás qué orden entendí y si el broker la recibió.")

    st.markdown('<div class="subtitulo">O usa los botones</div>', unsafe_allow_html=True)
    b1, b2, b3, b4 = st.columns(4)
    for col, clave, nombre, llave in (
        (b1, "luces_on", "Encender luces", "luces_on"),
        (b2, "luces_off", "Apagar luces", "sec_luces_off"),
        (b3, "puerta_abrir", "Abrir puerta", "puerta_abrir"),
        (b4, "puerta_cerrar", "Cerrar puerta", "sec_puerta_cerrar"),
    ):
        with col:
            st.button(nombre, key=llave, on_click=boton_manual, args=(clave,), use_container_width=True)

    historial = st.session_state.get("historial", [])
    if historial:
        with st.expander("Órdenes enviadas"):
            for epoch, descripcion, origen, ok in historial:
                marca = "✓" if ok else "✗"
                st.markdown(f"{marca} {hora_local(epoch):%H:%M:%S} · {descripcion} ({origen})")

st.write("")


@st.fragment(run_every=REFRESCO_SEG)
def panel() -> None:
    conexion.ultimo_uso = time.time()
    clase, texto_estado, ayuda = describir_dispositivo(conexion)
    dispositivo, hora, retenido, crudo = conexion.lectura()

    with st.container(key="tarjeta_dispositivo"):
        st.subheader("Estado del dispositivo")
        st.markdown(
            f'<div class="estado {clase}"><span class="punto"></span>{escape(texto_estado)}</div>',
            unsafe_allow_html=True,
        )
        detalle = f"{escape(conexion.broker)}:{conexion.puerto} · prefijo {escape(conexion.prefijo)}"
        if hora:
            detalle += f" · último estado {hace_cuanto(time.time() - hora)}"
            if retenido:
                detalle += " (guardado en el broker)"
        st.markdown(f'<div class="dato-linea">{detalle}</div>', unsafe_allow_html=True)
        if ayuda:
            st.warning(ayuda)
        st.markdown(
            '<div class="piezas">' + html_luz(dispositivo["led"]) + html_puerta(dispositivo["puerta"]) + "</div>",
            unsafe_allow_html=True,
        )

    st.write("")
    with st.expander("Detalles técnicos"):
        st.markdown(
            f"- **Broker:** `{conexion.broker}` · **puerto:** `{conexion.puerto}` (MQTT sin cifrar)\n"
            f"- **Tópico de órdenes:** `{conexion.t_orden}` · **QoS:** 1\n"
            f"- **Tópico de estado:** `{conexion.t_estado}` · **QoS:** 1 (retenido por el ESP32)\n"
            f"- **ID de cliente de esta app:** `{conexion.id_cliente}`\n"
            f"- **Órdenes confirmadas por el broker:** {conexion.enviados}"
        )
        if crudo:
            st.caption("Último estado crudo recibido:")
            st.code(crudo, language="json")


panel()
