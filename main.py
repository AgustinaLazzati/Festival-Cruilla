"""
Tal Cara, Tal Beat — main pipeline.

Usage:
    python main.py --image inputs/user.png
    python main.py --image inputs/user.png --mood happy --instrument guitar --era actual --with-music
"""

import argparse
import os
import sys
from pathlib import Path

# ── Repo root & module paths ───────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "face2label" / "models"))
sys.path.insert(0, str(REPO_ROOT / "models" / "ACE-Step-1.5"))

# ── Default artifact paths ─────────────────────────────────────────────────
MODEL_PATH    = REPO_ROOT / "face2label" / "logs" / "artists_mlp.pth"
LABELS_PATH   = REPO_ROOT / "face2label" / "logs" / "labels.json"
METADATA_PATH = Path("/export/hhome/ps2g07/code/data/Fake_Artist.csv")
ASSET_DIR     = REPO_ROOT / "inputs"
OUTPUT_DIR    = REPO_ROOT / "outputs"

# ==============================================================================
# STEP 1 — FACE -> ARTIST LABEL
# ==============================================================================

def step_face2label(image_path: str) -> dict | None:
    """
    Extract face embedding and predict the matching fake artist.

    Returns:
        {"name": str, "confidence": int, "genre": str}  or  None if no face found.
    """
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
          f"({result['confidence']}%)  genre: {result['genre']}")
    return result


# ==============================================================================
# STEP 2 — CLOTHING / ACCESSORY OVERLAY
# ==============================================================================

def step_clothing(user_image_path: str, artist_match: dict, output_path: str) -> str | None:
    """
    Apply the matched artist's signature look to the user image.

    TODO: import and call apply_look() from clothing.Clothing once that module
          exposes a clean function. Suggested signature:

            from clothing.Clothing import apply_look
            return apply_look(
                user_image_path=user_image_path,
                artist_name=artist_match["name"],
                output_path=output_path,
                csv_path=str(METADATA_PATH),
                asset_dir=str(ASSET_DIR),
            )
    """
    print(f"[clothing] TODO — overlay for '{artist_match['name']}' → {output_path}")
    return None


# ==============================================================================
# STEP 3 - MUSIC GENERATION
# ==============================================================================

def step_music(
    artist_match: dict,
    mood: str,
    instrument: str,
    era: str,
) -> dict | None:
    """
    Generate a ~20-second personalized melody using the local ACE-Step 1.5 model.
    Prompt is built dynamically from the artist match and user answers.
    """
    import time
    from api.music_generator import build_ace_prompt
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationParams, GenerationConfig, generate_music

    save_dir = str(OUTPUT_DIR / "music")
    os.makedirs(save_dir, exist_ok=True)

    # Build personalized prompt from user inputs + artist match
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
    print(f"Genre: {artist_match.get("genre", "pop")}")
    print(f"Tribe: {artist_match.get("tribe", artist_match.get("genre", "pop"))}")
    print(f"Confidence: {artist_match.get("confidence", 0)}")

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
# PIPELINE ORCHESTRATOR
# ==============================================================================

def run_pipeline(
    image_path: str,
    output_path: str | None = None,
    mood: str = "happy",
    instrument: str = "synth",
    era: str = "actual",
    skip_music: bool = True,
) -> dict:
    OUTPUT_DIR.mkdir(exist_ok=True)

    if output_path is None:
        stem = Path(image_path).stem
        output_path = str(OUTPUT_DIR / f"{stem}_styled.png")

    # Step 1 — face -> artist
    artist_match = step_face2label(image_path)
    if artist_match is None:
        return {"success": False, "error": "No face detected in image"}

    # Step 2 — clothing overlay
    styled_path = step_clothing(image_path, artist_match, output_path)
        
    # Step 3 — music
    music_result = None
    if not skip_music:
        music_result = step_music(artist_match, mood, instrument, era)

    return {
        "success": True,
        "artist_match": artist_match,
        "styled_image": styled_path,
        "music": music_result,
    }


# ==============================================================================
# CLI
# ==============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Festival Cruilla pipeline")
    parser.add_argument("--image",      required=True,  help="Path to user image")
    parser.add_argument("--output",     default=None,   help="Output styled image path")
    parser.add_argument("--mood",       default="happy")
    parser.add_argument("--instrument", default="synth")
    parser.add_argument("--era",        default="actual")
    parser.add_argument("--with-music", action="store_true",
                        help="Also generate music (requires ACE-Step API)")
    args = parser.parse_args()

    result = run_pipeline(
        image_path=args.image,
        output_path=args.output,
        mood=args.mood,
        instrument=args.instrument,
        era=args.era,
        skip_music=not args.with_music,
    )

    if result["success"]:
        print(f"\nArtist: {result['artist_match']['name']} "
              f"({result['artist_match']['confidence']}%)")
        if result["styled_image"]:
            print(f"Styled image: {result['styled_image']}")
        if result["music"] and result["music"].get("audio_path"):
            print(f"Music: {result['music']['audio_path']}")
    else:
        print(f"\nPipeline failed: {result['error']}")
        sys.exit(1)
