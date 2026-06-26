"""
music_generator.py
──────────────────
Prompt builder + ACE Step 1.5 caller for 20-second festival-ready melodies.

Pipeline:
  user answers (mood / instrument / era)
  + artist-match data (name / genre / tribe / confidence)
  ──► build_ace_prompt()
  ──► generate_personalized_music()   (calls ACE Step 1.5 REST API on port 8001)

Every mapping produces vocabulary that ACE Step 1.5 was trained on:
  tags block  → short comma-separated descriptors  (genre, mood, texture…)
  description → one rich prose sentence            (production intent)
"""

from __future__ import annotations
import os, re, time, uuid, unicodedata, requests
from pathlib import Path
from typing import Optional

# =============================================================
# 1.  VOCABULARY MAPS
# =============================================================

# 1A. MOOD
MOOD_MAP: dict[str, dict] = {
    "happy": {
        "tags": "euphoric, upbeat, feel-good, bright, triumphant, joyful energy",
        "desc": "radiates pure joy and euphoria, built to make a festival crowd erupt",
        "bpm_hint": "120–128 BPM",
        "key_hint": "major key",
    },
    "sad": {
        "tags": "nostalgic, vintage warmth, retro soul, timeless, evocative, wistful",
        "desc": "drenched in warm vintage color, summoning a place that no longer exists",
        "bpm_hint": "85–100 BPM",
        "key_hint": "major or mixolydian mode",
    },
    "chill": {
        "tags": "serene, meditative, flowing, peaceful, airy, spacious",
        "desc": "breathably serene, with open space and gentle forward motion",
        "bpm_hint": "60–80 BPM",
        "key_hint": "major or lydian mode",
    },
    "hype": {
        "tags": "high-energy, adrenaline, electric, festival anthem, peak-time, explosive",
        "desc": "explosive peak-time energy engineered for the main stage drop",
        "bpm_hint": "128–140 BPM",
        "key_hint": "major key",
    },
}

# 1B. INSTRUMENT
INSTRUMENT_MAP: dict[str, dict] = {
    "guitar": {
        "tags": "electric guitar lead, clean Stratocaster tone, fingerpicked arpeggios, overdriven riff",
        "desc": "driven by expressive guitar work ranging from clean arpeggios to saturated riffs",
        "texture": "organic, string-forward, mid-range warmth",
    },
    "piano": {
        "tags": "concert grand piano, melodic piano runs, harmonic piano chords, sustained notes",
        "desc": "built around a grand piano delivering rich harmonic depth and melodic clarity",
        "texture": "dynamic range, classical meeting contemporary",
    },
    "trumpet": {
        "tags": "solo trumpet, brass section stabs, muted trumpet, jazz brass, fanfare horn",
        "desc": "punctuated by bold brass—ranging from muted jazz nuance to triumphant fanfares",
        "texture": "bright, projecting, celebratory edge",
    },
    "drums": {
        "tags": "live drum kit, tight snare, punchy kick, driving rhythm, polyrhythmic percussion",
        "desc": "percussion-forward with a tight, punchy live drum feel at its core",
        "texture": "rhythmic backbone, kinetic, full-body impact",
    },
}

# 1C. ERA
ERA_MAP: dict[str, dict] = {
    "medieval": {
        "tags": "medieval era, acoustic resonance, natural reverb, troubadour folk, Gregorian chant",
        "desc": "produced with acoustic instruments and natural spatial resonance evoking the medieval era",
        "production": "lute, recorder, hurdy-gurdy, stone hall reverb, no electronic processing",
    },
    "90s": {
        "tags": "1990s, lo-fi grunge warmth, boom-bap hip-hop, alternative rock, Britpop, shoegaze wall of sound",
        "desc": "carries the raw analogue warmth and emotional directness of 1990s alternative and hip-hop",
        "production": "analogue warmth, slight saturation, lo-fi tape hiss, live drum recording",
    },
    "futuristic": {
        "tags": "futuristic, hyperpop, glitchy, experimental electronic, AI-generated textures, avant-garde",
        "desc": "pushed into a futuristic sound design space with glitchy, hypermodern textures",
        "production": "pitch-shifted vocals, granular synthesis, extreme processing, generative textures",
    },
    "actual": {
        "tags": "contemporary 2024 production, hi-fi master, modern mix, streaming-optimized, crystal-clear audio",
        "desc": "mastered to modern streaming standards—wide stereo field, punchy transients, immaculate detail",
        "production": "modern mastering, wide stereo image, loudness normalization, crisp high-end",
    },
}

# 1D. GENRE / TRIBE
GENRE_MAP: dict[str, dict] = {
    # -- Rock family --
    "Alternative Rock": {
        "tags": "alternative rock, jangly distorted guitar, raw emotional energy, indie grit, anthemic chorus",
        "desc": "charged with the raw emotional power of alternative rock—distorted guitars and cathartic anthems",
        "sub_genre": "indie rock, grunge",
    },
    "Art Rock": {
        "tags": "art rock, experimental guitar, cinematic arrangement, progressive texture, avant-garde structure",
        "desc": "conceptually bold, fusing rock instrumentation with cinematic and experimental arrangement",
        "sub_genre": "progressive rock, post-rock",
    },
    "Blues Rock": {
        "tags": "blues rock, overdriven guitar, bluesy string bends, raw southern grit, soulful riff",
        "desc": "drenched in bluesy guitar bends and overdriven warmth, rooted in raw southern grit",
        "sub_genre": "hard rock, classic rock",
    },
    "Britpop": {
        "tags": "britpop, jangly guitar, anthemic chorus, British swagger, lad-culture energy, 90s indie",
        "desc": "swagger-driven and anthemic in the britpop tradition—melodic guitars, big choruses",
        "sub_genre": "indie pop, alternative rock",
    },
    "Folk Rock": {
        "tags": "folk rock, acoustic guitar, organic warmth, rootsy storytelling, gentle drum groove",
        "desc": "organic and rootsy, weaving acoustic warmth with folk songwriting and rock energy",
        "sub_genre": "singer-songwriter, Americana",
    },
    "Garage Rock": {
        "tags": "garage rock, fuzzy guitar, lo-fi grit, raw power chord, stripped-back energy, punky drive",
        "desc": "fuzzed-out and unpolished, capturing the raw kinetic intensity of a garage band",
        "sub_genre": "punk rock, indie rock",
    },
    "Indie Rock": {
        "tags": "indie rock, melodic jangly guitar, introspective tone, college radio energy, alt-rock warmth",
        "desc": "introspective and melodic, built on jangly guitars and the quiet intensity of indie rock",
        "sub_genre": "alternative rock, dream pop",
    },
    "Pop Rock": {
        "tags": "pop rock, catchy hook, clean guitar, anthemic bridge, radio-friendly chorus, upbeat energy",
        "desc": "radio-friendly and irresistible, with clean guitar tones, catchy hooks, and a big chorus",
        "sub_genre": "power pop, alternative pop",
    },
    "Post-Punk": {
        "tags": "post-punk, angular guitar, driving bass, cold synth texture, minimal drums, dark edge",
        "desc": "angular and driving with cold synth textures, taut bass lines, and a dark atmospheric edge",
        "sub_genre": "new wave, gothic rock",
    },
    "Rock": {
        "tags": "rock, power chord, distorted guitar, driving drums, anthemic chorus, stadium rock energy",
        "desc": "charged with distorted power chords, thundering drums, and an anthemic stadium energy",
        "sub_genre": "classic rock, hard rock",
    },
    # -- Pop family --
    "Alternative Pop": {
        "tags": "alternative pop, emotive vocals, lush indie production, dream-pop haze, introspective hook",
        "desc": "emotionally rich and lushly produced, blending pop accessibility with indie depth",
        "sub_genre": "indie pop, chamber pop",
    },
    "Electronic Pop": {
        "tags": "electronic pop, synth-driven melody, danceable groove, glossy production, digital sheen, catchy hook",
        "desc": "slick and danceable, layering catchy pop hooks over a bright synthesizer-driven production",
        "sub_genre": "synth-pop, future pop",
    },
    "Indie Pop": {
        "tags": "indie pop, warm jangle, heartfelt lyric, sun-drenched melody, organic charm, bedroom pop warmth",
        "desc": "warm and heartfelt, with a sun-drenched indie-pop jangle and deeply personal melodic voice",
        "sub_genre": "dream pop, chamber pop",
    },
    "Pop": {
        "tags": "pop, radio-ready, hook-driven, polished production, bright melody, contemporary pop",
        "desc": "radio-optimized with an instantly memorable hook and pristine contemporary production",
        "sub_genre": "synth-pop, indie pop",
    },
    "Pop / World Music": {
        "tags": "world pop, global rhythm, cross-cultural fusion, diverse instrumentation, international groove",
        "desc": "globally inspired, fusing international rhythmic textures with contemporary pop songcraft",
        "sub_genre": "world music, fusion pop",
    },
    "Urban Pop": {
        "tags": "urban pop, contemporary R&B influence, polished street-informed groove, mainstream appeal",
        "desc": "polished and contemporary, drawing from urban music textures with mainstream pop appeal",
        "sub_genre": "R&B pop, contemporary pop",
    },
    # -- Hip-hop family --
    "Hip Hop / Soul": {
        "tags": "hip-hop soul, boom-bap groove, soulful sample, warm R&B chord, conscious flow, vintage urban",
        "desc": "rooted in the soulful intersection of hip-hop rhythm and R&B warmth—boom-bap with emotional depth",
        "sub_genre": "conscious hip-hop, neo-soul",
    },
    "Urban Hip Hop": {
        "tags": "urban hip-hop, hard-hitting beat, punchy 808, street energy, gritty flow, bass-heavy production",
        "desc": "hard-hitting and bass-heavy, capturing the raw gritty energy of urban hip-hop culture",
        "sub_genre": "trap, street rap",
    },
    "Urban Pop Rap": {
        "tags": "pop rap, melodic flow, mainstream hook, trap-influenced beat, crossover appeal, radio-ready rap",
        "desc": "melodic and crossover-ready, blending rap flow with pop hooks over a trap-informed beat",
        "sub_genre": "melodic rap, commercial hip-hop",
    },
    # -- Trap --
    "Urban Trap": {
        "tags": "urban trap, sliding 808, hi-hat rolls, dark atmospheric melody, streetwear aesthetic, club energy",
        "desc": "menacing and bass-heavy with sliding 808s, rolling hi-hats, and a dark urban melodic thread",
        "sub_genre": "melodic trap, Latin trap",
    },
    # -- Electronic / Dance --
    "Electronic": {
        "tags": "electronic, synthesizer texture, abstract beat, ambient pulse, producer-driven, experimental sound design",
        "desc": "synthesizer-driven and producer-focused, exploring electronic sound design with an experimental edge",
        "sub_genre": "IDM, ambient electronic",
    },
    "Electronic / Dance": {
        "tags": "electronic dance music, four-on-the-floor kick, supersaw lead, dancefloor energy, festival drop, build-up",
        "desc": "built for the dancefloor—driving kick, soaring synth leads, and an electrifying festival drop",
        "sub_genre": "house, techno, trance",
    },
    "Indie Electronic": {
        "tags": "indie electronic, warm synthesizer, organic texture, bedroom producer, dreamy lo-fi atmosphere",
        "desc": "intimate and dreamy, blending organic warmth with bedroom electronic production textures",
        "sub_genre": "chillwave, synthwave",
    },
    "Techno Brass": {
        "tags": "techno brass, industrial groove, bold brass stab, driving techno kick, avant-garde club, hypnotic",
        "desc": "a collision of industrial techno percussion and bold brass stabs—hypnotic, physical, and intense",
        "sub_genre": "industrial techno, jazz fusion",
    },
    # -- Latin --
    "Electro Cumbia": {
        "tags": "electro cumbia, digital cumbia beat, tropical bass, Latin groove, dancehall energy, electronic percussion",
        "desc": "pulsating with digital cumbia rhythms layered over electronic production and tropical bass",
        "sub_genre": "Latin electronic, tropical fusion",
    },
    "Pop Reggae Fusion": {
        "tags": "pop reggae, reggae off-beat guitar, melodic hook, tropical feel, radio-friendly reggae groove",
        "desc": "breezy and melodic with a reggae rhythmic lilt and a pop songwriting heart",
        "sub_genre": "reggaeton, dancehall pop",
    },
    "Urban Pop Reggaeton": {
        "tags": "reggaeton, dembow rhythm, 808 bass thud, urban Latino, perreo groove, Latin trap hi-hat",
        "desc": "locked into a dembow grid with rolling 808 sub-bass and contemporary Latin urban flair",
        "sub_genre": "reggaeton moderno, trap latino",
    },
    # -- Funk / Soul / Jazz --
    "Funk / Disco": {
        "tags": "funk disco, slap bass groove, brass stab, lush synth pad, four-on-the-floor, retro dancefloor",
        "desc": "propelled by slap bass, punchy brass stabs, and a lush synth groove made for the dancefloor",
        "sub_genre": "neo-soul, boogie",
    },
    "Jazz / Afrobeat": {
        "tags": "jazz afrobeat, polyrhythmic percussion, African rhythm pattern, brass melody, organic groove, vibrant energy",
        "desc": "vibrant and rhythmically complex, fusing jazz harmony with infectious African percussion",
        "sub_genre": "Afrofusion, world jazz",
    },
    "Jazz / Soul": {
        "tags": "jazz soul, warm piano chord, upright bass, soulful melody, late-night groove, harmonic richness",
        "desc": "soulful and harmonically rich, with warm piano chords and a late-night intimate groove",
        "sub_genre": "neo-soul, smooth jazz",
    },
    # -- Unique --
    "Marimba Punk": {
        "tags": "marimba punk, resonant marimba, raw punk energy, percussion-forward, unconventional, eclectic",
        "desc": "wildly eclectic, fusing the bright resonance of marimba with the raw kinetic energy of punk",
        "sub_genre": "experimental, world punk",
    },
    # -- Fallback --
    "unknown": {
        "tags": "crossover, genre-blending, eclectic, adventurous, boundary-pushing",
        "desc": "genre-defying, blending elements from multiple traditions into something entirely fresh",
        "sub_genre": "experimental, crossover",
    },
}

# 1E. TRIBE
TRIBE_MAP: dict[str, str] = {
    "Los Salvajes":   "raw guitar power, rebellious rock energy, distorted edge",
    "Los Soñadores":  "electronic dreamscape, synthesizer atmosphere, nocturnal depth",
    "Los Nómadas":    "world music rhythmic diversity, jazz harmony, organic groove",
    "Los Románticos": "melodic indie pop sensibility, heartfelt songwriting, summery warmth",
    "La Calle":       "urban street energy, hip-hop rhythmic grit, bass-heavy urban production",
    "hip_hop":        "hip-hop DNA, urban rhythmic sensibility",
    "electronic":     "electronic music production instinct, synthesizer-centric",
    "latin":          "Latin rhythmic feel, Caribbean melodic warmth",
    "rock":           "rock arrangement energy, guitar-driven power",
    "pop":            "pop songwriting craft, ear-worm melodic phrasing",
    "rnb":            "R&B groove sensibility, soulful harmonic palette",
    "classical":      "classical harmonic sophistication, orchestral depth",
    "folk":           "folk storytelling intimacy, acoustic warmth",
    "jazz":           "jazz harmonic complexity, improvisational feel",
    "world":          "world music rhythmic diversity, global melodic flavour",
}

# 1F. FESTIVAL QUALITY STACK
FESTIVAL_QUALITY_TAGS = (
    "high-fidelity recording, professionally mixed and mastered, "
    "wide stereo field, punchy transients, rich harmonic overtones, "
    "festival-ready production quality, immersive soundscape, "
    "dynamic range, no clipping, broadcast-quality audio"
)

FESTIVAL_QUALITY_DESC = (
    "The production is polished to a festival-ready standard: "
    "wide stereo image, punchy transients, deep sub-bass extension, "
    "and immaculate high-frequency detail, fully competitive with "
    "tracks played on a main-stage PA system."
)


# =============================================================
# 2.  CORE PROMPT BUILDER
# =============================================================

def build_ace_prompt(
    mood: str,
    instrument: str,
    era: str,
    genre: str,
    tribe: str,
    artist_confidence: int = 0,
    duration_seconds: int = 20,
) -> dict[str, str]:
    """
    Returns a dict with:
      'tags'        → short comma-separated keyword block
      'description' → rich prose sentence
      'full_prompt' → concatenated tags + description
    """
    m  = MOOD_MAP.get(mood,       MOOD_MAP["happy"])
    i  = INSTRUMENT_MAP.get(instrument, INSTRUMENT_MAP["guitar"])
    e  = ERA_MAP.get(era,         ERA_MAP["actual"])
    g  = GENRE_MAP.get(genre,     GENRE_MAP["unknown"])
    t  = TRIBE_MAP.get(tribe,     "")

    genre_ok = genre in GENRE_MAP
    tribe_ok = tribe in TRIBE_MAP
    print(f"[prompt_builder] Genre  : '{genre}  →  {'OK' if genre_ok else 'FALLBACK: unknown'}")
    print(f"[prompt_builder] Tribe  : '{tribe}'  →  {'OK: ' + t[:60] if tribe_ok else 'NOT FOUND (no tribe descriptor added)'}")
    print(f"[prompt_builder] Mood={mood}  Instrument={instrument}  Era={era}  Confidence={artist_confidence}%")

    if duration_seconds <= 15:
        structure_tag  = "short cinematic intro, compact motif"
        structure_desc = f"a focused {duration_seconds}-second motif with immediate impact"
    elif duration_seconds == 20:
        structure_tag  = "20-second melodic loop, festival intro, loop-ready arrangement"
        structure_desc = (
            f"a perfectly loopable {duration_seconds}-second arrangement with a clear "
            "melodic statement and space for a natural repeat"
        )
    else:
        structure_tag  = "full arrangement, verse-chorus arc, dynamic build"
        structure_desc = (
            f"a {duration_seconds}-second piece with a full dynamic arc "
            "from intro through climax"
        )

    if artist_confidence >= 10:
        genre_weight = f"strong {g['sub_genre']} influence"
    elif artist_confidence >= 5:
        genre_weight = f"clear {g['sub_genre']} sensibility"
    else:
        genre_weight = f"subtle {genre} undertone"

    tags_parts = [
        g["tags"],
        m["tags"],
        i["tags"],
        e["tags"],
        genre_weight,
        t,
        m["bpm_hint"],
        m["key_hint"],
        structure_tag,
        FESTIVAL_QUALITY_TAGS,
    ]
    tags = ", ".join(filter(None, tags_parts))

    tribe_clause = f", enriched with {t}" if t else ""
    description = (
        f"A {duration_seconds}-second {genre.replace('_', ' ')} melody "
        f"that {g['desc']}. "
        f"Emotionally it {m['desc']}, "
        f"with the arrangement {i['desc']}, "
        f"all {e['desc']}. "
        f"It draws on {genre_weight}{tribe_clause}. "
        f"Structured as {structure_desc}. "
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
#     Start the server with:  uv run acestep-api
#     REST API runs on port 8001 (Gradio UI is on 7860 — different thing)
# =============================================================

ACE_STEP_BASE_URL = os.getenv("ACE_STEP_API_URL", "http://localhost:8001")
ACE_STEP_API_KEY  = os.getenv("ACE_STEP_API_KEY", "")


def _call_ace_step(
    tags: str,
    description: str,
    duration: int,
    output_path: Path,
) -> dict:
    """
    Calls the ACE-Step 1.5 REST API via the async task workflow.

    Workflow:
      1. POST /release_task with prompt/duration
      2. Poll /query_result until task succeeds
      3. Download audio via /v1/audio endpoint
    """
    import time

    headers = {"Content-Type": "application/json"}
    if ACE_STEP_API_KEY:
        headers["Authorization"] = f"Bearer {ACE_STEP_API_KEY}"

    # Combine tags and description into a single prompt
    prompt = f"{tags}\n\n{description}"

    payload = {
        "prompt":    prompt,
        "duration":  duration,
        "audio_format": "wav",
    }
    if ACE_STEP_API_KEY:
        payload["ai_token"] = ACE_STEP_API_KEY

    try:
        # Step 1: Submit generation task
        print(f"[ace_step] POST {ACE_STEP_BASE_URL}/release_task …")
        resp = requests.post(
            f"{ACE_STEP_BASE_URL}/release_task",
            json=payload,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 200:
            return {"success": False, "error": f"API error: {data.get('error', 'Unknown error')}"}

        task_id = data["data"]["task_id"]
        print(f"[ace_step] Task submitted: {task_id}")

        # Step 2: Poll for task completion
        max_retries = 300  # 5 minutes with 1-second checks
        retry_count = 0
        audio_url = ""
        while retry_count < max_retries:
            time.sleep(1)
            query_resp = requests.post(
                f"{ACE_STEP_BASE_URL}/query_result",
                json={"task_ids": [task_id]},
                headers=headers,
                timeout=30,
            )
            query_resp.raise_for_status()
            query_data = query_resp.json()

            if query_data.get("code") != 200:
                return {"success": False, "error": f"Query error: {query_data.get('error', 'Unknown')}"}

            # data can be a list or dict depending on API version
            data_field = query_data.get("data", [])
            if isinstance(data_field, list) and data_field:
                tasks = data_field
            elif isinstance(data_field, dict):
                tasks = data_field.get("tasks", [])
            else:
                tasks = []

            if tasks:
                # Handle both list and dict responses
                task_info = tasks[0] if isinstance(tasks, list) else tasks
                task_status = task_info.get("status") if isinstance(task_info, dict) else task_info
                
                if task_status == 1:  # Success
                    audio_url = task_info.get("media_path", "") if isinstance(task_info, dict) else ""
                    print(f"[ace_step] Generation succeeded: {audio_url}")
                    break
                elif task_status == 2:  # Failed
                    error_msg = task_info.get("error_msg", "Unknown error") if isinstance(task_info, dict) else "Unknown error"
                    return {"success": False, "error": f"Task failed: {error_msg}"}
                else:  # Still queued/running (status 0)
                    if retry_count % 10 == 0:
                        print(f"[ace_step] Task {task_id} in progress... ({retry_count}s)")

            retry_count += 1

        if retry_count >= max_retries:
            return {"success": False, "error": "Task generation timeout (>5min)"}

        # Step 3: Download audio file
        if not audio_url:
            return {"success": False, "error": "No audio URL in response"}

        # If audio_url is a path, download via /v1/audio endpoint
        if audio_url.startswith("/"):
            download_url = f"{ACE_STEP_BASE_URL}/v1/audio?path={audio_url}"
        else:
            download_url = audio_url

        print(f"[ace_step] Downloading from: {download_url}")
        audio_resp = requests.get(download_url, headers=headers, timeout=60)
        audio_resp.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio_resp.content)
        return {"success": True, "audio_path": str(output_path)}

    except requests.exceptions.ConnectionError:
        return {"success": False, "error": (
            f"Cannot reach ACE-Step at {ACE_STEP_BASE_URL}. "
            "Start the server with:  python acestep/api_server.py"
        )}
    except requests.exceptions.Timeout:
        return {"success": False, "error": "ACE-Step timed out (>timeout threshold)."}
    except requests.exceptions.HTTPError as exc:
        return {"success": False,
                "error": f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# =============================================================
# 4.  PUBLIC ENTRY POINT
# =============================================================

def generate_personalized_music(
    artist_name: str,
    genre: str,
    mood: str,
    instrument: str,
    fuel: str,
    duration: int = 20,
    output_dir: str = "outputs",
    artist_confidence: int = 0,
    tribe: Optional[str] = None,
) -> dict:
    """
    Main entry point. Matches the call signature in step_4_generate_music().
    """
    prompt_data = build_ace_prompt(
        mood=mood,
        instrument=instrument,
        era=fuel,
        genre=genre,
        tribe=tribe or genre,
        artist_confidence=artist_confidence,
        duration_seconds=duration,
    )

    uid         = uuid.uuid4().hex[:8]
    filename    = f"melody_{mood}_{genre}_{uid}.wav"
    output_path = Path(output_dir) / filename

    print(f"\n{'='*60}")
    print(f"[music_generator] Artist : {artist_name} ({artist_confidence}% confidence)")
    print(f"[music_generator] Genre  : {genre}")
    print(f"[music_generator] Tribe  : {tribe or genre}")
    print(f"[music_generator] Mood={mood}  Instrument={instrument}  Era={fuel}  Duration={duration}s")
    print(f"{'='*60}")
    print(f"[music_generator] TAGS:\n{prompt_data['tags']}\n")
    print(f"[music_generator] DESCRIPTION:\n{prompt_data['description']}\n")

    result = _call_ace_step(
        tags=prompt_data["tags"],
        description=prompt_data["description"],
        duration=duration,
        output_path=output_path,
    )

    return {
        "success":     result["success"],
        "audio_path":  result.get("audio_path"),
        "prompt":      prompt_data["full_prompt"],
        "tags":        prompt_data["tags"],
        "description": prompt_data["description"],
        "error":       result.get("error"),
    }


# =============================================================
# 5.  QUICK CLI TEST  (python music_generator.py)
# =============================================================
if __name__ == "__main__":
    test_cases = [
        dict(mood="happy",       instrument="synth",  era="actual", genre="Urban Pop Reggaeton", tribe="La Calle",        confidence=78),
        dict(mood="melancholic", instrument="piano",  era="80s",    genre="Jazz / Soul",         tribe="Los Nómadas",     confidence=60),
        dict(mood="angry",       instrument="guitar", era="90s",    genre="Alternative Rock",    tribe="Los Salvajes",    confidence=90),
        dict(mood="romantic",    instrument="violin", era="70s",    genre="Jazz / Afrobeat",     tribe="Los Románticos",  confidence=55),
    ]

    for tc in test_cases:
        p = build_ace_prompt(
            mood=tc["mood"],
            instrument=tc["instrument"],
            era=tc["era"],
            genre=tc["genre"],
            tribe=tc["tribe"],
            artist_confidence=tc["confidence"],
            duration_seconds=20,
        )
        print("=" * 70)
        print(f"TEST: mood={tc['mood']} | genre={tc['genre']} | era={tc['era']}")
        print(f"BPM hint : {p['_bpm_hint']}")
        print(f"Key hint : {p['_key_hint']}")
        print(f"Production: {p['_production']}")
        print()
        print("── TAGS ─────────────────────────────────────────────────────────")
        print(p["tags"])
        print()
        print("── DESCRIPTION ──────────────────────────────────────────────────")
        print(p["description"])
        print()