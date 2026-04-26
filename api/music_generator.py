"""
Módulo para generar música personalizada basada en:
- Artista matching
- Respuestas de usuario (mood, instrumento, fuel/género)
- Parámetros de ACE-Step

Las respuestas de usuario se traducen a descripciones para la IA.
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any

# Add ACE-Step path
CHECKPOINTS_DIR = Path(__file__).parent.parent / "models" / "models" / "ace-step"
ACE_STEP_DIR = Path(__file__).parent.parent / "models" / "models" / "ACE-Step-1.5"
sys.path.insert(0, str(ACE_STEP_DIR))

from acestep.handler import AceStepHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music

# Load config para obtener traducciones de emojis
CONFIG_PATH = Path(__file__).parent / ".." / "ui" / "config.json"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    UI_CONFIG = json.load(f)


def get_emoji_translation(question_id: str, value: str) -> str:
    """
    Obtiene la descripción en AI para un emoji seleccionado.
    
    Args:
        question_id: 'mood', 'instrument', 'fuel'
        value: valor del emoji seleccionado
    
    Returns:
        String con la descripción para la IA
    """
    questions = {q["id"]: q for q in UI_CONFIG["onboarding_questions"]}
    question = questions.get(question_id)
    
    if question:
        for option in question["options"]:
            if option["value"] == value:
                return option["ai_description"]
    
    return value


def build_music_prompt(
    artist_name: str,
    genre: str,
    mood: str,
    instrument: str,
    fuel: str,
) -> str:
    """
    Construye un prompt descriptivo para la generación de música.
    
    Integra:
    - Estilo del artista matching
    - Mood del usuario (🔥 🫠 👽 🤪)
    - Instrumento preferido (🎸 🎛️ 🎷 🥁)
    - Fuel/Actitud (🍻 💧 🍕 🍹)
    
    Args:
        artist_name: Nombre del artista para el estilo
        genre: Género musical
        mood: Valor mood (energetic, chill, experimental, chaotic)
        instrument: Valor instrument (guitar, synth, funk, drums)
        fuel: Valor fuel (stadium, pop, heavy, tropical)
    
    Returns:
        String con el prompt para ACE-Step
    """
    
    # Traducir emojis a descripciones
    mood_desc = get_emoji_translation("mood", mood)
    instrument_desc = get_emoji_translation("instrument", instrument)
    fuel_desc = get_emoji_translation("fuel", fuel)
    
    # Construir prompt combinando todas las características
    prompt = (
        f"Create an instrumental track in the style of {artist_name}. "
        f"Genre: {genre}. "
        f"\n"
        f"Mood characteristics: {mood_desc}. "
        f"\n"
        f"Instrumentation: {instrument_desc}. "
        f"\n"
        f"Overall vibe: {fuel_desc}. "
        f"\n"
        f"Festival atmosphere, perfect for celebration and dancing. "
        f"Duration: 15-30 seconds."
    )
    
    return prompt


def generate_personalized_music(
    artist_name: str,
    genre: str,
    mood: str,
    instrument: str,
    fuel: str,
    duration: int = 15,
    output_dir: str = "outputs",
    device: str = "cuda",
) -> Dict[str, Any]:
    """
    Genera música personalizada usando ACE-Step.
    
    Args:
        artist_name: Nombre del artista matching
        genre: Género musical
        mood: Valor mood del usuario
        instrument: Valor instrumento del usuario
        fuel: Valor combustible/género del usuario
        duration: Duración en segundos (default: 15)
        output_dir: Directorio para guardar audio
        device: 'cuda' o 'cpu'
    
    Returns:
        Dict con {success: bool, audio_path: str, prompt: str, error: str}
    """
    
    try:
        # Construir prompt
        prompt = build_music_prompt(
            artist_name=artist_name,
            genre=genre,
            mood=mood,
            instrument=instrument,
            fuel=fuel,
        )
        
        print(f"📝 Prompt generado:\n{prompt}\n")
        
        # Inicializar handler de ACE-Step
        print(f"🚀 Inicializando ACE-Step (device: {device})...")
        dit_handler = AceStepHandler()
        dit_handler.initialize_service(
            project_root=str(CHECKPOINTS_DIR),
            config_path="acestep-v15-turbo",
            device=device,
        )
        
        # Configurar parámetros de generación
        params = GenerationParams(
            caption=prompt,
            lyrics="",
            duration=duration,
            bpm=128,
            vocal_language="en",
        )
        
        config = GenerationConfig(
            batch_size=1,
            audio_format="wav",
        )
        
        # Generar música
        print(f"🎵 Generando música ({duration}s)...")
        result = generate_music(
            dit_handler,
            None,
            params,
            config,
            save_dir=output_dir
        )
        
        if result.success:
            print(f"✅ Generado: {result.audio_path}")
            return {
                "success": True,
                "audio_path": str(result.audio_path),
                "prompt": prompt,
                "error": None
            }
        else:
            error_msg = getattr(result, 'error', 'Unknown error')
            print(f"❌ Error: {error_msg}")
            return {
                "success": False,
                "audio_path": None,
                "prompt": prompt,
                "error": str(error_msg)
            }
    
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "audio_path": None,
            "prompt": None,
            "error": str(e)
        }


if __name__ == "__main__":
    # Test
    result = generate_personalized_music(
        artist_name="Bad Bunny",
        genre="reggaeton",
        mood="energetic",
        instrument="synth",
        fuel="stadium",
        duration=15,
        device="cuda"
    )
    
    print(f"\nResultado: {result}")
