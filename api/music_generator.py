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
import os, time, uuid, wave, struct, requests
from pathlib import Path

MIN_AUDIO_DURATION_SEC = 20   # reject and retry if shorter than this
MAX_GENERATION_ATTEMPTS = 3   # maximum API calls per request
FADE_OUT_SEC = 0.4            # fade-out duration applied when trimming

# =============================================================
# 1.  VOCABULARY MAPS
# =============================================================

# 1A. MOOD
MOOD_MAP: dict[str, dict] = {
    "happy": {
        "tags": "euphoric, uplifting, triumphant, bright major tonality, ascending melodic hook, joyful crowd energy",
        "desc": (
            "radiates infectious joy through a bright, ascending melodic hook built on I–V–vi–IV major chords. "
            "The melody rises confidently with each bar, creating a sense of triumph and forward momentum that pulls the crowd upward"
        ),
        "bpm_hint": "128 BPM",
        "key_hint": "major key, bright and open harmonic palette",
    },
    "sad": {
        "tags": "nostalgic, bittersweet, longing, minor descending melody, emotional resonance, evocative atmosphere",
        "desc": (
            "carries a deeply emotive, descending minor melodic line that feels like something remembered but lost. "
            "The harmonic movement resolves downward through vi–IV–I–V, creating an aching sense of longing that "
            "transforms into acceptance and beauty at the drop"
        ),
        "bpm_hint": "120 BPM",
        "key_hint": "natural minor key, warm harmonic tension",
    },
    "chill": {
        "tags": "relaxed groove, laid-back swing, open chord voicings, spacious atmosphere, sunset warmth, floating melody",
        "desc": (
            "flows with a loose, swung rhythmic feel and wide open chord voicings—major 7ths and suspended 4ths—that "
            "leave breathing room between each note. The melody drifts in gentle, unhurried phrases, creating a sensation "
            "of golden-hour suspension where time slows down"
        ),
        "bpm_hint": "115–120 BPM",
        "key_hint": "Lydian or major 7th tonality, airy and unresolved tension",
    },
    "hype": {
        "tags": "peak-time energy, adrenaline surge, high-tension riser, punishing drop, crowd ignition, dominant melodic stab",
        "desc": (
            "builds to a razor-sharp, punishing drop using short staccato melodic stabs on the dominant chord that create "
            "maximum rhythmic tension before release. The energy escalates through a white-noise riser that compresses the "
            "entire frequency spectrum, then explodes into a massive, repetitive anthem hook engineered to ignite a crowd"
        ),
        "bpm_hint": "132–140 BPM",
        "key_hint": "major key, dominant-tonic tension, explosive harmonic release",
    },
}

# 1B. INSTRUMENT
INSTRUMENT_MAP: dict[str, dict] = {
    "guitar": {
        "tags": "electric guitar lead, single-note pentatonic riff, overdriven string texture, melodic guitar hook",
        "desc": (
            "driven by a distinct single-note electric guitar riff that defines the central melodic identity of the track. "
            "The guitar alternates between a clean, cutting lead tone in the build and a warm, slightly overdriven texture "
            "at the drop, giving the melody a human, expressive quality"
        ),
        "texture": "organic string attack, pick articulation, warm harmonic overtones, melodic sustain",
    },
    "piano": {
        "tags": "driving staccato piano chords, arpeggiated right-hand melody, hammered harmonic rhythm, anthemic piano hook",
        "desc": (
            "anchored by a piano delivering crisp, hammered staccato chords on every beat in the build, then opening into "
            "a flowing arpeggiated right-hand melody at the drop. The piano's bright upper register carries the melodic hook "
            "while the low register provides harmonic weight"
        ),
        "texture": "percussive attack, bright upper harmonics, resonant low-end chord body, rhythmic drive",
    },
    "trumpet": {
        "tags": "syncopated brass stab, call-and-response horn phrase, bold fanfare motif, celebratory brass lead",
        "desc": (
            "punctuated by a bold brass section playing a syncopated, call-and-response horn phrase that acts as the track's "
            "central melodic signature. The trumpet delivers a short, punchy fanfare motif that repeats and evolves, "
            "cutting through the mix with a bright, projecting timbre"
        ),
        "texture": "sharp brass attack, bright projecting tone, wide midrange presence, triumphant harmonic character",
    },
    "drums": {
        "tags": "four-on-the-floor kick pattern, crisp snare on two and four, rolling 16th-note hi-hats, percussion-led groove",
        "desc": (
            "percussion-forward with the melodic identity carried by tuned percussive elements—tom fills, "
            "pitched cowbell motifs, and syncopated snare ghost notes—woven around a solid four-on-the-floor kick. "
            "The rhythm IS the melody here, with each percussion hit placed to create forward motion"
        ),
        "texture": "punchy transient attack, deep sub-kick body, crisp snare crack, kinetic rhythmic momentum",
    },
}

# 1C. ERA
ERA_MAP: dict[str, dict] = {
    "medieval": {
        "tags": "modal melody, Dorian or Mixolydian scale, hurdy-gurdy texture, ancient folk motif fused with modern sub-bass",
        "desc": (
            "fuses a distinctly modal melodic identity—built on the Dorian or Mixolydian scale rather than conventional "
            "major/minor—with a modern festival sub-bass foundation. The melody carries the microtonal tension of ancient "
            "folk music: drone-based, cyclical phrases that feel timeless yet dance-ready"
        ),
        "production": "hybrid acoustic-electronic, modal harmonic color, natural reverb decay, clean sub-bass layer",
    },
    "90s": {
        "tags": "analog synth lead, TB-303 acid bass hint, vintage eurodance chord stab, warm tape saturation, retro rave energy",
        "desc": (
            "saturated with the analog warmth of 1990s rave culture: a sharp, slightly detuned synth lead plays the melody "
            "with the characteristic portamento glide of classic eurodance, while chord stabs arrive on every offbeat with "
            "the punchy, slightly compressed quality of hardware synthesizers recorded to tape"
        ),
        "production": "analog saturation, slight tape warmth, mid-forward EQ, punchy transient shaping",
    },
    "futuristic": {
        "tags": "granular synthesis texture, pitch-shifted melodic fragments, hypermodern sound design, deconstructed beat, forward-thinking timbre",
        "desc": (
            "dissolves conventional melody into a fragmented, granular texture where pitched sound-design elements—stretched, "
            "pitch-shifted, and time-warped—form the melodic identity. Notes arrive at unexpected rhythmic positions, "
            "creating a sense of controlled chaos that still resolves into recognizable harmonic patterns"
        ),
        "production": "granular processing, wide stereo imaging, sub-bass precision, hypermodern mastering limiter",
    },
    "actual": {
        "tags": "sidechain-compressed lead, modern festival mix, crisp high-shelf presence, contemporary EDM production aesthetic",
        "desc": (
            "mastered to current festival production standards: the lead melody rides sidechain compression that pulses "
            "rhythmically with the kick, creating a breathing, pumping quality that feels alive. The mix is clean and "
            "precise, with controlled low-end and a slightly lifted high shelf for air and presence on large PA systems"
        ),
        "production": "sidechain compression, modern mastering, crisp high-end, precise low-frequency control",
    },
}

# 1D. CASAS (Mapped internally via the 'genre' parameter)
# Each entry is written so that ANY listener familiar with the genre
# would immediately recognize it from the first 5 seconds of audio.
CASAS_MAP: dict[str, dict] = {
    "indie": {
        "tags": (
            "indie rock, jangly clean electric guitar arpeggios, Fender Telecaster tone, "
            "reverb-drenched guitar chords, melodic indie bass line following the harmony, "
            "live acoustic drum kit with room reverb, indie pop chord progression, "
            "strummed open guitar chords, organic warm guitar texture"
        ),
        "desc": (
            "THIS IS AN INDIE ROCK TRACK. The defining sound is a clean, jangly electric guitar "
            "playing arpeggiated open chords with natural reverb—the exact timbre of a Fender Telecaster "
            "through a clean amp. The guitar is front and center: it carries both the rhythm (strummed "
            "chord stabs on beats 2 and 4) and the melody (a single-note lead line between chord hits). "
            "A melodic bass guitar follows the chord roots with small fills. The drum kit sounds like a "
            "real room: brushed snare, overhead cymbals, and a slightly muffled kick. No heavy synthesis. "
            "The entire sound should feel like a live indie band on a festival stage."
        ),
        "vibe": "live indie band sound, clean jangly guitar, organic warmth, emotional guitar melody",
    },
    "pop": {
        "tags": (
            "pop EDM, bright glossy synthesizer lead melody, supersaw synth, polished commercial production, "
            "four-on-the-floor kick drum, clap on beats 2 and 4, filtered synth build, "
            "clean sidechain compression pumping, radio-ready pop hook, catchy repetitive melodic phrase"
        ),
        "desc": (
            "THIS IS A COMMERCIAL POP EDM TRACK. The defining sound is a bright, glossy supersaw synthesizer "
            "playing a simple, instantly memorable melodic hook—a short phrase of 4–6 notes that repeats and "
            "sits perfectly in the upper midrange. The production is immaculate: a crisp four-on-the-floor kick, "
            "a sharp clap on beats 2 and 4, and a synth lead that breathes with sidechain compression on every "
            "beat. The build strips the melody down to a filtered, rising synth that cuts off sharply before "
            "the drop. The drop reveals the full, polished hook with maximum brightness and commercial energy. "
            "It should sound like a top-10 radio hit on a festival main stage."
        ),
        "vibe": "bright polished commercial sound, catchy supersaw hook, maximum radio appeal, clean EDM energy",
    },
    "rock": {
        "tags": (
            "rock, heavily distorted electric guitar, power chords, palm-muted guitar riff, "
            "overdriven Marshall amp tone, crashing live cymbals, powerful snare crack, "
            "driving bass guitar following kick drum, stadium rock energy, "
            "guitar solo or melodic lead guitar line, crunchy guitar distortion"
        ),
        "desc": (
            "THIS IS A ROCK TRACK. The defining sound is a heavily distorted electric guitar playing "
            "a crunchy, aggressive riff—the kind of overdriven Marshall amp tone that fills a stadium. "
            "The guitar alternates between palm-muted rhythmic chunks on the low strings (creating a "
            "percussive, chunky rhythm) and open power chord crashes on the beats. A separate lead guitar "
            "carries the melodic line with sustained, singing distortion. The drums are loud and live: "
            "a crashing ride cymbal, a massive snare crack, and a felt-tip kick drum. A driving bass guitar "
            "locks in with the kick drum. There are NO synthesizers as the primary sound—guitars and live "
            "drums dominate everything. It should sound like a rock band at full volume outdoors."
        ),
        "vibe": "heavy guitar distortion, stadium rock power, live band energy, riff-driven melody",
    },
    "techno": {
        "tags": (
            "techno, relentless 4/4 kick drum at 138 BPM, industrial techno, dark warehouse atmosphere, "
            "TB-303 acid bassline with resonant filter sweep, 16th-note closed hi-hats, "
            "reverb-drenched snare clap, dark hypnotic loop, minimal dark synth texture, "
            "hard techno kick, driving mechanical rhythm"
        ),
        "desc": (
            "THIS IS A TECHNO TRACK. The defining sound is a relentless, hard-hitting 4/4 kick drum "
            "at exactly 138 BPM that never stops—loud, punchy, and industrial. Layered above it: "
            "a TB-303 acid bassline with its characteristic resonant filter sweep moving up and down, "
            "creating the iconic 'wah-wah' acid sound that defines the genre. Closed hi-hats pulse on "
            "every 16th note with mechanical precision. A heavily reverbed snare or clap lands on beats "
            "2 and 4. The 'melody' is minimal: a dark, short synth phrase of 2–3 notes that loops "
            "hypnotically. The atmosphere is dark, industrial, warehouse. There are NO pop melodies, "
            "NO bright sounds, NO joyful elements. Pure mechanical energy."
        ),
        "vibe": "relentless 4/4 kick, dark industrial atmosphere, acid 303 bassline, hypnotic techno loop",
    },
    "urban": {
        "tags": (
            "trap music, thunderous 808 bass with pitch slide, trap hi-hat triplet rolls, "
            "snare on beat 3, dark cinematic strings or piano, half-time trap rhythm, "
            "sub-bass dominant mix, trap beat, dark atmospheric pads, "
            "melodic trap, pitched 808 bass notes carrying the harmony"
        ),
        "desc": (
            "THIS IS A TRAP / URBAN TRACK. The defining sound is a thunderous 808 sub-bass that slides "
            "between pitched notes—each 808 hit starts at one pitch and glides down, creating a physical, "
            "chest-hitting sub-bass melody that IS the harmonic foundation of the track. The rhythm is "
            "half-time trap: a snare on beat 3 only (not 2 and 4), with fast, stuttering trap hi-hat "
            "triplet rolls (the characteristic 'tss-ts-ts-ts' pattern) filling the space between. "
            "Dark atmospheric strings or a minor-key piano plays a simple, melancholic melodic phrase "
            "above the 808. The overall feel is dark, heavy, and cinematic. "
            "It should be immediately recognizable as trap music the moment the 808 hits."
        ),
        "vibe": "808 sub-bass dominance, trap hi-hat rolls, dark cinematic atmosphere, half-time heavy groove",
    },
    "unknown": {
        "tags": (
            "genre-fusion, crossover festival track, hybrid instrumentation, "
            "unexpected genre blend, eclectic festival energy"
        ),
        "desc": (
            "A genre-defying festival track that consciously blends sonic hallmarks from multiple genres: "
            "a drop that introduces an unexpected instrument or rhythm pattern from a different style. "
            "The arrangement creates deliberate tension between contrasting sonic worlds."
        ),
        "vibe": "deliberate genre collision, unexpected sonic identity, crossover energy",
    },
}

# 1E. FESTIVAL QUALITY STACK
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
        f"FULL {duration_seconds}-SECOND TRACK, never cut short, sustain music until the very end, "
        f"stripped-back 10-second build-up with teased melodic motif, "
        f"full melodic drop at second 10, sustained peak chorus from second 10 to {duration_seconds - 3}, "
        f"smooth fade outro from second {duration_seconds - 3} to {duration_seconds}, "
        f"complete {duration_seconds}-second duration, do not stop early, balanced gain, clean mixing"
    )
    structure_desc = (
        f"IMPORTANT: This track MUST fill the complete {duration_seconds} seconds — do not stop or fade out early. "
        f"The track follows a precise arrangement arc: the first 10 seconds introduce a stripped-back "
        f"build-up that teases only a fragment of the core melodic motif. "
        f"At exactly second 10, the full melody arrives with its complete harmonic layer and a clear energy surge. "
        f"This peak melodic statement is sustained continuously from second 10 through second {duration_seconds - 3} "
        f"— the melody must keep playing through this entire section without stopping or trailing off. "
        f"From second {duration_seconds - 3} to {duration_seconds}, all elements resolve smoothly into a clean outro. "
        f"The music must be present and active for the full {duration_seconds} seconds. "
        f"The overall volume is perfectly normalized with a soft limiter to ensure maximum punch and clarity, "
        f"completely avoiding any digital clipping, harsh noise, or audio distortion."
    )

    # Genre tags go FIRST so the model anchors on genre identity before any modifier
    tags_parts = [
        c["tags"],          # genre-defining sounds — most important
        c["vibe"],          # genre vibe reinforcement
        m["tags"],          # mood colour
        m["bpm_hint"],
        m["key_hint"],
        i["tags"],          # instrument texture layered on top of genre
        e["tags"],          # era production style
        structure_tag,
        FESTIVAL_QUALITY_TAGS,
    ]
    tags = ", ".join(filter(None, tags_parts))

    description = (
        # Genre paragraph comes first and is stated explicitly — sets the sonic contract
        f"{c['desc']} "
        f"The mood adds {m['desc']}. "
        f"The featured instrument contributes {i['desc']} within the genre's sonic framework. "
        f"The production era is {e['desc']}. "
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
# 3.  HELPERS
# =============================================================

def _wav_duration(path: Path) -> float:
    """Return duration in seconds of a WAV file, or 0.0 on any error."""
    try:
        with wave.open(str(path), "rb") as wf:
            return wf.getnframes() / float(wf.getframerate())
    except Exception:
        return 0.0


def _trim_or_pad_wav(path: Path, target_seconds: float) -> None:
    """
    Trim or zero-pad a WAV file in-place to exactly target_seconds.
    When trimming, applies a short linear fade-out over the last FADE_OUT_SEC
    so the cut doesn't sound abrupt.
    """
    with wave.open(str(path), "rb") as wf:
        params      = wf.getparams()
        framerate   = wf.getframerate()
        sampwidth   = wf.getsampwidth()
        nchannels   = wf.getnchannels()
        target_frames = int(target_seconds * framerate)
        actual_frames = wf.getnframes()

        if actual_frames >= target_frames:
            raw = wf.readframes(target_frames)
        else:
            raw = wf.readframes(actual_frames)

    if actual_frames >= target_frames:
        # Apply linear fade-out over the last FADE_OUT_SEC of the trimmed audio
        fade_frames = min(int(FADE_OUT_SEC * framerate), target_frames)
        frame_size  = sampwidth * nchannels
        # Signed-integer format string for struct (1-byte unsigned treated as signed)
        fmt = {1: "b", 2: "h", 4: "i"}.get(sampwidth, "h")

        buf = bytearray(raw)
        fade_start = target_frames - fade_frames
        for f in range(fade_start, target_frames):
            factor = 1.0 - (f - fade_start) / fade_frames
            base   = f * frame_size
            for ch in range(nchannels):
                off    = base + ch * sampwidth
                sample = struct.unpack_from(fmt, buf, off)[0]
                struct.pack_into(fmt, buf, off, int(sample * factor))
        raw = bytes(buf)
    else:
        # Pad with silence to reach the target length
        missing_frames = target_frames - actual_frames
        raw += b"\x00" * (missing_frames * sampwidth * nchannels)

    tmp = path.with_suffix(".tmp.wav")
    with wave.open(str(tmp), "wb") as wf_out:
        wf_out.setparams(params)
        wf_out.writeframes(raw)
    tmp.replace(path)


# =============================================================
# 4.  ACE STEP 1.5 API CALLER
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
# 5.  PUBLIC ENTRY POINT
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

    result = {"success": False, "error": "No attempts made"}
    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        attempt_path = output_path.with_stem(f"{output_path.stem}_a{attempt}")
        result = _call_ace_step(
            tags=prompt_data["tags"],
            description=prompt_data["description"],
            duration=duration,
            output_path=attempt_path,
        )
        if not result["success"]:
            print(f"[music_generator] Attempt {attempt} failed: {result.get('error')}")
            break  # API error — no point retrying the same call

        actual_dur = _wav_duration(attempt_path)
        print(f"[music_generator] Attempt {attempt}: audio duration = {actual_dur:.1f}s")

        if actual_dur >= MIN_AUDIO_DURATION_SEC:
            # Trim or pad to exactly the requested duration, then keep
            _trim_or_pad_wav(attempt_path, duration)
            attempt_path.replace(output_path)
            result["audio_path"] = str(output_path)
            print(f"[music_generator] Final audio trimmed/padded to exactly {duration}s")
            break

        print(
            f"[music_generator] Audio too short ({actual_dur:.1f}s < {MIN_AUDIO_DURATION_SEC}s), "
            f"retrying... ({attempt}/{MAX_GENERATION_ATTEMPTS})"
        )
        attempt_path.unlink(missing_ok=True)
        if attempt == MAX_GENERATION_ATTEMPTS:
            result = {"success": False, "error": f"Generated audio was always shorter than {MIN_AUDIO_DURATION_SEC}s"}

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