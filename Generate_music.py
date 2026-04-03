import sys
sys.path.insert(0, "/export/hhome/ps2g07/code/Festival-Cruilla/models/models/ACE-Step-1.5")

from acestep.handler import AceStepHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music

CHECKPOINTS_DIR = "/export/hhome/ps2g07/code/Festival-Cruilla/models/models/ace-step"

dit_handler = AceStepHandler()
dit_handler.initialize_service(
    project_root=CHECKPOINTS_DIR,
    config_path="acestep-v15-turbo",
    device="cuda",
)
params = GenerationParams(
    caption="upbeat electronic festival music with heavy bass, energetic crowd, euphoric synths, summer outdoor atmosphere",
    lyrics="",
    duration=30,
    bpm=128,
    vocal_language="en",
)

config = GenerationConfig(
    batch_size=1,
    audio_format="wav",
)

result = generate_music(
    dit_handler,
    None,
    params,
    config,
    save_dir="/export/hhome/ps2g07/code/Festival-Cruilla/outputs"
)

if result.success:
    print(f"✅ Generado: {result.audio_path}")
else:
    print(f"❌ Error: {result.error}")