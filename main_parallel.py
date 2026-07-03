"""
Tal Cara, Tal Beat — main pipeline (Parallel Version).

Usage:
    python main.py --image inputs/user.png --mood hype --instrument drums --era actual --casa techno --with-music --language es
"""

import argparse
import os
import sys
import time
import unicodedata
from pathlib import Path
import concurrent.futures  # <--- Manejo de hilos en paralelo

# ── Repo root & module paths ───────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "face2label" / "models"))
sys.path.insert(0, str(REPO_ROOT / "models" / "ACE-Step-1.5"))

# ── Default artifact paths ─────────────────────────────────────────────────
MODEL_PATH       = REPO_ROOT / "face2label" / "logs" / "artists_mlp.pth"
LABELS_PATH      = REPO_ROOT / "face2label" / "logs" / "labels.json"
METADATA_PATH    = Path("/home/spG07/data/Fake_Artist.csv")
ASSET_DIR        = REPO_ROOT / "inputs"
OUTPUT_DIR       = REPO_ROOT / "outputs"
OUTPUT_IMAGES_DIR = OUTPUT_DIR / "images"
OUTPUT_MUSIC_DIR  = OUTPUT_DIR / "music"
OUTPUT_VIDEO_DIR  = OUTPUT_DIR / "final_video"

# ── Canonical tribes: urban · indie · rock · pop · tecno ───────────────────
TRIBE_BACKGROUNDS: dict[str, dict[str, str]] = {
    lang: {
        "urban": str(ASSET_DIR / lang / "bg_urban.png"),
        "indie": str(ASSET_DIR / lang / "bg_indie.png"),
        "rock":  str(ASSET_DIR / lang / "bg_rockstar.png"),
        "pop":   str(ASSET_DIR / lang / "bg_pop.png"),
        "tecno": str(ASSET_DIR / lang / "bg_tecno.png"),
    }
    for lang in ("ca", "es", "en")
}

TEXT_BAND_FRACTION = 0.22
SUBJECT_HEIGHT_FRACTION = 0.72

# ── Helper ─────────────────────────────────────────────────────────────────
def _normalise_tribe(raw: str) -> str:
    nfkd = unicodedata.normalize("NFKD", raw.strip())
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()

# ==============================================================================
# STEP 1 — FACE -> ARTIST LABEL
# ==============================================================================
def step_face2label(image_path: str) -> dict | None:
    from predictor import ArtistPredictor

    predictor = ArtistPredictor(
        model_path=str(MODEL_PATH),
        labels_path=str(LABELS_PATH),
        metadata_path=str(METADATA_PATH),
    )

    result = predictor.predict(image_path)

    if result is None:
        print("[face2label] No face detected.")
        return None

    print(f"[face2label] Matched: {result['name']}  "
          f"({result['confidence']}%)  "
          f"genre: {result['genre']}  "
          f"tribe: {result.get('tribe', 'unknown')}")
    return result

# ==============================================================================
# STEP 2 — CLOTHING / ACCESSORY OVERLAY
# ==============================================================================
def step_clothing(user_image_path: str, artist_match: dict, output_path: str) -> str | None:
    from clothing.Clothing import apply_look

    return apply_look(
        user_image_path=user_image_path,
        artist_name=artist_match["name"],
        output_path=output_path,
        csv_path=str(METADATA_PATH),
        asset_dir=str(ASSET_DIR),
    )

# ==============================================================================
# STEP 3 — MUSIC GENERATION (A.1 - Solo respuestas del cuestionario)
# ==============================================================================
def step_music(
    mood: str,
    instrument: str,
    era: str,
    casa: str,
) -> dict | None:
    from api.music_generator import build_ace_prompt
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationParams, GenerationConfig, generate_music

    save_dir = str(OUTPUT_MUSIC_DIR)
    os.makedirs(save_dir, exist_ok=True)

    # Construimos el prompt de 25 segundos mapeando la casa al parámetro 'genre'
    prompt_data = build_ace_prompt(
        mood=mood,
        instrument=instrument,
        era=era,
        genre=casa,
        duration_seconds=25,
    )

    print(f"[music] Generando pista instrumental para Casa: {casa.upper()}...")
    t0 = time.perf_counter()

    handler = AceStepHandler()
    handler.initialize_service(
        project_root=None,
        config_path="acestep-v15-turbo",
        device="cuda",
    )

    params = GenerationParams(
        caption=prompt_data["tags"] + ". " + prompt_data["description"],
        lyrics="",
        duration=25,
        bpm=80,
    )
    gen_config = GenerationConfig(batch_size=1, audio_format="wav")

    result = generate_music(handler, None, params, gen_config, save_dir=save_dir)
    print(f"[music] Terminado en {time.perf_counter() - t0:.2f}s")

    if result.success:
        audio_path = result.audios[0]["path"] if result.audios else None
        return {"success": True, "audio_path": audio_path}
    else:
        return {"success": False, "error": result.error}

# ==============================================================================
# STEP 4 — TRIBE BACKGROUND COMPOSITE
# ==============================================================================
def step_background(
    user_image_path: str,
    artist_match: dict,
    output_path: str,
    language: str = "ca" 
) -> str | None:
    try:
        from rembg import remove
        from PIL import Image
    except ImportError as e:
        print(f"[background] Missing dependency: {e}")
        return None

    raw_tribe  = artist_match.get("tribe", "")
    tribe_key  = _normalise_tribe(raw_tribe)             
    
    lang_backgrounds = TRIBE_BACKGROUNDS.get(language, TRIBE_BACKGROUNDS["ca"])
    bg_path = lang_backgrounds.get(tribe_key)

    if bg_path is None or not Path(bg_path).exists():
        return None

    background = Image.open(bg_path).convert("RGBA")
    bg_w, bg_h = background.size

    import numpy as np
    from PIL import ImageFilter

    user_img = Image.open(user_image_path)
    subject  = remove(user_img)
    if subject.mode != "RGBA":
        subject = subject.convert("RGBA")

    alpha_arr    = np.array(subject.split()[3], dtype=np.uint8)
    alpha_binary = np.where(alpha_arr >= 100, 255, 0).astype(np.uint8)
    alpha_edge   = Image.fromarray(alpha_binary).filter(ImageFilter.GaussianBlur(1.5))
    r, g, b, _   = subject.split()
    subject      = Image.merge("RGBA", (r, g, b, alpha_edge))

    text_band_px = int(bg_h * TEXT_BAND_FRACTION) 
    usable_h     = bg_h - text_band_px             

    target_h = int(usable_h * SUBJECT_HEIGHT_FRACTION)
    scale    = target_h / subject.height
    target_w = int(subject.width * scale)
    subject  = subject.resize((target_w, target_h), Image.LANCZOS)

    paste_x = (bg_w - target_w) // 2
    paste_y = usable_h - target_h      

    composite = background.copy()
    composite.paste(subject, (paste_x, paste_y), subject)   

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    composite.convert("RGB").save(output_path, quality=95)
    print(f"[background] ✓ Póster guardado → {output_path}")
    return output_path

# ==============================================================================
# STEP 5 — VIDEO GENERATION
# ==============================================================================
def step_video(image_path: str, audio_path: str, output_path: str) -> str | None:
    try:
        from moviepy import ImageClip, AudioFileClip
    except ImportError as e:
        print(f"[video] Missing dependency: {e}")
        return None

    try:
        audio = AudioFileClip(audio_path)
        video = ImageClip(image_path, duration=audio.duration).with_audio(audio)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        video.write_videofile(
            output_path, fps=1, codec="libx264", audio_codec="aac", logger=None,
        )
        video.close()
        audio.close()
        print(f"[video] ✓ Video final guardado → {output_path}")
        return output_path
    except Exception as e:
        print(f"[video] ✗ Error: {e}")
        return None

# ==============================================================================
# WORKFLOW DE IMAGEN (A.2 y B - Mapeo facial, Complementos y Polaroid)
# ==============================================================================
def workflow_crea_polaroid(image_path: str, output_path: str, language: str, timings: dict) -> dict:
    stem = Path(image_path).stem
    
    # A.2 Mapping del artista basado en la foto
    t_start = time.perf_counter()
    artist_match = step_face2label(image_path)
    timings["step_face2label"] = time.perf_counter() - t_start

    if not artist_match:
        return {"success": False, "error": "No face detected"}

    # B.1 Colocar los complementos/ropa sobre el usuario usando landmarks
    t_start = time.perf_counter()
    styled_path = step_clothing(image_path, artist_match, output_path)
    timings["step_clothing"] = time.perf_counter() - t_start

    working_image = styled_path if styled_path else image_path

    # B.2 Crear la Polaroid uniendo el usuario recortado y el fondo de su casa/tribu
    poster_output = str(OUTPUT_IMAGES_DIR / f"{stem}_tribe_poster_{language}.png")
    t_start = time.perf_counter()
    tribe_poster = step_background(
        user_image_path=working_image, artist_match=artist_match, output_path=poster_output, language=language
    )
    timings["step_background"] = time.perf_counter() - t_start

    return {
        "success": True,
        "artist_match": artist_match,
        "styled_image": styled_path,
        "tribe_poster": tribe_poster
    }

# ==============================================================================
# PIPELINE ORCHESTRATOR (Coordinador de Concurrencia)
# ==============================================================================
def run_pipeline(
    image_path: str,
    output_path: str | None = None,
    mood: str = "happy",
    instrument: str = "synth",
    era: str = "actual",
    casa: str = "pop",
    language: str = "ca",
    skip_music: bool = True,
) -> dict:
    OUTPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_IMAGES_DIR.mkdir(exist_ok=True)
    OUTPUT_MUSIC_DIR.mkdir(exist_ok=True)
    OUTPUT_VIDEO_DIR.mkdir(exist_ok=True)

    stem = Path(image_path).stem
    if output_path is None:
        output_path = str(OUTPUT_IMAGES_DIR / f"{stem}_styled_{language}.png")

    timings = {}
    music_result = None
    image_result = None

    print("\n" + "="*60)
    print(" PROCESAMIENTO EN PARALELO (concurrent.futures)")
    print("="*60)

    # Disparamos los dos hilos simultáneamente
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        
        # HILO 1: Generación de Música (Basado en respuestas)
        if not skip_music:
            future_music = executor.submit(step_music, mood, instrument, era, casa)
        else:
            future_music = None

        # --- SIMULACIÓN DEL RETRASO DE LA CÁMARA (Opcional) ---
        # Si la foto de la cámara tarda 10s en llegar, puedes descomentar la siguiente línea:
        # time.sleep(10)

        # HILO 2: Flujo de Imagen (Face mapping, complementos y composición de Polaroid)
        future_image = executor.submit(workflow_crea_polaroid, image_path, output_path, language, timings)

        # Recogemos los resultados sincrónicamente (espera a que ambos terminen)
        if future_music:
            t_wait_music = time.perf_counter()
            music_result = future_music.result()
            timings["step_music_async_wait"] = time.perf_counter() - t_wait_music
        else:
            timings["step_music_async_wait"] = 0.0

        image_result = future_image.result()

    # Si el flujo de imagen falló, cancelamos
    if not image_result.get("success"):
        return {"success": False, "error": image_result.get("error"), "timings": timings}

    artist_match = image_result["artist_match"]
    tribe_poster = image_result["tribe_poster"]

    # ── PASO C: CREAR VIDEO FINAL ──
    # Una vez tenemos la Polaroid (Hilo 2) y el Audio (Hilo 1), los unificamos
    final_video = None
    audio_path = music_result.get("audio_path") if music_result and music_result.get("success") else None
    
    if tribe_poster and audio_path:
        print("\n🎬 UNIFICANDO HILOS: Mezclando Polaroid y Música en Video Final...")
        t_start = time.perf_counter()
        video_output = str(OUTPUT_VIDEO_DIR / f"{stem}_final_{language}.mp4")
        final_video = step_video(tribe_poster, audio_path, video_output)
        timings["step_video"] = time.perf_counter() - t_start
    else:
        timings["step_video"] = 0.0

    return {
        "success":      True,
        "artist_match": artist_match,
        "styled_image": image_result["styled_image"],
        "tribe_poster": tribe_poster,
        "music":        music_result,
        "final_video":  final_video,
        "timings":      timings,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Festival Cruilla — Tal Cara, Tal Beat")
    parser.add_argument("--image",      required=True,  help="Ruta a la foto del usuario")
    parser.add_argument("--output",     default=None,   help="Ruta de salida de imagen estilizada")
    parser.add_argument("--mood",       default="happy")
    parser.add_argument("--instrument", default="synth")
    parser.add_argument("--era",        default="actual")
    parser.add_argument("--casa",       default="pop", choices=["indie", "pop", "rock", "techno", "urban"])
    parser.add_argument("--language",   default="ca", choices=["en", "es", "ca"])
    parser.add_argument("--with-music", action="store_true", help="Generar música en paralelo")
    args = parser.parse_args()

    total_start = time.perf_counter()
    
    result = run_pipeline(
        image_path=args.image, output_path=args.output,
        mood=args.mood, instrument=args.instrument, era=args.era, casa=args.casa,
        language=args.language, skip_music=not args.with_music,
    )
    
    total_duration = time.perf_counter() - total_start

    if result["success"]:
        print("\n" + "="*50)
        print(" PIPELINE COMPLETADO CON ÉXITO")
        print("="*50)
        print(f"Artista detectado : {result['artist_match']['name']}")
        print(f"Casa seleccionada : {args.casa.upper()}")
        print(f"Polaroid generada : {result['tribe_poster']}")
        if result["music"] and result["music"].get("audio_path"):
            print(f"Audio guardado    : {result['music']['audio_path']}")
        if result["final_video"]:
            print(f"Video MP4 final   : {result['final_video']}")
            
        print("\n" + "-"*50)
        print("⏱️  TIEMPOS DE EJECUCIÓN DEL FLUJO CONCURRENTE")
        print("-"*50)
        for step, dur in result["timings"].items():
            print(f"{step:<25} : {dur:.2f} segundos")
        print("-"*50)
        print(f"TIEMPO TOTAL EN RELOJ (Wall-Clock): {total_duration:.2f} segundos")
        print("="*50)