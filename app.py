import streamlit as st
import base64
import logging
from langchain_core.messages import HumanMessage
from agent_graph import graph

# =======================
#  CONFIGURACIÓN INICIAL 
# =======================
logging.basicConfig(level = logging.INFO, format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger('view_logger')

st.set_page_config(page_title = "Agente Post-Venta", page_icon = "🤖", layout = "centered")

# =======================
#   GESTIÓN DE ESTADO 
# =======================
if 'messages' not in st.session_state: 
    st.session_state.messages = []
if 'thread_id' not in st.session_state: 
    st.session_state.thread_id = "1"
if 'file_uploader_key' not in st.session_state: 
    st.session_state.file_uploader_key = 0

# =======================
#  FUNCIONES AUXILIARES
# =======================

def encode_image(uploaded_file):
    """Convierte archivo a Base64."""
    bytes_data = uploaded_file.getvalue()
    return base64.b64encode(bytes_data).decode('utf-8')

def mostrar_mensaje(msg):
    """Renderiza mensajes en el chat."""
    with st.chat_message(msg['role']):
        content = msg['content']
        if isinstance(content, str):
            st.markdown(content)
        elif isinstance(content, list):
            # Renderizado para bloques multimodal
            # Se itera sobre los bloques. Si se pusó la imagen primero en la lista, se renderiza primero
            for block in content:
                if block['type'] == 'image_url':
                    url = block['image_url']['url']
                    if url.startswith('data:image'):
                        st.image(url, width = 250) # Se quita el caption para que se vea más limpio como un chat
                elif block['type'] == 'text':
                    st.markdown(block['text'])

def manejar_respuesta_agente(inputs, config):
    """Ejecuta el grafo y maneja la respuesta."""
    with st.chat_message('assistant'):
        contenedor = st.empty()
        with st.spinner("🧠 Analizando caso y manuales..."):
            try:
                resultado = graph.invoke(inputs, config = config)
                respuesta = resultado.get('final_response', "⚠️ No se generó respuesta.")
                contenedor.markdown(respuesta)
                st.session_state.messages.append({
                    'role': 'assistant', 
                    'content': respuesta
                    }
                )
            except Exception as e:
                log.error(f"    Error: {e}", exc_info = True)
                contenedor.error(f"Ocurrió un error técnico: {str(e)}")

# =======================
#        SIDEBAR
# =======================
with st.sidebar:
    st.header("⚙️ Contexto del Caso")
    producto = st.selectbox(
        'Producto sobre el que consultas:', 
        ('Seleccionar...', 'ROG Xbox Ally X', 'Lavadora Secadora EcoBubble', 'Refrigerador French Door', 'TV OLED S95F 4K')
    )
    problema = st.selectbox(
        'Tipo de Consulta:', 
        ('Uso Técnico / Fallas', 'Garantía', 'Devolución')
    )
    
    st.divider()
    if st.button("🗑️ Reiniciar Conversación", use_container_width = True):
        st.session_state.messages = []
        st.session_state.file_uploader_key += 1 # Limpia el adjunto si había uno
        st.session_state.thread_id = st.session_state.get('thread_id', '1') + '_new'
        st.rerun()

st.title("🛠️ Asistente técnico")
st.caption(f"Asistiendo sobre: **{producto}** | Caso: **{problema}**")

# ============================
#  RENDERIZADO DEL HISTORIAL
# ============================
for msg in st.session_state.messages:
    mostrar_mensaje(msg)

# =======================
#     ZONA DE INPUT
# =======================
col_file, col_text = st.columns([0.1, 0.9], gap = 'small')
archivo = None

with col_file:
    # El uploader vive dentro del popover para no ocupar espacio
    with st.popover("📎", use_container_width = True, help = "Adjuntar imagen (Requiere texto)"):
        archivo = st.file_uploader(
            "Subir foto", 
            type = ['jpg', 'png', 'jpeg'],
            key = f"uploader_{st.session_state.file_uploader_key}" 
        )

# Feedback visual en el placeholder
placeholder_text = "Describe el problema aquí..."
if archivo:
    placeholder_text = "📸 Foto adjunta. Escribe un mensaje para enviarla..."

prompt = st.chat_input(placeholder_text)

# ============================
#   LÓGICA DE PROCESAMIENTO
# ============================
if prompt:
    if producto == 'Seleccionar...':
        st.warning("⚠️ Por favor selecciona un producto en el menú lateral para poder ayudarte mejor.")
        st.stop()

    # Preparar imagen (Si existe)
    img_b64 = None
    if archivo:
        img_b64 = encode_image(archivo)

    # Gestión de lo visual. Lo que ve el usuario en el chat
    # Se crea una lista explícita para el frontend
    if img_b64:
        contenido_visual = [
            # Imagen primero para que salga arriba
            {'type': 'image_url', 'image_url': {'url': f"data:image/jpeg;base64,{img_b64}"}},
            # Texto después
            {'type': 'text', 'text': prompt}
        ]
    else:
        # Si no hay imagen, es solo texto simple
        contenido_visual = prompt
    
    # Se guarda y muestra lo visual
    st.session_state.messages.append({'role': 'user', 'content': contenido_visual})
    mostrar_mensaje({'role': 'user', 'content': contenido_visual})

    # ==========================================
    # GESTIÓN LÓGICA (Lo que se envía al Agente)
    # ==========================================
    # Al agente se le manda el contexto del sistema oculto, que no se quiere mostrar en el chat
    contexto_sistema = f"""
    [META-DATA DEL SISTEMA]
    Producto Seleccionado: {producto}
    Tipo de Consulta: {problema}
    -----------------------
    """
    texto_final_agente = f"{contexto_sistema}\nConsulta del Usuario: {prompt}"
    bloques_agente = [{'type': 'text', 'text': texto_final_agente}]
    
    if img_b64:
        bloques_agente.append({
            'type': 'image_url', 
            'image_url': {'url': f"data:image/jpeg;base64,{img_b64}"}
        })
        log.info("    Input multimodal enviado al agente.")

    inputs = {
        'messages': [HumanMessage(content = bloques_agente)],
        'input_type': 'image' if archivo else 'text',
        'num_retries': 0
    }
    config = {'configurable': {'thread_id': st.session_state.thread_id}}

    manejar_respuesta_agente(inputs, config)

    # ============
    #   LIMPIEZA
    # ============
    if archivo:
        st.session_state.file_uploader_key += 1
        st.rerun()