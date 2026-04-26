import streamlit as st
import json
import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load config
with open(Path(__file__).parent / "config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

st.set_page_config(
    page_title="Tal Cara, Tal Beat",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS personalizado para pantalla táctil
st.markdown("""
<style>
    body {
        font-size: 18px;
    }
    button {
        font-size: 18px;
        padding: 20px 40px;
        border-radius: 10px;
    }
    .stRadio > label {
        font-size: 18px;
        padding: 15px;
    }
    .step-indicator {
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 30px;
    }
    .question-title {
        font-size: 32px;
        font-weight: bold;
        margin-bottom: 40px;
        text-align: center;
    }
    .emoji-button {
        display: inline-block;
        width: 150px;
        height: 150px;
        margin: 20px;
        font-size: 80px;
        border: 4px solid #ddd;
        border-radius: 20px;
        background-color: #f0f0f0;
        cursor: pointer;
        transition: all 0.3s ease;
        text-align: center;
        line-height: 150px;
    }
    .emoji-button:hover {
        transform: scale(1.1);
        border-color: #ff6b6b;
        background-color: #ffe0e0;
    }
    .emoji-button.selected {
        border-color: #4CAF50;
        background-color: #c8e6c9;
        transform: scale(1.15);
    }
    .emoji-container {
        display: flex;
        justify-content: center;
        gap: 20px;
        flex-wrap: wrap;
        margin: 40px 0;
    }
</style>
""", unsafe_allow_html=True)

# Inicializar session state
if "current_step" not in st.session_state:
    st.session_state.current_step = 1

if "user_answers" not in st.session_state:
    st.session_state.user_answers = {
        "mood": None,
        "instrument": None,
        "fuel": None
    }

if "artist_match" not in st.session_state:
    st.session_state.artist_match = None

if "generated_audio_path" not in st.session_state:
    st.session_state.generated_audio_path = None


def emoji_selector(question_id: str, question_config: dict) -> str:
    """
    Crea un selector visual de emojis gigantes.
    Retorna el valor (value) del emoji seleccionado.
    """
    st.markdown(f'<div class="question-title">{question_config["question"]}</div>', unsafe_allow_html=True)
    
    # Crear columnas para mostrar emojis
    cols = st.columns(4)
    selected = st.session_state.user_answers.get(question_id)
    
    # Mostrar cada opción como botón de emoji
    html_content = '<div class="emoji-container">'
    for idx, option in enumerate(question_config["options"]):
        emoji = option["emoji"]
        value = option["value"]
        ai_desc = option["ai_description"]
        
        # Crear botón HTML + JavaScript
        html_content += f'''
        <div onclick="handleEmojiClick('{question_id}', '{value}', this)" 
             class="emoji-button {'selected' if selected == value else ''}" 
             title="{ai_desc}">
            {emoji}
        </div>
        '''
    
    html_content += '</div>'
    st.markdown(html_content, unsafe_allow_html=True)
    
    # Usar columnas para botones interactivos
    for idx, option in enumerate(question_config["options"]):
        with cols[idx]:
            emoji = option["emoji"]
            value = option["value"]
            
            if st.button(emoji, key=f"{question_id}_{idx}", use_container_width=True):
                st.session_state.user_answers[question_id] = value
                st.rerun()
    
    return st.session_state.user_answers[question_id]


# ============ PASO 1: ONBOARDING ============
def step_1_onboarding():
    st.markdown('<div class="step-indicator">PASO 1 / 6: Tu Perfil</div>', unsafe_allow_html=True)
    
    # Pregunta 1: Mood
    mood = emoji_selector("mood", config["onboarding_questions"][0])
    
    st.divider()
    
    # Pregunta 2: Instrumento
    instrument = emoji_selector("instrument", config["onboarding_questions"][1])
    
    st.divider()
    
    # Pregunta 3: Fuel/Género
    fuel = emoji_selector("fuel", config["onboarding_questions"][2])
    
    # Resumen
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if mood:
            mood_emoji = next(
                (opt["emoji"] for opt in config["onboarding_questions"][0]["options"] if opt["value"] == mood),
                "?"
            )
            st.markdown(f"### Mood\n# {mood_emoji}")
    
    with col2:
        if instrument:
            instrument_emoji = next(
                (opt["emoji"] for opt in config["onboarding_questions"][1]["options"] if opt["value"] == instrument),
                "?"
            )
            st.markdown(f"### Instrumento\n# {instrument_emoji}")
    
    with col3:
        if fuel:
            fuel_emoji = next(
                (opt["emoji"] for opt in config["onboarding_questions"][2]["options"] if opt["value"] == fuel),
                "?"
            )
            st.markdown(f"### Combustible\n# {fuel_emoji}")
    
    # Botones de navegación
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Atrás", use_container_width=True):
            st.session_state.current_step = max(1, st.session_state.current_step - 1)
            st.rerun()
    
    with col2:
        if st.button("Siguiente →", use_container_width=True, type="primary"):
            if mood and instrument and fuel:
                st.session_state.current_step = 2
                st.rerun()
            else:
                st.error("⚠️ Por favor responde todas las preguntas")


# ============ PASO 2: CAPTURA (placeholder) ============
def step_2_camera():
    st.markdown('<div class="step-indicator">PASO 2 / 6: Tu Foto</div>', unsafe_allow_html=True)
    st.markdown('<div class="question-title">Prepárate para la cámara 📸</div>', unsafe_allow_html=True)
    
    st.info("ℹ️ Próximamente: Captura facial con cámara del stand\n\nDe momento, continuaremos sin foto.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Atrás", use_container_width=True):
            st.session_state.current_step = 1
            st.rerun()
    
    with col2:
        if st.button("Siguiente →", use_container_width=True, type="primary"):
            st.session_state.current_step = 3
            st.rerun()


# ============ PASO 3: MATCH FACIAL (placeholder) ============
def step_3_facial_match():
    st.markdown('<div class="step-indicator">PASO 3 / 6: Tu Artista</div>', unsafe_allow_html=True)
    st.markdown('<div class="question-title">Escaneando artistas... 🎭</div>', unsafe_allow_html=True)
    
    st.info("ℹ️ Próximamente: Matching facial con reconocimiento de caras\n\nDe momento, usaremos un artista de prueba.")
    
    # Para testing, simulamos un match
    if st.session_state.artist_match is None:
        st.session_state.artist_match = {
            "name": "Bad Bunny",
            "confidence": 78,
            "genre": "reggaeton",
            "tribe": "hip_hop"
        }
    
    artist = st.session_state.artist_match
    st.markdown(f"### Te pareces a **{artist['name']}** al {artist['confidence']}%")
    st.write(f"Género: {artist['genre'].title()}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Atrás", use_container_width=True):
            st.session_state.current_step = 2
            st.rerun()
    
    with col2:
        if st.button("Siguiente →", use_container_width=True, type="primary"):
            st.session_state.current_step = 4
            st.rerun()


# ============ PASO 4: GENERAR MÚSICA ============
def step_4_generate_music():
    st.markdown('<div class="step-indicator">PASO 4 / 6: Tu Canción</div>', unsafe_allow_html=True)
    st.markdown('<div class="question-title">Generando tu melodía única 🎵</div>', unsafe_allow_html=True)
    
    if st.button("🎵 Generar mi canción", use_container_width=True, type="primary"):
        with st.spinner("Creando tu canción personalizada..."):
            try:
                # Importar el generador de música
                from api.music_generator import generate_personalized_music
                
                # Obtener respuestas del usuario
                artist_name = st.session_state.artist_match["name"]
                genre = st.session_state.artist_match["genre"]
                mood_value = st.session_state.user_answers.get("mood", "energetic")
                instrument_value = st.session_state.user_answers.get("instrument", "synth")
                fuel_value = st.session_state.user_answers.get("fuel", "stadium")
                
                # Llamar generador
                result = generate_personalized_music(
                    artist_name=artist_name,
                    genre=genre,
                    mood=mood_value,
                    instrument=instrument_value,
                    fuel=fuel_value,
                    duration=15,
                    output_dir="outputs"
                )
                
                if result["success"]:
                    st.session_state.generated_audio_path = result["audio_path"]
                    st.success("✅ ¡Canción generada!")
                    st.info(f"📝 Prompt usado:\n{result['prompt']}")
                    st.audio(result["audio_path"])
                else:
                    st.error(f"❌ Error: {result['error']}")
            
            except Exception as e:
                st.error(f"❌ Error al generar música: {str(e)}")
    
    # Mostrar audio si ya fue generado
    if st.session_state.generated_audio_path:
        st.markdown("### 🎧 Tu canción generada:")
        st.audio(st.session_state.generated_audio_path)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Atrás", use_container_width=True):
            st.session_state.current_step = 3
            st.rerun()
    
    with col2:
        if st.button("Siguiente →", use_container_width=True, type="primary"):
            st.session_state.current_step = 5
            st.rerun()


# ============ PASO 5: TRIBU & RESULTADO ============
def step_5_tribe():
    st.markdown('<div class="step-indicator">PASO 5 / 6: Tu Tribu</div>', unsafe_allow_html=True)
    
    artist = st.session_state.artist_match
    mood = st.session_state.user_answers.get("mood", "unknown")
    tribe_key = artist.get("tribe", "pop")
    tribe_info = config["tribes"].get(tribe_key, config["tribes"]["pop"])
    
    # Resumen visual
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"### Te pareces a\n# {artist['name']}\n### al {artist['confidence']}%")
    
    with col2:
        mood_emoji = next(
            (opt["emoji"] for opt in config["onboarding_questions"][0]["options"] if opt["value"] == mood),
            "?"
        )
        st.markdown(f"### Tu mood\n# {mood_emoji}")
    
    with col3:
        st.markdown(f"### Tu Tribu\n# {tribe_info['emoji']}\n# {tribe_info['name']}")
    
    # Mini player
    if st.session_state.generated_audio_path:
        st.markdown("---")
        st.markdown("### 🎧 Tu canción:")
        st.audio(st.session_state.generated_audio_path)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Atrás", use_container_width=True):
            st.session_state.current_step = 4
            st.rerun()
    
    with col2:
        if st.button("Siguiente →", use_container_width=True, type="primary"):
            st.session_state.current_step = 6
            st.rerun()


# ============ PASO 6: DESCARGAR & QR ============
def step_6_download():
    st.markdown('<div class="step-indicator">PASO 6 / 6: Llévate tu Resultado</div>', unsafe_allow_html=True)
    st.markdown('<div class="question-title">¡Comparte tu experiencia! 📱</div>', unsafe_allow_html=True)
    
    st.markdown("### 🔗 Próximamente: QR para descargar")
    st.info("- Tu foto\n- Porcentaje de match\n- Tu canción generada\n- Tu insignia de tribu")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Atrás", use_container_width=True):
            st.session_state.current_step = 5
            st.rerun()
    
    with col2:
        if st.button("🔄 Empezar de nuevo", use_container_width=True, type="primary"):
            st.session_state.current_step = 1
            st.session_state.user_answers = {
                "mood": None,
                "instrument": None,
                "fuel": None
            }
            st.session_state.artist_match = None
            st.session_state.generated_audio_path = None
            st.rerun()


# ============ MAIN APP ============
def main():
    # Header
    st.markdown("# 🎵 Tal Cara, Tal Beat")
    st.markdown("*Descubre tu artista gemelo y genera tu canción única*")
    st.divider()
    
    # Router de pasos
    if st.session_state.current_step == 1:
        step_1_onboarding()
    elif st.session_state.current_step == 2:
        step_2_camera()
    elif st.session_state.current_step == 3:
        step_3_facial_match()
    elif st.session_state.current_step == 4:
        step_4_generate_music()
    elif st.session_state.current_step == 5:
        step_5_tribe()
    elif st.session_state.current_step == 6:
        step_6_download()


if __name__ == "__main__":
    main()
