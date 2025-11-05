# app.py — Control por voz → MQTT (topic fijo: voice_alejandro)
import json
import time
import platform
import paho.mqtt.client as mqtt
import streamlit as st
from bokeh.models import Button, CustomJS
from streamlit_bokeh_events import streamlit_bokeh_events

# ---------------------------
# Config & Estilos (Dark UI)
# ---------------------------
st.set_page_config(page_title="Voz → MQTT", page_icon="🎙️", layout="centered")

DARK_CSS = """
<style>
/* fondo y tipografía */
html, body, [data-testid="stAppViewContainer"]{
  background: #000 !important; color: #fff !important;
}
h1,h2,h3,h4,h5,p,span,div,label { color:#fff !important; }
small, .markdown-text-container { color:#ddd !important; }

/* contenedores/paneles */
.block-container{ padding-top: 2rem; max-width: 880px; }
.stAlert{ background:#111; border:1px solid #2a2a2a; }
[data-testid="stSidebar"]{
  background:#0b0b0b !important; border-right: 1px solid #1a1a1a;
}

/* tarjetas */
.card{
  background:#0f0f10; border:1px solid #1f1f1f; border-radius:16px;
  padding:16px 18px; margin:10px 0;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.04) inset;
}

/* chips/pills */
.pill{
  display:inline-block; padding:6px 10px; border-radius:999px;
  background:#111; border:1px solid #2a2a2a; color:#e5e5e5;
  font-size:12px; letter-spacing:.3px;
}

/* botón primario */
.stButton > button{
  background:#111 !important; color:#fff !important;
  border:1px solid #2a2a2a !important; border-radius:999px !important;
  padding:10px 18px !important; font-weight:600;
}
.stButton > button:hover{ background:#151515 !important; }

/* input & select */
input, textarea{
  background:#0e0e0f !important; color:#fff !important;
  border:1px solid #2a2a2a !important; border-radius:10px !important;
}
</style>
"""
st.markdown(DARK_CSS, unsafe_allow_html=True)

# ---------------------------
# Encabezado
# ---------------------------
st.markdown("<span class='pill'>TELEMETRÍA POR VOZ</span>", unsafe_allow_html=True)
st.title("🎙️ Control de Voz → MQTT")

st.markdown(
    "<div class='card'>Habla y enviaremos el texto reconocido en formato JSON al tópico "
    "<b>voice_alejandro</b> del broker MQTT que elijas. "
    "Esto funciona en navegadores con <i>Web Speech API</i> (Chrome/Edge).</div>",
    unsafe_allow_html=True,
)

# ---------------------------
# Sidebar (config del broker)
# ---------------------------
with st.sidebar:
    st.subheader("⚙️ Conexión MQTT")
    broker = st.text_input("Broker", value="broker.mqttdashboard.com")
    port = st.number_input("Puerto", min_value=1, max_value=65535, value=1883, step=1)
    client_id = st.text_input("Client ID", value="voice-client")
    qos = st.selectbox("QoS", [0, 1, 2], index=0)
    retain = st.checkbox("Retain", value=False)

# Tópico fijo
topic = "voice_alejandro"
st.markdown(f"<span class='pill'>Topic fijo: {topic}</span>", unsafe_allow_html=True)

# ---------------------------
# Utilidades MQTT
# ---------------------------
def publish_text(text: str) -> tuple[bool, str]:
    """Publica {"Act1": <texto>} en el tópico fijo; devuelve (ok, msg)."""
    payload = {"Act1": text.strip()}
    try:
        client = mqtt.Client(client_id=client_id, clean_session=True)
        client.connect(broker, int(port), keepalive=60)
        rc, mid = client.publish(topic, json.dumps(payload), qos=int(qos), retain=retain)
        # Espera breve para asegurar el envío antes de desconectar
        client.loop_start()
        time.sleep(0.2)
        client.loop_stop()
        client.disconnect()
        if rc == mqtt.MQTT_ERR_SUCCESS:
            return True, f"Publicado ✅ → {topic} | {payload}"
        return False, f"Publicación con código {rc} (revisar conexión/credenciales)"
    except Exception as e:
        return False, f"Error publicando: {e}"

# ---------------------------
# Botón de micrófono (Bokeh)
# ---------------------------
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.subheader("🎤 Micrófono")

mic_btn = Button(label="Pulsa para dictar", width=240)
mic_btn.js_on_event(
    "button_click",
    CustomJS(
        code="""
        // Compatible con Chrome/Edge (webkitSpeechRecognition)
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if(!SR){
          document.dispatchEvent(new CustomEvent("GET_TEXT", {detail: "__NO_API__"}));
          return;
        }
        const r = new SR();
        r.continuous = true;
        r.interimResults = true;
        r.lang = "es-ES";
        let finalText = "";
        r.onresult = (e) => {
          for (let i=e.resultIndex; i<e.results.length; i++){
            const res = e.results[i];
            if(res.isFinal){ finalText += res[0].transcript; }
          }
          if(finalText.trim().length){
            document.dispatchEvent(new CustomEvent("GET_TEXT", {detail: finalText}));
            finalText = "";
          }
        };
        r.onerror = () => {
          document.dispatchEvent(new CustomEvent("GET_TEXT", {detail: "__ERR__"}));
        };
        r.start();
        """
    ),
)

result = streamlit_bokeh_events(
    mic_btn,
    events="GET_TEXT",
    key="mic",
    refresh_on_update=False,
    override_height=90,
    debounce_time=0,
)
st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------
# Procesa resultado del mic
# ---------------------------
if result and "GET_TEXT" in result:
    text = result["GET_TEXT"]
    if text == "__NO_API__":
        st.error("Tu navegador no soporta Web Speech API. Prueba con Chrome/Edge.")
    elif text == "__ERR__":
        st.error("Ocurrió un error con el reconocimiento de voz.")
    else:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("📝 Texto reconocido")
        st.write(text.strip())
        ok, msg = publish_text(text)
        (st.success if ok else st.error)(msg)
        st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------
# Alternativa: texto manual
# ---------------------------
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.subheader("⌨️ Enviar texto manual")
manual = st.text_input("Escribe el comando/frase a publicar", "")
send_btn = st.button("Enviar al tópico")
if send_btn:
    if manual.strip():
        ok, msg = publish_text(manual)
        (st.success if ok else st.error)(msg)
    else:
        st.warning("Escribe algo antes de enviar.")
st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------
# Meta/ayuda
# ---------------------------
with st.expander("ℹ️ Ayuda / Notas"):
    st.markdown(
        f"""
- **Python**: {platform.python_version()}
- Publica JSON con la forma `{{"Act1": "…"}}` en **`{topic}`**.
- Si el micro no funciona, usa el campo de texto manual.
- Revisa red/puerto (`{port}`) y que el broker acepte conexiones sin TLS.
        """
    )
