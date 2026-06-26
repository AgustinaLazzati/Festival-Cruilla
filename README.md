# Festival Cruilla — Tal Cara, Tal Beat

> **"Your face reveals your beat."**
> An AI-powered interactive experience that analyzes your photo, assigns you a festival tribe, dresses you like a matching artist, and generates a personalized music track. All in real time!

---

## Overview

**Tal Cara, Tal Beat** is a multimodal AI pipeline built for Festival Cruilla. It takes a photo of a festival attendee and runs it through a series of AI steps to produce a fully personalized creative output: a styled festival poster and a custom-generated music melody.

The system identifies which musical artist the attendee resembles most, maps them to one of five festival "tribes", applies the artist's visual style to the photo, and generates a short melody that matches the tribe's genre and mood.

---

## Pipeline
<img width="1585" height="676" alt="PIPELINE" src="https://github.com/user-attachments/assets/537570ec-1b9a-470a-8244-a60830a1a34d" />

The pipeline runs five sequential steps composing 3 main flows:

**Step 1 — Face → Artist Label (`face2label`)**
A trained MLP model analyzes the user's face and matches it to the closest artist in the Cruilla lineup. Returns the matched artist's name, genre, tribe, and confidence score.

**Step 2 — Clothing / Accessory Overlay (`clothing`)**
Applies the matched artist's signature look and accessories to the user's photo using style transfer.

**Step 3 — Music Generation (`api/music_generator` + ACE-Step 1.5)**
Builds a personalized prompt from the artist match and user answers (mood, instrument, era) and generates a ~20-second melody using the local ACE-Step 1.5 model.

**Step 4 — Tribe Background Composite (`background`)**
Removes the background from the styled photo using `rembg` and composites the subject onto a tribe-specific festival background, producing a full festival poster.

**Step 5 — Video Generation (`moviepy`)**
Combines the tribe poster and the generated audio clip into a final `.mp4` video file.

---

## The Five Tribes

Each artist in the lineup belongs to one of five festival tribes, each with its own visual identity and music style:

| Tribe | Description |
|---|---|
| 🏙️ La Calle | Urban sounds, hip-hop, trap, reggaeton |
| 🐾 Los Salvajes | Raw energy, rock, electronic, punk |
| 💘 Los Románticos | Emotional, indie, pop, soul |
| 🌍 Los Nómadas | World music, folk, afrobeat, fusion |
| ✨ Los Soñadores | Dream pop, ambient, synthwave, experimental |

---

## Repository Structure

```
Festival-Cruilla/
│
├── main.py                  # Pipeline orchestrator & CLI entry point
├── streamlit_app.py         # Streamlit web UI
├── Synthetic_data.py        # Synthetic data generation utilities
├── config.json              # Configuration file
├── run.sh                   # Shell runner script
│
├── face2label/              # Face recognition & artist matching model
│   ├── models/              # MLP predictor
│   └── logs/                # Trained model weights & label mappings
│
├── clothing/                # Clothing / accessory overlay module
│
├── background/              # Background removal & tribe poster composite
│
├── api/                     # Music prompt builder
│   └── music_generator.py
│
├── inputs/                  # Input images & tribe background assets
├── outputs/                 # Generated outputs
│   ├── images/              # Styled photos & tribe posters
│   ├── music/               # Generated audio files (.wav)
│   └── final_video/         # Final video outputs (.mp4)
│
├── QUICK_START.md           # Quick setup guide (Spanish)
├── UI_SETUP.md              # UI setup documentation
└── .gitignore
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- CUDA-compatible GPU (recommended for music generation)
- ACE-Step 1.5 model downloaded locally

### Installation

```bash
git clone https://github.com/AgustinaLazzati/Festival-Cruilla.git
cd Festival-Cruilla
pip install -r requirements.txt
```

Key dependencies include:

```
streamlit
rembg
Pillow
moviepy
torch
```

### Running the Streamlit UI

```bash
streamlit run streamlit_app.py
```

Then open `http://localhost:8501` in your browser.

### Running the CLI Pipeline

**Basic usage (no music):**
```bash
python main.py --image inputs/user.png
```

**Full pipeline with music generation:**
```bash
python main.py --image inputs/user.png --mood happy --instrument guitar --era actual --with-music
```

**Available CLI arguments:**

| Argument | Default | Description |
|---|---|---|
| `--image` | *(required)* | Path to input user photo |
| `--output` | auto-generated | Output path for styled image |
| `--mood` | `happy` | Mood for music generation |
| `--instrument` | `synth` | Instrument preference |
| `--era` | `actual` | Musical era (e.g. `actual`, `90s`, `80s`) |
| `--with-music` | disabled | Enable ACE-Step music generation |

### Example Output

```
Artist    : Bad Bunny (87%)
Tribe     : La Calle
Styled image  : outputs/images/user_styled.png
Tribe poster  : outputs/images/user_tribe_poster.png
Music         : outputs/music/user_audio.wav
Final video   : outputs/final_video/user_final.mp4
```

---

## Streamlit UI Walkthrough

The interactive UI guides the user through a step-by-step experience:

1. **Emoji Questions** — Select your mood, instrument, and energy level using large visual selectors.
2. **Camera Capture** — Take a photo directly in the browser using the device camera.
3. **Artist Match** — See which artist you've been matched with and the confidence score.
4. **Music Generation** — Generate your personalized 20-second song based on your tribe and answers.
5. **Tribe Summary** — View your tribe assignment with a visual poster.
6. **Download / Restart** — Download your result or start over.

> Camera access requires a browser with permission granted. Use `http://localhost:8501` (same device) for best results. HTTPS may be required when accessing from another machine on the network.

---

## Configuration

The `config.json` file controls key parameters. The `TRIBE_BACKGROUNDS` mapping in `main.py` links each tribe name to its background image asset in the `inputs/` folder:

```python
TRIBE_BACKGROUNDS = {
    "la calle":       "inputs/bg_la_calle.png",
    "los salvajes":   "inputs/bg_los_salvajes.png",
    "los romanticos": "inputs/bg_los_romanticos.png",
    "los nomadas":    "inputs/bg_los_nomadas.png",
    "los sonadores":  "inputs/bg_los_sonadores.png",
}
```

Layout constants:

```python
TEXT_BAND_FRACTION    = 0.22   # Fraction of poster height reserved for text band
SUBJECT_HEIGHT_FRACTION = 0.72  # How tall the subject appears relative to usable area
```

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'streamlit'`**
```bash
pip install streamlit
```

**`Port 8501 already in use`**
```bash
streamlit run streamlit_app.py --server.port 8502
```

**`Cannot find module 'acestep'`**
The music generator requires the ACE-Step 1.5 model. Verify the model is present:
```bash
ls models/ACE-Step-1.5/
```

**No background found for tribe**
Check that the tribe name in your artist CSV exactly matches one of the five tribe keys above (accent-insensitive matching is applied, but spelling must match).

**Camera not working in browser**
- Grant camera permissions in your browser settings.
- Use `http://localhost:8501` on the same machine — cross-device access may require HTTPS.
- Reload the page (F5) after granting permissions.

---

## 🤝 Contributing

This project was built as a creative AI installation for Festival Cruilla. Contributions, improvements, and new tribe backgrounds are welcome. Open an issue or pull request to get started.

---

## 📄 License

This project builds on the following open-source libraries and models:
 
| Dependency | License | Notes |
|---|---|---|
| [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5) | Apache 2.0 | Music generation model by ACE Studio & StepFun |
| [Streamlit](https://github.com/streamlit/streamlit) | Apache 2.0 | Web UI framework |
| [rembg](https://github.com/danielgatis/rembg) | MIT | Background removal |
| [MoviePy](https://github.com/Zulko/moviepy) | MIT | Video generation |
| [Pillow](https://github.com/python-pillow/Pillow) | MIT-CMU (HPND) | Image processing |
| [PyTorch](https://github.com/pytorch/pytorch) | BSD-3-Clause | Deep learning framework |
