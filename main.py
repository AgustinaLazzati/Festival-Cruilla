"""
Tal Cara, Tal Beat — main pipeline.

Usage:
    python main.py --image inputs/user.png --language ca
    python main.py --image inputs/user.png --mood happy --instrument guitar --era actual --with-music --language en
"""

import argparse
import os
import sys
import time
import unicodedata
from pathlib import Path

# ── Repo root & module paths ───────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "face2label" / "models"))
sys.path.insert(0, str(REPO_ROOT / "models" / "ACE-Step-1.5"))

# ── Default artifact paths ─────────────────────────────────────────────────
MODEL_PATH       = REPO_ROOT / "face2label" / "logs" / "artists_mlp.pth"
LABELS_PATH      = REPO_ROOT / "face2label" / "logs" / "labels.json"
METADATA_PATH    = REPO_ROOT / "Fake_Artist.csv"
ASSET_DIR        = REPO_ROOT / "inputs"
OUTPUT_DIR       = REPO_ROOT / "outputs"
OUTPUT_IMAGES_DIR = OUTPUT_DIR / "images"
OUTPUT_MUSIC_DIR  = OUTPUT_DIR / "music"
OUTPUT_VIDEO_DIR  = OUTPUT_DIR / "final_video"

# ── Tribe to background image mapping (Localized) ──────────────────────────
# Assumes backgrounds are organized into language subfolders inside inputs/
TRIBE_BACKGROUNDS: dict[str, dict[str, str]] = {
    "ca": {
        "urban":       str(ASSET_DIR / "ca" / "bg_urban.png"),
        "indie":   str(ASSET_DIR / "ca" / "bg_indie.png"),
        "los romanticos": str(ASSET_DIR / "ca" / "bg_romantics.png"),
        "rockstar":    str(ASSET_DIR / "ca" / "bg_rockstar.png"),
        "tecno":  str(ASSET_DIR / "ca" / "bg_tecno.png"),
    },
    "es": {
        "la calle":       str(ASSET_DIR / "es" / "bg_urban.png"),
        "indie":   str(ASSET_DIR / "es" / "bg_indie.png"),
        "los romanticos": str(ASSET_DIR / "es" / "bg_romantics.png"),
        "rockstar":    str(ASSET_DIR / "es" / "bg_rockstar.png"),
        "tecno":  str(ASSET_DIR / "es" / "bg_tecno.png"),
    },
    "en": {
        "la calle":       str(ASSET_DIR / "en" / "bg_urban.png"),
        "indie":   str(ASSET_DIR / "en" / "bg_indie.png"),
        "los romanticos": str(ASSET_DIR / "en" / "bg_romantics.png"),
        "rockstar":    str(ASSET_DIR / "en" / "bg_rockstar.png"),
        "tecno":  str(ASSET_DIR / "en" / "bg_tecno.png"),
    }
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
# STEP 3 — MUSIC GENERATION
# ==============================================================================

def step_music(
    artist_match: dict,
    mood: str,
    instrument: str,
    era: str,
) -> dict | None:
    from api.music_generator import build_ace_prompt
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationParams, GenerationConfig, generate_music

    save_dir = str(OUTPUT_MUSIC_DIR)
    os.makedirs(save_dir, exist_ok=True)

    prompt_data = build_ace_prompt(
        mood=mood,
        instrument=instrument,
        era=era,
        genre=artist_match.get("genre", "pop"),
        tribe=artist_match.get("tribe", artist_match.get("genre", "pop")),
        artist_confidence=artist_match.get("confidence", 0),
        duration_seconds=20,
    )

    print(f" ------------ RESULTS ------------")
    print(f"Genre:      {artist_match.get('genre', 'pop')}")
    print(f"Tribe:      {artist_match.get('tribe', 'unknown')}")
    print(f"Confidence: {artist_match.get('confidence', 0)}")
    print(f"[music] Tags: {prompt_data['tags'][:120]}...")
    print(f"[music] Initializing ACE-Step 1.5...")
    t0 = time.perf_counter()

    handler = AceStepHandler()
    handler.initialize_service(
        project_root=None,
        config_path="acestep-v15-turbo",
        device="cuda",
    )
    print(f"[music] Model loaded in {time.perf_counter() - t0:.2f}s")

    params = GenerationParams(
        caption=prompt_data["tags"] + ". " + prompt_data["description"],
        lyrics="",
        duration=20,
        bpm=80,
    )
    gen_config = GenerationConfig(batch_size=1, audio_format="wav")

    print("[music] Generating...")
    t1 = time.perf_counter()
    result = generate_music(handler, None, params, gen_config, save_dir=save_dir)
    print(f"[music] Inference done in {time.perf_counter() - t1:.2f}s")

    if result.success:
        audio_path = result.audios[0]["path"] if result.audios else None
        print(f"[music] Saved: {audio_path}")
        return {"success": True, "audio_path": audio_path}
    else:
        print(f"[music] Error: {result.error}")
        return {"success": False, "error": result.error}


# ==============================================================================
# STEP 4 — TRIBE BACKGROUND COMPOSITE
# ==============================================================================

def step_background(
    user_image_path: str,
    artist_match: dict,
    output_path: str,
    language: str = "ca"  # <--- Added language parameter here
) -> str | None:

    try:
        from rembg import remove
        from PIL import Image
    except ImportError as e:
        print(f"[background] Missing dependency: {e}  →  pip install rembg pillow")
        return None

    # ── 1. Resolve tribe → background path based on language ──────────────
    raw_tribe  = artist_match.get("tribe", "")
    tribe_key  = _normalise_tribe(raw_tribe)             
    
    # Safely get the dictionary for the requested language (fallback to 'ca')
    lang_backgrounds = TRIBE_BACKGROUNDS.get(language, TRIBE_BACKGROUNDS["ca"])
    bg_path = lang_backgrounds.get(tribe_key)

    if bg_path is None:
        # Partial-match fallback
        for key, path in lang_backgrounds.items():
            if key in tribe_key or tribe_key in key:
                bg_path = path
                print(f"[background] Partial match: '{raw_tribe}' → '{key}' in lang '{language}'")
                break

    if bg_path is None or not Path(bg_path).exists():
        print(
            f"[background] ✗ No background found for tribe '{raw_tribe}' in lang '{language}'.\n"
            f"             Normalised key: '{tribe_key}'\n"
            f"             Known keys: {list(lang_backgrounds.keys())}\n"
            f"             Expected file: {bg_path}"
        )
        return None

    print(f"[background] '{raw_tribe}' ({language}) →  {bg_path}")

    # ── 2. Load background ─────────────────────────────────────────────────
    background = Image.open(bg_path).convert("RGBA")
    bg_w, bg_h = background.size

    # ── 3. Remove background from user photo ──────────────────────────────
    print("[background] Removing subject background with rembg…")
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

    # ── 4. Scale subject to fit above the text band ───────────────────────
    text_band_px = int(bg_h * TEXT_BAND_FRACTION) 
    usable_h     = bg_h - text_band_px             

    target_h = int(usable_h * SUBJECT_HEIGHT_FRACTION)
    scale    = target_h / subject.height
    target_w = int(subject.width * scale)
    subject  = subject.resize((target_w, target_h), Image.LANCZOS)

    # ── 5. Compute paste position ──────────────────────────────────────────
    paste_x = (bg_w - target_w) // 2
    paste_y = usable_h - target_h      

    # ── 6. Composite ──────────────────────────────────────────────────────
    composite = background.copy()
    composite.paste(subject, (paste_x, paste_y), subject)   

    # ── 7. Save ───────────────────────────────────────────────────────────
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    composite.convert("RGB").save(output_path, quality=95)
    print(f"[background] ✓ Poster saved → {output_path}")
    return output_path


# ==============================================================================
# STEP 5 — VIDEO GENERATION
# ==============================================================================

def step_video(image_path: str, audio_path: str, output_path: str) -> str | None:
    try:
        from moviepy import ImageClip, AudioFileClip
    except ImportError as e:
        print(f"[video] Missing dependency: {e}  →  pip install moviepy")
        return None

    try:
        audio = AudioFileClip(audio_path)
        video = ImageClip(image_path, duration=audio.duration).with_audio(audio)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        video.write_videofile(output_path, fps=1, logger=None)
        video.close()
        audio.close()

        print(f"[video] ✓ Video saved → {output_path}")
        return output_path
    except Exception as e:
        print(f"[video] ✗ Error generating video: {e}")
        return None


# ==============================================================================
# PIPELINE ORCHESTRATOR
# ==============================================================================

def run_pipeline(
    image_path: str,
    output_path: str | None = None,
    mood: str = "happy",
    instrument: str = "synth",
    era: str = "actual",
    language: str = "ca",  # <--- Added language to pipeline orchestrator
    skip_music: bool = True,
) -> dict:
    OUTPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_IMAGES_DIR.mkdir(exist_ok=True)
    OUTPUT_MUSIC_DIR.mkdir(exist_ok=True)
    OUTPUT_VIDEO_DIR.mkdir(exist_ok=True)

    stem = Path(image_path).stem

    if output_path is None:
        # Append the language to the filename to avoid overwriting different versions
        output_path = str(OUTPUT_IMAGES_DIR / f"{stem}_styled_{language}.png")

    timings = {}

    # ── Step 1 — face → artist ────────────────────────────────────────────
    t_start = time.perf_counter()
    artist_match = step_face2label(image_path)
    timings["step_face2label"] = time.perf_counter() - t_start

    if artist_match is None:
        return {"success": False, "error": "No face detected in image", "timings": timings}

    # ── Step 2 — clothing overlay ─────────────────────────────────────────
    t_start = time.perf_counter()
    styled_path = step_clothing(image_path, artist_match, output_path)
    timings["step_clothing"] = time.perf_counter() - t_start

    working_image = styled_path if styled_path else image_path

    # ── Step 3 — music ────────────────────────────────────────────────────
    music_result = None
    if not skip_music:
        t_start = time.perf_counter()
        music_result = step_music(artist_match, mood, instrument, era)
        timings["step_music"] = time.perf_counter() - t_start
    else:
        timings["step_music"] = 0.0

    # ── Step 4 — tribe background composite ──────────────────────────────
    poster_output = str(OUTPUT_IMAGES_DIR / f"{stem}_tribe_poster_{language}.png")
    t_start = time.perf_counter()
    tribe_poster  = step_background(
        user_image_path=working_image,
        artist_match=artist_match,
        output_path=poster_output,
        language=language  # <--- Passed language to background function
    )
    timings["step_background"] = time.perf_counter() - t_start

    # ── Step 5 — video generation ─────────────────────────────────────────
    final_video = None
    audio_path = music_result.get("audio_path") if music_result and music_result.get("success") else None
    if tribe_poster and audio_path:
        t_start = time.perf_counter()
        video_output = str(OUTPUT_VIDEO_DIR / f"{stem}_final_{language}.mp4")
        final_video = step_video(tribe_poster, audio_path, video_output)
        timings["step_video"] = time.perf_counter() - t_start
    else:
        timings["step_video"] = 0.0

    return {
        "success":      True,
        "artist_match": artist_match,
        "styled_image": styled_path,
        "tribe_poster": tribe_poster,
        "music":        music_result,
        "final_video":  final_video,
        "timings":      timings,
    }


# ==============================================================================
# CLI
# ==============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Festival Cruilla — Tal Cara, Tal Beat")
    parser.add_argument("--image",      required=True,  help="Path to user image")
    parser.add_argument("--output",     default=None,   help="Output styled image path")
    parser.add_argument("--mood",       default="happy")
    parser.add_argument("--instrument", default="synth")
    parser.add_argument("--era",        default="actual")
    parser.add_argument("--language",   default="ca", choices=["en", "es", "ca"], 
                        help="Language context for backgrounds (ca, es, en)")
    parser.add_argument("--with-music", action="store_true",
                        help="Also generate music (requires ACE-Step API)")
    args = parser.parse_args()

    total_start = time.perf_counter()
    
    result = run_pipeline(
        image_path=args.image,
        output_path=args.output,
        mood=args.mood,
        instrument=args.instrument,
        era=args.era,
        language=args.language,  # <--- Catch argument from CLI
        skip_music=not args.with_music,
    )
    
    total_duration = time.perf_counter() - total_start

    if result["success"]:
        print(f"\nArtist       : {result['artist_match']['name']} "
              f"({result['artist_match']['confidence']}%)")
        print(f"Tribe        : {result['artist_match'].get('tribe', 'unknown')}")
        if result["styled_image"]:
            print(f"Styled image : {result['styled_image']}")
        if result["tribe_poster"]:
            print(f"Tribe poster : {result['tribe_poster']}")
        if result["music"] and result["music"].get("audio_path"):
            print(f"Music        : {result['music']['audio_path']}")
        if result["final_video"]:
            print(f"Final video  : {result['final_video']}")
            
        print("\n" + "="*40)
        print("         PERFORMANCE TIMINGS          ")
        print("="*40)
        for step, duration in result["timings"].items():
            print(f"{step:<20} : {duration:.2f} seconds")
        print("-"*40)
        print(f"{'Total Pipeline Time':<20} : {total_duration:.2f} seconds")
        print("="*40)
        
    else:
        print(f"\nPipeline failed: {result['error']}")
        
        if "timings" in result:
            print("\n--- Timings up to failure ---")
            for step, duration in result["timings"].items():
                print(f"{step}: {duration:.2f}s")
                
        sys.exit(1)