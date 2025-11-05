# app.py
import os
import json
import time
import platform
import tempfile

import streamlit as st
from PIL import Image
import paho.mqtt.client as paho

from bokeh.models import CustomJS
from bokeh.models.widgets import Button
from streamlit_bokeh_events import streamlit_bokeh_events

# ----- Opcionales -----
try:
    from deep_translator import GoogleTranslator
    HAS_TRANSLATE = True
except Exception:
    HAS_TRANSLATE = False

try:
    from gtts import gTTS
    HAS_TTS = True
except Exception:
    HAS_TTS = False


# =========================
# Configuración de página
# =========================
st.set_page_config(page_title="Ctrl Voz · MQTT", page_icon="🎙️", layout="centered")

# =========================
# Estilos (negro / blanco)
# =========================
st.markdown("""
<style>
/* Base negra + tipografía blanca */
html, body, [data-testid="stAppViewContainer"] {
  background: #000 !important;
  color: #fff !important;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, 'Helvetica Neue', Arial, 'Apple Color Emoji','Segoe UI Emoji';
}
/* Container central más angosto y sin scroll horizontal raro */
.block-container {max-width: 900px; padding-top: 2rem; padding-bottom: 4rem;}
/* Inputs y selects */
input, textarea, select {
  background: #0d0d0d !important; color: #fff !important; border: 1px solid #222 !important; border-radius: 10px !important;
}
[data-baseweb="input"] input { color: #fff !important; }
.stTextInput > div > div > input::placeholder { color:#777; }
.stNumberInput input { color: #fff !important; }
/* Botones */
button[kind="primary"]{
  background:#fff !important; color:#000 !important; border-radius: 999px !important; border:none !important; font-weight:600;
}
button[kind="secondary"]{
  background:#111 !important; color:#fff !important; border:1px solid #333 !important; border-radius: 999px !important;
}
button:hover { filter: brightness(0.92); }
/* Chips */
.pill {
  display:inline-block; padding:.35rem .65rem; border:1px solid #333; border-radius:999px; background:#0b0b0b; color:#e5e5e5; font-size:.78rem; margin-right:.3rem;
}
/* Dividers */
hr{ border:0; border-top:1px solid #1d1d1d; margin:1.25rem 0; }
/* Expander */
.streamlit-expanderHeader{ color:#fff !important; }
</style>
""", unsafe_allow_html=True)

# =========================
# Encabezado
# =========================
st.markdown("### TELEMETRÍA POR VOZ")
st.markdown("# 🎙️ Control por Voz → MQTT")
st.markdown(
    '<span class="pill">Dark UI</span>'
    '<span class="pill">Bokeh Speech</span>'
    '<span class="pill">MQTT</span>'
    f'<span class="pill">Python {platform.python_version()}</span>',
    unsafe_allow_html=True
)
st.write("Habla y publicaremos el texto reconocido en tu tópico MQTT. "
         "Opcionalmente traducimos a **EN** y/o reproducimos audio.")

st.markdown("---")

# =========================
# Sidebar: configuración
# =========================
with st.sidebar:
    st.subheader("⚙️ Conexión MQTT")
    broker = st.text_input("Broker", value="broker.mqttdashboard.com")
    port = st.number_input("Puerto", min_value=1, max_value=65535, value=1883)
    topic = st.text_input("Tópico de publicación", value="voice_isabela")
    client_id = st.text_input("Client ID", value="ctrl-voice-ui")

    st.subheader("🎛️ Procesamiento")
    do_translate = st.toggle("Traducir a inglés (deep-translator)", value=True if HAS_TRANSLATE else False,
                             help="Usa deep-translator; si no está instalado, se ignorará.")
    do_tts = st.toggle("Reproducir audio (gTTS)", value=False,
                       help="Convierte el texto en voz y lo reproduce en el navegador.")

    st.caption(f"Traducción disponible: {'sí' if HAS_TRANSLATE else 'no'} · TTS disponible: {'sí' if HAS_TTS else 'no'}")


# =========================
# MQTT helpers
# =========================
def on_publish(_client, _userdata, _result):
    # Solo log sencillo a consola del servidor
    print("Publicado en MQTT")

def publish_mqtt(broker_host: str, port_num: int, topic_name: str, payload: dict, client_name: str):
    try:
        c = paho.Client(client_name)
        c.on_publish = on_publish
        c.connect(broker_host, int(port_num))
        rc = c.publish(topic_name, json.dumps(payload), qos=0, retain=False)
        c.disconnect()
        return rc.rc == 0, None
    except Exception as e:
        return False, str(e)


# =========================
# Botón de micrófono (Bokeh)
# =========================
st.markdown("#### 🎧 Captura por voz")
st.caption("Pulsa **Iniciar** y habla con pausas breves. Cerrará automáticamente al dejar de hablar.")

bokeh_btn = Button(label="▶︎ Iniciar reconocimiento", width=260)
bokeh_btn.js_on_event("button_click", CustomJS(code="""
    const rec = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    rec.lang = 'es-ES';
    rec.continuous = true;
    rec.interimResults = true;

    rec.onresult = (e) => {
        let said = "";
        for (let i = e.resultIndex; i < e.results.length; ++i) {
            if (e.results[i].isFinal) { said += e.results[i][0].transcript + " "; }
        }
        if (said.trim() !== "") {
            document.dispatchEvent(new CustomEvent("GET_TEXT", {detail: said.trim()}));
        }
    };
    rec.onerror = (e) => {
        document.dispatchEvent(new CustomEvent("GET_TEXT", {detail: "__error__:" + (e.message || 'Speech error')}));
    };
    rec.start();
"""))

result = streamlit_bokeh_events(
    bokeh_btn,
    events="GET_TEXT",
    key="voice-listener",
    refresh_on_update=False,
    override_height=90,
    debounce_time=0
)

recognized = None
if result and "GET_TEXT" in result:
    recognized = result.get("GET_TEXT")

# =========================
# Post-proceso + MQTT
# =========================
if recognized:
    if recognized.startswith("__error__:"):
        st.error(f"🎤 Error de reconocimiento: {recognized.split(':',1)[1]}")
    else:
        st.markdown("#### 📝 Texto reconocido")
        st.write(f"“{recognized}”")

        text_to_send = recognized

        # Traducción opcional
        if do_translate:
            if HAS_TRANSLATE:
                try:
                    text_to_send = GoogleTranslator(source="auto", target="en").translate(text_to_send)
                    st.write('<span class="pill">Traducido → EN</span>', unsafe_allow_html=True)
                    st.write(f"“{text_to_send}”")
                except Exception as e:
                    st.warning(f"No se pudo traducir: {e}")
            else:
                st.info("Instala `deep-translator` para activar traducción.")

        # Publicación MQTT
        payload = {"Act1": text_to_send}
        ok, err = publish_mqtt(broker, port, topic, payload, client_id)
        if ok:
            st.success(f"📤 Publicado en **{broker} → {topic}**")
        else:
            st.error(f"❌ Error publicando MQTT: {err}")

        # TTS opcional
        if do_tts:
            if HAS_TTS:
                try:
                    # Idioma: si ya tradujimos a EN, voz en inglés; si no, español
                    tts_lang = "en" if (do_translate and HAS_TRANSLATE) else "es"
                    speech = gTTS(text=text_to_send, lang=tts_lang)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                        speech.save(tmp.name)
                        audio_path = tmp.name
                    st.audio(audio_path)
                    st.caption("🔊 Reproduciendo TTS")
                except Exception as e:
                    st.warning(f"No se pudo generar audio: {e}")
            else:
                st.info("Instala `gTTS` para activar audio (TTS).")

st.markdown("---")
with st.expander("ℹ️ Ayuda rápida", expanded=False):
    st.markdown("""
- **Broker / Puerto / Tópico**: define a dónde publicamos el texto reconocido.
- **Traducir a inglés**: usa `deep-translator` (evita `googletrans`, que rompe en Python 3.13).
- **Reproducir audio (gTTS)**: convierte el texto final a voz en el navegador.
- **Privacidad**: el reconocimiento corre en tu navegador (Web Speech), no subimos el audio.
    """)
