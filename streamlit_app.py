import streamlit as st
import json
import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import CSV handler
from api.csv_handler import save_user_response

# Load config
with open(Path(__file__).parent / "config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

st.set_page_config(
    page_title="Tal Cara, Tal Beat",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="collapsed"
)
st.logo("cruilla.png")
# CSS for touch screen and Cruilla Branding
st.markdown("""
<style>
    /* Fondo amarillo estilo Cruïlla para la aplicación principal */
    [data-testid="stAppViewContainer"] {
        background-color: #FFEA00; 
    }
    
    /* Hacer transparente el header por defecto de Streamlit para que no tape el fondo */
    [data-testid="stHeader"] {
        background-color: transparent;
    }

    /* Ajustar el color del texto principal a negro para mantener la identidad visual */
    .stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp div {
        color: #000000 !important;
    }
/* --- Estilos para los Emojis (Botones Terciarios) --- */
    button[data-testid="stBaseButton-tertiary"] {
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    
    /* Aumentar drásticamente el tamaño del emoji */
    button[data-testid="stBaseButton-tertiary"] p {
        font-size: 65px !important; 
        line-height: 1.2 !important;
        margin: 0 !important;
    }

    /* Efecto "pop" divertido al pasar el dedo o el ratón */
    button[data-testid="stBaseButton-tertiary"]:hover {
        transform: scale(1.15);
        transition: 0.2s ease-in-out;
    }

    /* Tamaños originales que tenías para pantallas táctiles */
    body {
        font-size: 18px;
    }
    button {
        font-size: 18px !important;
        padding: 20px 40px !important;
        border-radius: 10px !important;
        min-height: 80px;
        font-weight: bold !important;
    }
    
    .step-indicator {
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 30px;
        color: #000000;
        text-transform: uppercase;
        border-bottom: 3px solid #000000;
        display: inline-block;
        padding-bottom: 5px;
    }
    
    /* Estilizar los divisores para que sean negros y resalten */
    hr {
        border-color: #000000 !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "current_step" not in st.session_state:
    st.session_state.current_step = 1

if "user_answers" not in st.session_state:
    st.session_state.user_answers = {
        "mood": None,
        "instrument": None,
        "era": None
    }

if "session_id" not in st.session_state:
    st.session_state.session_id = None

if "artist_match" not in st.session_state:
    st.session_state.artist_match = None

if "generated_audio_path" not in st.session_state:
    st.session_state.generated_audio_path = None

if "user_photo" not in st.session_state:
    st.session_state.user_photo = None

def emoji_selector(question_id: str, question_config: dict) -> str:
    st.markdown(f'### {question_config["question"]}')
    
    selected = st.session_state.user_answers.get(question_id)
    
    # Show description of selected option
    if selected:
        for option in question_config["options"]:
            if option["value"] == selected:
                st.write(f"✓ **{option['ai_description']}**")
                break
    
    # Create columns for buttons
    cols = st.columns(4)
    
    # Render buttons
    for idx, option in enumerate(question_config["options"]):
        with cols[idx]:
            emoji = option["emoji"]
            value = option["value"]
            ai_desc = option["ai_description"]
            
            button_label = f"{emoji}\n✓" if selected == value else emoji
            
            if st.button(
                button_label,
                key=f"{question_id}_{idx}",
                use_container_width=True,
                help=ai_desc,
                type="tertiary"  # <--- THIS REMOVES THE BORDER AND BACKGROUND
            ):
                st.session_state.user_answers[question_id] = value
                st.rerun()
    
    return st.session_state.user_answers.get(question_id)

# ============ STEP 1: ONBOARDING ============
def step_1_onboarding():
    st.markdown('<div class="step-indicator">STEP 1 / 6: Your Profile</div>', unsafe_allow_html=True)
    st.markdown("## Let's get to know you! 🎤")
    
    # Question 1: Mood
    mood = emoji_selector("mood", config["onboarding_questions"][0])
    st.divider()
    
    # Question 2: Instrument
    instrument = emoji_selector("instrument", config["onboarding_questions"][1])
    st.divider()
    
    # Question 3: Era
    era = emoji_selector("era", config["onboarding_questions"][2])
    
    # Summary
    st.divider()
    st.markdown("### Your choices:")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if mood:
            mood_emoji = next(
                (opt["emoji"] for opt in config["onboarding_questions"][0]["options"] if opt["value"] == mood),
                "?"
            )
            st.markdown(f"**Mood**\n# {mood_emoji}")
    
    with col2:
        if instrument:
            instrument_emoji = next(
                (opt["emoji"] for opt in config["onboarding_questions"][1]["options"] if opt["value"] == instrument),
                "?"
            )
            st.markdown(f"**Instrument**\n# {instrument_emoji}")
    
    with col3:
        if era:
            era_emoji = next(
                (opt["emoji"] for opt in config["onboarding_questions"][2]["options"] if opt["value"] == era),
                "?"
            )
            st.markdown(f"**Era**\n# {era_emoji}")
    
    # Navigation buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back", use_container_width=True):
            st.session_state.current_step = max(1, st.session_state.current_step - 1)
            st.rerun()
    
    with col2:
        if st.button("Next →", use_container_width=True, type="primary"):
            if mood and instrument and era:
                # Save to CSV
                session_id = save_user_response(
                    mood=mood,
                    instrument=instrument,
                    era=era
                )
                st.session_state.session_id = session_id
                st.session_state.current_step = 2
                st.success(f"✅ Answers saved! Session: {session_id}")
                st.rerun()
            else:
                st.error("⚠️ Please answer all questions")


# ============ STEP 2: CAMERA ============
def step_2_camera():
    st.markdown('<div class="step-indicator">STEP 2 / 6: Your Photo</div>', unsafe_allow_html=True)
    st.markdown("## Get ready for the camera 📸")
    
    st.write("### Take a photo")
    picture = st.camera_input("Click to capture")
    
    if picture is not None:
        st.session_state.user_photo = picture
        st.success("✅ Photo captured!")
        st.image(picture, caption="Your photo", width=300)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📷 Retake", use_container_width=True):
                st.session_state.user_photo = None
                st.rerun()
        
        with col2:
            if st.button("← Back", use_container_width=True):
                st.session_state.current_step = 1
                st.rerun()
        
        with col3:
            if st.button("Next →", use_container_width=True, type="primary"):
                st.session_state.current_step = 3
                st.rerun()
    else:
        st.info("📸 Please take a photo to continue")
        
        if st.button("← Back", use_container_width=True):
            st.session_state.current_step = 1
            st.rerun()


# ============ STEP 3: FACIAL MATCH ============
def step_3_facial_match():
    st.markdown('<div class="step-indicator">STEP 3 / 6: Your Artist</div>', unsafe_allow_html=True)
    st.markdown("## Scanning artists... 🎭")
    
    st.info("ℹ️ Coming soon: Facial recognition to match your artist!\n\nFor now, we'll use a test artist.")
    
    if st.session_state.artist_match is None:
        st.session_state.artist_match = {
            "name": "Bad Bunny",
            "confidence": 78,
            "genre": "Urban Pop Reggaeton",
            "tribe": "La Calle"
        }
    
    artist = st.session_state.artist_match
    st.markdown(f"### You look like **{artist['name']}** ({artist['confidence']}%)")
    st.write(f"Genre: {artist['genre'].title()}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back", use_container_width=True):
            st.session_state.current_step = 2
            st.rerun()
    
    with col2:
        if st.button("Next →", use_container_width=True, type="primary"):
            st.session_state.current_step = 4
            st.rerun()

def step_4_generate_music():
    st.markdown('<div class="step-indicator">STEP 4 / 6: Your Song</div>', unsafe_allow_html=True)
    st.markdown("## Generating your unique melody 🎵")

    if st.button("🎵 Generate my song", use_container_width=True, type="primary"):
        with st.spinner("Creating your personalized song..."):
            try:
                from api.music_generator import generate_personalized_music

                artist      = st.session_state.artist_match
                user        = st.session_state.user_answers

                result = generate_personalized_music(
                    artist_name=artist["name"],
                    genre=artist["genre"],
                    tribe=artist.get("tribe", artist["genre"]),       # ← tribe
                    artist_confidence=artist.get("confidence", 50),   # ← confidence
                    mood=user.get("mood", "happy"),
                    instrument=user.get("instrument", "synth"),
                    fuel=user.get("era", "actual"),
                    duration=20,
                    output_dir="outputs",
                )

                if result["success"]:
                    st.session_state.generated_audio_path = result["audio_path"]
                    st.success("✅ Song generated!")
                    with st.expander("📝 Prompt used"):
                        st.markdown("**Tags:**")
                        st.code(result["tags"], language=None)
                        st.markdown("**Description:**")
                        st.write(result["description"])
                    st.audio(result["audio_path"])
                else:
                    st.error(f"❌ Error: {result['error']}")

            except Exception as e:
                st.error(f"❌ Error generating music: {str(e)}")

    if st.session_state.generated_audio_path:
        st.markdown("### 🎧 Your generated song:")
        st.audio(st.session_state.generated_audio_path)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back", use_container_width=True):
            st.session_state.current_step = 3
            st.rerun()
    with col2:
        if st.button("Next →", use_container_width=True, type="primary"):
            st.session_state.current_step = 5
            st.rerun()

# ============ STEP 5: TRIBE & RESULT ============
def step_5_tribe():
    st.markdown('<div class="step-indicator">STEP 5 / 6: Your Tribe</div>', unsafe_allow_html=True)
    
    artist = st.session_state.artist_match
    mood = st.session_state.user_answers.get("mood", "unknown")
    from api.music_generator import _norm
    tribe_key = _norm(artist.get("tribe", "los_salvajes"))
    tribe_info = config["tribes"].get(tribe_key, config["tribes"]["los_salvajes"])
    
    # Show photo if exists
    if st.session_state.user_photo is not None:
        st.image(st.session_state.user_photo, caption="Your photo", width=200)
        st.divider()
    
    # Summary
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"### You look like\n# {artist['name']}\n### at {artist['confidence']}%")
    
    with col2:
        mood_emoji = next(
            (opt["emoji"] for opt in config["onboarding_questions"][0]["options"] if opt["value"] == mood),
            "?"
        )
        st.markdown(f"### Your mood\n# {mood_emoji}")
    
    with col3:
        st.markdown(f"### Your Tribe\n# {tribe_info['emoji']}\n# {tribe_info['name']}")
    
    # Mini player
    if st.session_state.generated_audio_path:
        st.markdown("---")
        st.markdown("### 🎧 Your song:")
        st.audio(st.session_state.generated_audio_path)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back", use_container_width=True):
            st.session_state.current_step = 4
            st.rerun()
    
    with col2:
        if st.button("Next →", use_container_width=True, type="primary"):
            st.session_state.current_step = 6
            st.rerun()


# ============ STEP 6: DOWNLOAD & QR ============
def step_6_download():
    st.markdown('<div class="step-indicator">STEP 6 / 6: Take it home</div>', unsafe_allow_html=True)
    st.markdown("## Share your experience! 📱")
    
    artist = st.session_state.artist_match
    mood = st.session_state.user_answers.get("mood", "unknown")
    
    if st.session_state.user_photo is not None:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(st.session_state.user_photo, caption="Your photo", width=150)
        with col2:
            st.markdown(f"**Artist:** {artist['name']} ({artist['confidence']}%)")
            st.markdown(f"**Mood:** {mood}")
    
    st.markdown("---")
    st.markdown("### 🔗 Coming soon: QR code to download")
    st.info("- Your photo\n- Match percentage\n- Your generated song\n- Your tribe badge")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back", use_container_width=True):
            st.session_state.current_step = 5
            st.rerun()
    
    with col2:
        if st.button("🔄 Start again", use_container_width=True, type="primary"):
            st.session_state.current_step = 1
            st.session_state.user_answers = {
                "mood": None,
                "instrument": None,
                "era": None
            }
            st.session_state.artist_match = None
            st.session_state.generated_audio_path = None
            st.session_state.user_photo = None
            st.session_state.session_id = None
            st.rerun()


# ============ MAIN APP ============
def main():
    # Create 3 columns and put the image in the middle one to center it
    # Adjust the numbers [1, 2, 1] to make the logo bigger or smaller
    col1, col2, col3 = st.columns([1, 2, 1])
    # Optional: Center the title using HTML for a better layout
    st.markdown("<h1 style='text-align: center;'>🎵 Tal Cara, Tal Beat</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-style: italic;'>Discover your twin artist and generate your unique song</p>", unsafe_allow_html=True)
    st.divider()
    
    # Route to steps
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
