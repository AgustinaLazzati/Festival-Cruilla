"""
music_generator.py
──────────────────
Prompt builder + ACE Step 1.5 caller for 20-second festival-ready melodies.

Pipeline:
  user answers (mood / instrument / era)
  + artist-match data (name / genre / tribe / confidence)
  ──► build_ace_prompt()
  ──► generate_personalized_music()   (calls ACE Step 1.5 HTTP API)

Every mapping produces vocabulary that ACE Step 1.5 was trained on:
  tags block  → short comma-separated descriptors  (genre, mood, texture…)
  description → one rich prose sentence            (production intent)
"""

from __future__ import annotations
import os, time, uuid, requests
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────────────────────
# 1.  VOCABULARY MAPS
#     Each key matches the "value" fields you already store in
#     session_state / CSV so no extra translation is needed.
# ─────────────────────────────────────────────────────────────

# ── 1A. MOOD ──────────────────────────────────────────────────
MOOD_MAP: dict[str, dict] = {
    # ── positive / energetic ──
    "happy": {
        "tags": "euphoric, upbeat, feel-good, bright, triumphant, joyful energy",
        "desc": "radiates pure joy and euphoria, built to make a festival crowd erupt",
        "bpm_hint": "120–128 BPM",
        "key_hint": "major key",
    },
    "excited": {
        "tags": "high-energy, adrenaline, electric, festival anthem, peak-time, explosive",
        "desc": "explosive peak-time energy engineered for the main stage drop",
        "bpm_hint": "128–140 BPM",
        "key_hint": "major key",
    },
    "romantic": {
        "tags": "sensual, warm, lush, intimate, dreamy, passionate",
        "desc": "deeply sensual and warm, with a slow-burn tension that feels cinematic",
        "bpm_hint": "70–90 BPM",
        "key_hint": "minor or dorian mode",
    },
    "melancholic": {
        "tags": "melancholic, introspective, bittersweet, emotional depth, wistful, haunting",
        "desc": "emotionally charged and introspective, evoking bittersweet nostalgia",
        "bpm_hint": "80–100 BPM",
        "key_hint": "minor key",
    },
    # ── intense / dark ──
    "angry": {
        "tags": "intense, driven, aggressive, raw, powerful, urgent",
        "desc": "fierce and relentless, channeling raw power into every beat",
        "bpm_hint": "140–160 BPM",
        "key_hint": "minor or phrygian mode",
    },
    "dark": {
        "tags": "dark, brooding, cinematic tension, mysterious, ominous, atmospheric",
        "desc": "brooding and cinematic, dripping with tension and shadowy atmosphere",
        "bpm_hint": "90–110 BPM",
        "key_hint": "minor or locrian mode",
    },
    # ── calm / reflective ──
    "calm": {
        "tags": "serene, meditative, flowing, peaceful, airy, spacious",
        "desc": "breathably serene, with open space and gentle forward motion",
        "bpm_hint": "60–80 BPM",
        "key_hint": "major or lydian mode",
    },
    "nostalgic": {
        "tags": "nostalgic, vintage warmth, retro soul, timeless, evocative, wistful",
        "desc": "drenched in warm vintage color, summoning a place that no longer exists",
        "bpm_hint": "85–100 BPM",
        "key_hint": "major or mixolydian mode",
    },
}

# ── 1B. INSTRUMENT ────────────────────────────────────────────
INSTRUMENT_MAP: dict[str, dict] = {
    "guitar": {
        "tags": "electric guitar lead, clean Stratocaster tone, fingerpicked arpeggios, overdriven riff",
        "desc": "driven by expressive guitar work ranging from clean arpeggios to saturated riffs",
        "texture": "organic, string-forward, mid-range warmth",
    },
    "acoustic_guitar": {
        "tags": "acoustic guitar, fingerstyle, resonant body, campfire warmth, nylon string",
        "desc": "anchored by an intimate acoustic guitar with natural room resonance",
        "texture": "warm, organic, unplugged intimacy",
    },
    "piano": {
        "tags": "concert grand piano, melodic piano runs, harmonic piano chords, sustained notes",
        "desc": "built around a grand piano delivering rich harmonic depth and melodic clarity",
        "texture": "dynamic range, classical meeting contemporary",
    },
    "synth": {
        "tags": "analog synthesizer lead, polysynth pads, modular textures, detuned supersaws, lush synth strings",
        "desc": "propelled by layered synthesizers from evolving pads to cutting lead lines",
        "texture": "electronic shimmer, lush harmonic overtones",
    },
    "drums": {
        "tags": "live drum kit, tight snare, punchy kick, driving rhythm, polyrhythmic percussion",
        "desc": "percussion-forward with a tight, punchy live drum feel at its core",
        "texture": "rhythmic backbone, kinetic, full-body impact",
    },
    "bass": {
        "tags": "electric bass guitar, sub-bass rumble, slap bass groove, deep low end, walking bass line",
        "desc": "rooted in a thick, grooving bass line that anchors the entire arrangement",
        "texture": "low-end weight, groove-centric, physical impact",
    },
    "violin": {
        "tags": "solo violin, soaring strings, legato bowing, orchestral strings, vibrato, cinematic strings",
        "desc": "led by soaring violin lines layered over lush orchestral string textures",
        "texture": "cinematic sweep, emotional resonance, classical gravitas",
    },
    "trumpet": {
        "tags": "solo trumpet, brass section stabs, muted trumpet, jazz brass, fanfare horn",
        "desc": "punctuated by bold brass—ranging from muted jazz nuance to triumphant fanfares",
        "texture": "bright, projecting, celebratory edge",
    },
}

# ── 1C. ERA ───────────────────────────────────────────────────
ERA_MAP: dict[str, dict] = {
    "60s": {
        "tags": "1960s production, mono warmth, lo-fi tape saturation, Motown soul, British Invasion",
        "desc": "produced with 1960s analogue tape warmth and a vintage mono aesthetic",
        "production": "tape saturation, room reverb, minimal processing",
    },
    "70s": {
        "tags": "1970s, warm analogue mix, disco groove, funk influence, vinyl crackle, AM radio warmth",
        "desc": "steeped in 1970s analogue richness with a funky, warm vinyl character",
        "production": "thick analogue saturation, live room feel, prominent bass",
    },
    "80s": {
        "tags": "1980s, gated reverb drums, DX7 synth pads, New Wave, power ballad production, retro-futuristic",
        "desc": "channeling 1980s bombast—gated snare, shimmering DX7 pads, and a cinematic reverb wash",
        "production": "gated reverb, digital synths, layered synth pads, big room sound",
    },
    "90s": {
        "tags": "1990s, lo-fi grunge warmth, boom-bap hip-hop, alternative rock, Britpop, shoegaze wall of sound",
        "desc": "carries the raw analogue warmth and emotional directness of 1990s alternative and hip-hop",
        "production": "analogue warmth, slight saturation, lo-fi tape hiss, live drum recording",
    },
    "2000s": {
        "tags": "2000s pop-rock, polished digital production, Pro Tools era, maximalist mix, early EDM influence",
        "desc": "polished with early 2000s digital clarity—punchy, radio-ready, and precisely mixed",
        "production": "digital clarity, maximalist layering, compressed punchy mix",
    },
    "2010s": {
        "tags": "2010s, EDM drop structure, trap hi-hats, future bass, heavy sidechain, streaming-era production",
        "desc": "built on 2010s production DNA—sidechain pumping, trap-influenced rhythms, festival-ready drops",
        "production": "heavy sidechain compression, 808 sub-bass, trap hi-hats, future bass chords",
    },
    "actual": {
        "tags": "contemporary 2024 production, hi-fi master, modern mix, streaming-optimized, crystal-clear audio",
        "desc": "mastered to modern streaming standards—wide stereo field, punchy transients, immaculate detail",
        "production": "modern mastering, wide stereo image, loudness normalization, crisp high-end",
    },
    "futuristic": {
        "tags": "futuristic, hyperpop, glitchy, experimental electronic, AI-generated textures, avant-garde",
        "desc": "pushed into a futuristic sound design space with glitchy, hypermodern textures",
        "production": "pitch-shifted vocals, granular synthesis, extreme processing, generative textures",
    },
}

# ── 1D. GENRE / TRIBE ─────────────────────────────────────────
# Describes the *sound world* without naming the matched artist.
# Keys match genre + tribe fields from the artist-match payload.
GENRE_MAP: dict[str, dict] = {
    # ── Urban / Latin ──
    "reggaeton": {
        "tags": "reggaeton, dembow rhythm, perreo groove, 808 bass thud, Latin trap hi-hats, urbano latino",
        "desc": "locked into a dembow grid with rolling 808 sub-bass and Latin urban flair",
        "sub_genre": "reggaeton moderno, trap latino",
    },
    "latin_trap": {
        "tags": "Latin trap, sliding 808, trap hi-hat rolls, dark Latin melody, drill influence, urbano",
        "desc": "merging sliding 808s and trap hi-hat patterns with a dark Latin melodic sensibility",
        "sub_genre": "Latin drill, afrobeats fusion",
    },
    "salsa": {
        "tags": "salsa, clave rhythm, brass montuno, congas, timbales, Cuban son, Caribbean groove",
        "desc": "driven by clave, swinging brass montunos, and infectious Caribbean percussion",
        "sub_genre": "salsa romántica, salsa dura",
    },
    # ── Hip-Hop ──
    "hip_hop": {
        "tags": "hip-hop, boom-bap, sample chop, vinyl texture, punchy kick, soulful loop, urban grit",
        "desc": "rooted in boom-bap tradition with soulful sample chops and a gritty urban energy",
        "sub_genre": "conscious hip-hop, golden era",
    },
    "trap": {
        "tags": "trap, triple hi-hats, 808 sub-bass, dark minor melody, hi-hat rolls, dark trap aesthetic",
        "desc": "defined by rattling hi-hat rolls, thunderous 808s, and a menacing minor melody",
        "sub_genre": "melodic trap, dark trap",
    },
    "drill": {
        "tags": "drill, sliding 808, dark synth, off-beat kick, UK drill stab, menacing atmosphere",
        "desc": "icy and minimal with sliding 808 basslines and a distinctly menacing atmosphere",
        "sub_genre": "UK drill, NY drill",
    },
    # ── Electronic / Dance ──
    "edm": {
        "tags": "EDM, festival anthem, massive drop, supersaw lead, build-up tension, main stage energy",
        "desc": "engineered for main-stage impact with a towering supersaw drop and crowd-lifting build",
        "sub_genre": "progressive house, electro house",
    },
    "house": {
        "tags": "house music, four-on-the-floor kick, soulful piano chord, deep groove, warm bass line",
        "desc": "built on a warm four-on-the-floor groove with soulful piano chords and deep bass",
        "sub_genre": "deep house, afro house",
    },
    "techno": {
        "tags": "techno, industrial percussion, hypnotic loop, dark atmosphere, driving kick, acid bass",
        "desc": "relentlessly hypnotic with industrial percussion and a driving, acid-inflected bassline",
        "sub_genre": "dark techno, minimal techno",
    },
    "future_bass": {
        "tags": "future bass, emotional chords, lush synth chords, pitched vocal chop, wobbly bass, euphoric drop",
        "desc": "emotive and lush, with shimmering chord stabs and a euphoric pitched-vocal drop",
        "sub_genre": "melodic dubstep, chillwave",
    },
    # ── Rock / Alternative ──
    "rock": {
        "tags": "rock, power chord, distorted guitar, driving drums, anthemic chorus, stadium rock energy",
        "desc": "charged with distorted power chords, thundering drums, and an anthemic stadium energy",
        "sub_genre": "alternative rock, indie rock",
    },
    "metal": {
        "tags": "metal, heavy riff, palm-muted chug, double kick, aggressive, distorted down-tuned guitar",
        "desc": "brutally heavy with down-tuned riffs, palm-muted chugs, and relentless double-kick",
        "sub_genre": "modern metal, prog metal",
    },
    # ── Pop ──
    "pop": {
        "tags": "pop, radio-ready, hook-driven, polished production, bright melody, contemporary pop",
        "desc": "radio-optimized with an instantly memorable hook and pristine contemporary production",
        "sub_genre": "synth-pop, indie pop",
    },
    "k_pop": {
        "tags": "K-pop, glossy production, precise arrangement, bright synth, choreography-ready, hyper-polished",
        "desc": "hyper-polished with the signature K-pop blend of bright synths and precision arrangement",
        "sub_genre": "4th gen K-pop, neo soul K-pop",
    },
    # ── R&B / Soul ──
    "rnb": {
        "tags": "R&B, smooth groove, soulful chord, neo-soul warmth, lush pad, silky production",
        "desc": "silky and soulful, draped in warm neo-soul chords and a laid-back rhythmic pocket",
        "sub_genre": "neo-soul, alternative R&B",
    },
    "afrobeats": {
        "tags": "afrobeats, percussion-driven groove, highlife guitar, African rhythm, tropical melody",
        "desc": "pulsating with infectious African-inspired rhythms and bright highlife guitar motifs",
        "sub_genre": "afropop, afro fusion",
    },
    # ── Fallback ──
    "unknown": {
        "tags": "crossover, genre-blending, eclectic, adventurous, boundary-pushing",
        "desc": "genre-defying, blending elements from multiple traditions into something entirely fresh",
        "sub_genre": "experimental, crossover",
    },
}

# ── 1E. TRIBE (secondary genre from artist-match) ─────────────
TRIBE_MAP: dict[str, str] = {
    # Cruilla tribes
    "los_salvajes":   "raw guitar power, rebellious rock energy, distorted edge",
    "los_sonadores":  "electronic dreamscape, synthesizer atmosphere, nocturnal depth",
    "los_nomadas":    "world music rhythmic diversity, jazz harmony, organic groove",
    "los_romanticos": "melodic indie pop sensibility, heartfelt songwriting, summery warmth",
    "la_calle":       "urban street energy, hip-hop rhythmic grit, bass-heavy urban production",
    # Generic fallbacks
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

# ── 1F. FESTIVAL QUALITY STACK ────────────────────────────────
# These tags are ALWAYS appended so the model aims for
# professional, non-lo-fi output.
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


# ─────────────────────────────────────────────────────────────
# 2.  CORE PROMPT BUILDER
# ─────────────────────────────────────────────────────────────

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
      'tags'        → short comma-separated keyword block  (ACE Step tag input)
      'description' → rich prose sentence                  (ACE Step description input)
      'full_prompt' → concatenated tags + description      (single-string fallback)

    All keys are normalised to lowercase with underscores to match the maps.
    Unknown values fall back to sensible defaults gracefully.
    """

    # ── Normalise inputs ──
    mood       = (mood or "happy").lower().replace(" ", "_")
    instrument = (instrument or "synth").lower().replace(" ", "_")
    era        = (era or "actual").lower().replace(" ", "_")
    genre      = (genre or "pop").lower().replace(" ", "_").replace("-", "_")
    tribe      = (tribe or "pop").lower().replace(" ", "_").replace("-", "_")

    # ── Resolve maps (with fallbacks) ──
    m  = MOOD_MAP.get(mood,       MOOD_MAP["happy"])
    i  = INSTRUMENT_MAP.get(instrument, INSTRUMENT_MAP["synth"])
    e  = ERA_MAP.get(era,         ERA_MAP["actual"])
    g  = GENRE_MAP.get(genre,     GENRE_MAP["unknown"])
    t  = TRIBE_MAP.get(tribe,     "")

    # ── Structural / timing descriptor ──
    if duration_seconds <= 15:
        structure_tag  = "short cinematic intro, compact motif"
        structure_desc = f"a focused {duration_seconds}-second motif with immediate impact"
    elif duration_seconds <= 25:
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

    # ── Confidence modifier ──
    # High confidence → lean into the genre more specifically
    if artist_confidence >= 75:
        genre_weight = f"strong {g['sub_genre']} influence"
    elif artist_confidence >= 50:
        genre_weight = f"clear {g['sub_genre']} sensibility"
    else:
        genre_weight = f"subtle {genre} undertone"

    # ── Assemble TAGS block ──
    tags_parts = [
        g["tags"],                  # genre first (highest weight in ACE Step)
        m["tags"],                  # mood
        i["tags"],                  # instrument
        e["tags"],                  # era / production style
        genre_weight,               # confidence-scaled genre depth
        t,                          # tribal / secondary genre
        m["bpm_hint"],              # tempo hint
        m["key_hint"],              # key / mode hint
        structure_tag,              # duration structure
        FESTIVAL_QUALITY_TAGS,      # always: pro quality
    ]
    tags = ", ".join(filter(None, tags_parts))

    # ── Assemble DESCRIPTION block ──
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

    # ── Full single-string prompt (fallback / debug) ──
    full_prompt = f"[TAGS]: {tags}\n\n[DESCRIPTION]: {description}"

    return {
        "tags": tags,
        "description": description,
        "full_prompt": full_prompt,
        # expose resolved hints for debugging / UI display
        "_bpm_hint":  m["bpm_hint"],
        "_key_hint":  m["key_hint"],
        "_production": e["production"],
        "_texture":   i["texture"],
    }


# ─────────────────────────────────────────────────────────────
# 3.  ACE STEP 1.5 API CALLER
#     Replace ACE_STEP_API_URL with your actual endpoint.
#     The payload structure follows the ACE Step 1.5 HTTP spec.
# ─────────────────────────────────────────────────────────────

ACE_STEP_API_URL = os.getenv("ACE_STEP_API_URL", "http://localhost:7860/generate")
ACE_STEP_API_KEY = os.getenv("ACE_STEP_API_KEY", "")


def _call_ace_step(
    tags: str,
    description: str,
    duration: int,
    output_path: Path,
) -> dict:
    """
    Calls the ACE Step 1.5 HTTP endpoint.
    Returns {"success": True, "audio_path": str} or {"success": False, "error": str}.
    """
    payload = {
        # ACE Step 1.5 primary inputs
        "prompt":       tags,           # tag-style prompt
        "description":  description,    # prose description (used by the encoder)
        "duration":     duration,
        # Recommended inference settings for festival-quality 20s clips
        "steps":        100,            # more steps → better quality
        "cfg_scale":    7.0,            # classifier-free guidance strength
        "seed":         -1,             # -1 = random seed
        "scheduler":    "euler",
        "sample_rate":  44100,
        "format":       "wav",
    }

    headers = {"Content-Type": "application/json"}
    if ACE_STEP_API_KEY:
        headers["Authorization"] = f"Bearer {ACE_STEP_API_KEY}"

    try:
        response = requests.post(
            ACE_STEP_API_URL,
            json=payload,
            headers=headers,
            timeout=120,
        )
        response.raise_for_status()

        # ACE Step returns raw audio bytes
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)

        return {"success": True, "audio_path": str(output_path)}

    except requests.exceptions.Timeout:
        return {"success": False, "error": "ACE Step API timed out (>120s)."}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": f"Cannot reach ACE Step API at {ACE_STEP_API_URL}."}
    except requests.exceptions.HTTPError as exc:
        return {"success": False, "error": f"ACE Step API HTTP {exc.response.status_code}: {exc.response.text[:300]}"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ─────────────────────────────────────────────────────────────
# 4.  PUBLIC ENTRY POINT  (called from step_4_generate_music)
# ─────────────────────────────────────────────────────────────

def generate_personalized_music(
    artist_name: str,
    genre: str,
    mood: str,
    instrument: str,
    fuel: str,                      # maps to "era"
    duration: int = 20,
    output_dir: str = "outputs",
    artist_confidence: int = 0,
    tribe: Optional[str] = None,
) -> dict:
    """
    Main entry point.  Matches the call signature in step_4_generate_music().

    Parameters
    ----------
    artist_name       : matched artist (used for logging, NOT in the prompt)
    genre             : primary genre from artist-match  e.g. "reggaeton"
    mood              : emoji answer  e.g. "happy" | "melancholic" | …
    instrument        : emoji answer  e.g. "guitar" | "synth" | …
    fuel              : era emoji answer  e.g. "actual" | "80s" | …
    duration          : clip length in seconds (default 20)
    output_dir        : folder for saving .wav files
    artist_confidence : 0–100 from artist-match payload
    tribe             : secondary genre/tribe from artist-match payload

    Returns
    -------
    {
        "success"    : bool,
        "audio_path" : str | None,
        "prompt"     : str,          ← shown in the UI info box
        "tags"       : str,
        "description": str,
        "error"      : str | None,
    }
    """

    # ── Build the prompt ──
    prompt_data = build_ace_prompt(
        mood=mood,
        instrument=instrument,
        era=fuel,
        genre=genre,
        tribe=tribe or genre,        # fall back to genre if no tribe
        artist_confidence=artist_confidence,
        duration_seconds=duration,
    )

    # ── Determine output path ──
    uid          = uuid.uuid4().hex[:8]
    filename     = f"melody_{mood}_{genre}_{uid}.wav"
    output_path  = Path(output_dir) / filename

    # ── Log intent (without artist name in the prompt itself) ──
    print(
        f"[music_generator] Generating {duration}s clip | "
        f"artist-match: {artist_name} ({artist_confidence}%) | "
        f"mood={mood} instrument={instrument} era={fuel} genre={genre}"
    )
    print(f"[music_generator] TAGS:\n{prompt_data['tags']}\n")
    print(f"[music_generator] DESCRIPTION:\n{prompt_data['description']}\n")

    # ── Call ACE Step 1.5 ──
    result = _call_ace_step(
        tags=prompt_data["tags"],
        description=prompt_data["description"],
        duration=duration,
        output_path=output_path,
    )

    # ── Return unified response dict ──
    return {
        "success":     result["success"],
        "audio_path":  result.get("audio_path"),
        "prompt":      prompt_data["full_prompt"],   # shown in st.info()
        "tags":        prompt_data["tags"],
        "description": prompt_data["description"],
        "error":       result.get("error"),
    }


# ─────────────────────────────────────────────────────────────
# 5.  QUICK CLI TEST  (python music_generator.py)
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_cases = [
        dict(mood="happy",      instrument="synth",  era="actual", genre="reggaeton",   tribe="hip_hop",   confidence=78),
        dict(mood="melancholic", instrument="piano",  era="80s",    genre="pop",         tribe="rnb",       confidence=60),
        dict(mood="angry",      instrument="guitar", era="90s",    genre="rock",         tribe="rock",      confidence=90),
        dict(mood="romantic",   instrument="violin", era="70s",    genre="rnb",          tribe="classical", confidence=55),
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