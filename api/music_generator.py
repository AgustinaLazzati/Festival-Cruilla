"""
music_generator.py
──────────────────
Prompt builder + ACE Step 1.5 caller for 25-second festival-ready melodies with a mid-track drop.

Pipeline:
  user answers (mood / instrument / era / genre)
  ──► build_ace_prompt()
  ──► generate_personalized_music()   (calls ACE Step 1.5 REST API on port 8001)
"""

from __future__ import annotations
import os, time, uuid, requests
from pathlib import Path

# =============================================================
# 1.  VOCABULARY MAPS
# =============================================================

# 1A. MOOD
MOOD_MAP: dict[str, dict] = {
    "happy": {
        "tags": "euphoric, upbeat, feel-good, bright, triumphant, joyful energy",
        "desc": "radiates joy and euphoria, built to make a festival crowd move smoothly",
        "bpm_hint": "128 BPM",
        "key_hint": "major key",
    },
    "sad": {
        "tags": "nostalgic, emotional festival progressive, retro soul, evocative",
        "desc": "drenched in warm vintage color but driving with festival energy, summoning an evocative place",
        "bpm_hint": "120 BPM",
        "key_hint": "minor key",
    },
    "chill": {
        "tags": "sunset festival vibe, melodic electronic, atmospheric, flowing, spacious groove",
        "desc": "perfect for a festival sunset set, balancing serene space with a solid forward dance motion",
        "bpm_hint": "115–120 BPM",
        "key_hint": "major or lydian mode",
    },
    "hype": {
        "tags": "high-energy, adrenaline, electric, festival anthem, crowd-pumping",
        "desc": "energetic peak-time energy engineered flawlessly for a main stage drop",
        "bpm_hint": "128–140 BPM",
        "key_hint": "major key",
    },
}

# 1B. INSTRUMENT
INSTRUMENT_MAP: dict[str, dict] = {
    "guitar": {
        "tags": "electric guitar lead, festival synth-guitar layer, smooth overdriven riff",
        "desc": "driven by expressive guitar work ranging from clean festival leads to warm riffs",
        "texture": "organic, string-forward, warm festival grit",
    },
    "piano": {
        "tags": "staccato house piano, melodic piano runs, anthemic festival chords",
        "desc": "built around an anthemic grand piano delivering driving harmonic depth and clarity",
        "texture": "dynamic range, dancefloor-ready piano chords",
    },
    "trumpet": {
        "tags": "bold brass stabs, festival horn section, electronic brass lead",
        "desc": "punctuated by bold festival brass and synthetic horn sections delivering triumphant energy",
        "texture": "bright, projecting, celebratory festival edge",
    },
    "drums": {
        "tags": "punchy festival kick, smooth electronic snare, driving club rhythm",
        "desc": "percussion-forward with a tight festival drum grid designed to move the crowd",
        "texture": "rhythmic backbone, kinetic, warm mainstage impact",
    },
}

# 1C. ERA
ERA_MAP: dict[str, dict] = {
    "medieval": {
        "tags": "folk festival electronic, ancient melodies modern sub-bass, hybrid sound",
        "desc": "produced as a modern festival track fusing acoustic medieval motifs with clean electronic bass",
        "production": "hybrid electronic mastering, clean output",
    },
    "90s": {
        "tags": "90s rave aesthetic, classic eurodance energy, retro festival synth",
        "desc": "carries the high-energy analog warmth and directness of 1990s festival raves",
        "production": "analog warmth, balanced mid-range, optimized for large sound systems",
    },
    "futuristic": {
        "tags": "futuristic EDM, hyperpop elements, experimental electronic, clean sound design",
        "desc": "pushed into a futuristic sound design space with hypermodern festival textures",
        "production": "granular synthesis, smooth processing, wide stereo master",
    },
    "actual": {
        "tags": "contemporary festival production, modern EDM master, crystal-clear audio",
        "desc": "mastered to elite festival standards—wide stereo field and immaculate detail",
        "production": "modern mainstage mastering, wide stereo image, smooth high-end",
    },
}

# 1D. CASAS (Mapped internally via the 'genre' parameter)
CASAS_MAP: dict[str, dict] = {
    "indie": {
        "tags": "indie electronic festival, euphoric indie rock, warm synthesizer, stadium indie vibe",
        "desc": "blends the emotional depth of indie music with a euphoric festival groove",
        "vibe": "indie festival aesthetic, organic-electronic fusion",
    },
    "pop": {
        "tags": "mainstage pop EDM, pure festival pop, bright glossy synthesis, radio-ready melody",
        "desc": "delivers highly polished, infectious pop melodies supercharged with a commercial festival drop",
        "vibe": "polished mainstream appeal, bright crowd-pleasing energy",
    },
    "rock": {
        "tags": "stadium rock, heavy festival rock, overdriven power chords, live drum energy",
        "desc": "channels the adrenaline-fueled power of stadium rock, built around warm overdriven guitars",
        "vibe": "rebellious raw energy, guitar-driven power",
    },
    "techno": {
        "tags": "peak-time techno, massive 4/4 kick, hypnotic acid synth, dark festival rave",
        "desc": "drives forward with a relentless, hypnotic techno pulse and a dark, euphoric rave energy",
        "vibe": "hypnotic nocturnal energy, pure rave aesthetic",
    },
    "urban": {
        "tags": "festival trap, deep 808 sub-bass, urban mainstage groove, dembow rhythm",
        "desc": "hits hard with deep 808s and an infectious, rhythmic urban bounce scaled up for festival sound systems",
        "vibe": "street-informed swagger, bassline dominance, rhythmic bounce",
    },
    "unknown": {
        "tags": "crossover festival beat, genre-blending drop, energetic mainstage fusion",
        "desc": "genre-defying festival track blending elements into an energetic mainstage experience",
        "vibe": "experimental crossover energy",
    },
}

# 1E. FESTIVAL QUALITY STACK (Modificado para bajar volumen y evitar ruidos/distorsión)
FESTIVAL_QUALITY_TAGS = (
    "high-fidelity recording, professionally mixed and mastered, "
    "wide stereo field, smooth dynamics, NO clipping, NO distortion, "
    "warm mastering, -3dB headroom, well-balanced mix, clear frequencies, "
    "strictly instrumental, no vocals, no voice, absolute wordless track, pure music"
)

FESTIVAL_QUALITY_DESC = (
    "The production is polished to an absolute festival standard but mixed with care: "
    "it features a well-balanced EQ, smooth high frequencies, and dynamic headroom (-3dB) "
    "to ensure a warm, distortion-free listening experience without harsh noise or clipping. "
    "Crucially, this is a strictly instrumental track with no vocals, no lyrics, and no human voices."
)


# =============================================================
# 2.  CORE PROMPT BUILDER
# =============================================================

def build_ace_prompt(
    mood: str,
    instrument: str,
    era: str,
    genre: str,  # <-- Se mantiene como 'genre' para que main.py no falle
    duration_seconds: int = 25,
) -> dict[str, str]:
    """
    Returns a dict with festival arrangements, no lyrics, controlled volume, and a mid-track peak.
    """
    m = MOOD_MAP.get(mood, MOOD_MAP["hype"])
    i = INSTRUMENT_MAP.get(instrument, INSTRUMENT_MAP["drums"])
    e = ERA_MAP.get(era, ERA_MAP["actual"])
    
    # Usamos 'genre' para buscar en el diccionario de casas
    safe_casa = genre.lower().strip() if genre else "unknown"
    c = CASAS_MAP.get(safe_casa, CASAS_MAP["unknown"])

# --- NUEVA ESTRUCTURA DE FESTIVAL CON DROP EN EL SEGUNDO 10 (SIN RUIDO) ---
    structure_tag = (
        "precise 25-second festival arrangement, progressive 10-second build-up, "
        "massive mainstage melodic drop at exactly 10 seconds, sustained high-energy "
        "instrumental chorus from second 10 to 22, smooth volume-controlled outro from 22 to 25, "
        "balanced gain, clean mixing"
    )
    structure_desc = (
        f"The track follows a strict chronological festival arrangement: It begins with a driving, "
        f"progressive 10-second build-up. At exactly second 10, the track transitions into a much better, "
        f"powerful and highly intensified melodic drop and mainstage chorus. This peak energy and new melody "
        f"are beautifully sustained from second 10 through second 22. From second 22 to 25, it enters a smooth "
        f"and controlled outro. The overall volume is perfectly normalized with a soft limiter to ensure "
        f"maximum punch and clarity, completely avoiding any digital clipping, harsh noise, or audio distortion."
    )

    tags_parts = [
        c["tags"],
        m["tags"],
        i["tags"],
        e["tags"],
        c["vibe"],
        m["bpm_hint"],
        m["key_hint"],
        structure_tag,
        FESTIVAL_QUALITY_TAGS,
    ]
    tags = ", ".join(filter(None, tags_parts))

    description = (
        f"A festival-optimized {duration_seconds}-second {safe_casa} track "
        f"that {c['desc']}. "
        f"Emotionally it drives with {m['desc']}, "
        f"with the core arrangement {i['desc']}, "
        f"all wrapped in {e['desc']}. "
        f"It carries a strong {c['vibe']}. "
        f"{structure_desc} "
        f"{FESTIVAL_QUALITY_DESC}"
    )

    full_prompt = f"[TAGS]: {tags}\n\n[DESCRIPTION]: {description}"

    return {
        "tags": tags,
        "description": description,
        "full_prompt": full_prompt,
        "_bpm_hint":   m["bpm_hint"],
        "_key_hint":   m["key_hint"],
        "_production": e["production"],
        "_texture":    i["texture"],
    }


# =============================================================
# 3.  ACE STEP 1.5 API CALLER
# =============================================================
ACE_STEP_BASE_URL = os.getenv("ACE_STEP_API_URL", "http://localhost:8001")
ACE_STEP_API_KEY  = os.getenv("ACE_STEP_API_KEY", "")

def _call_ace_step(tags: str, description: str, duration: int, output_path: Path) -> dict:
    headers = {"Content-Type": "application/json"}
    if ACE_STEP_API_KEY:
        headers["Authorization"] = f"Bearer {ACE_STEP_API_KEY}"

    prompt = f"{tags}\n\n{description}"
    payload = {"prompt": prompt, "duration": duration, "audio_format": "wav"}
    if ACE_STEP_API_KEY:
        payload["ai_token"] = ACE_STEP_API_KEY

    try:
        print(f"[ace_step] POST {ACE_STEP_BASE_URL}/release_task …")
        resp = requests.post(f"{ACE_STEP_BASE_URL}/release_task", json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 200:
            return {"success": False, "error": f"API error: {data.get('error', 'Unknown error')}"}

        task_id = data["data"]["task_id"]
        print(f"[ace_step] Task submitted: {task_id}")

        max_retries = 300
        retry_count = 0
        audio_url = ""
        while retry_count < max_retries:
            time.sleep(1)
            query_resp = requests.post(f"{ACE_STEP_BASE_URL}/query_result", json={"task_ids": [task_id]}, headers=headers, timeout=30)
            query_resp.raise_for_status()
            query_data = query_resp.json()

            if query_data.get("code") != 200:
                return {"success": False, "error": f"Query error: {query_data.get('error', 'Unknown')}"}

            data_field = query_data.get("data", [])
            tasks = data_field if isinstance(data_field, list) else data_field.get("tasks", [])

            if tasks:
                task_info = tasks[0] if isinstance(tasks, list) else tasks
                task_status = task_info.get("status") if isinstance(task_info, dict) else task_info
                
                if task_status == 1:  # Success
                    audio_url = task_info.get("media_path", "") if isinstance(task_info, dict) else ""
                    print(f"[ace_step] Generation succeeded: {audio_url}")
                    break
                elif task_status == 2:  # Failed
                    return {"success": False, "error": f"Task failed"}
                else:
                    if retry_count % 10 == 0:
                        print(f"[ace_step] Task {task_id} in progress... ({retry_count}s)")

            retry_count += 1

        if not audio_url:
            return {"success": False, "error": "No audio URL"}

        download_url = f"{ACE_STEP_BASE_URL}/v1/audio?path={audio_url}" if audio_url.startswith("/") else audio_url
        audio_resp = requests.get(download_url, headers=headers, timeout=60)
        audio_resp.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio_resp.content)
        return {"success": True, "audio_path": str(output_path)}

    except Exception as exc:
        return {"success": False, "error": str(exc)}


# =============================================================
# 4.  PUBLIC ENTRY POINT
# =============================================================
def generate_personalized_music(
    mood: str,
    instrument: str,
    era: str,
    genre: str, # <-- Recibe 'genre' desde tu main.py
    duration: int = 25,
    output_dir: str = "outputs",
    **kwargs # <-- Absorbe argumentos extra (como artist_match) sin crashear
) -> dict:
    """
    Main entry point purely based on the user answers.
    Takes 'genre' to maintain compatibility with main.py pipeline.
    """
    prompt_data = build_ace_prompt(
        mood=mood,
        instrument=instrument,
        era=era,
        genre=genre,
        duration_seconds=duration,
    )

    uid = uuid.uuid4().hex[:8]
    safe_casa_name = genre.lower().replace(" ", "_") if genre else "unknown"
    filename = f"festival_25s_{mood}_{safe_casa_name}_{uid}.wav"
    output_path = Path(output_dir) / filename

    print(f"\n{'='*60}")
    print(f"[music_generator] Generating {duration}s track for Casa: {safe_casa_name.upper()}")
    print(f"[music_generator] Mood: {mood} | Instrument: {instrument} | Era: {era}")
    print(f"{'='*60}")

    result = _call_ace_step(
        tags=prompt_data["tags"],
        description=prompt_data["description"],
        duration=duration,
        output_path=output_path,
    )

    return {
        "success":       result["success"],
        "audio_path":    result.get("audio_path"),
        "prompt":        prompt_data["full_prompt"],
        "tags":          prompt_data["tags"],
        "description":   prompt_data["description"],
        "error":         result.get("error"),
    }

if __name__ == "__main__":
    # Prueba rápida simulando las respuestas
    test_user_answers = [
        {"mood": "hype",  "instrument": "drums",  "era": "actual",     "genre": "techno"},
        {"mood": "chill", "instrument": "guitar", "era": "90s",        "genre": "indie"},
    ]
    
    for ans in test_user_answers:
        print(f"\n── TEST RUN: {ans['genre'].upper()} ─────────────────────────────────────")
        p = build_ace_prompt(**ans, duration_seconds=25)
        print(p["full_prompt"])