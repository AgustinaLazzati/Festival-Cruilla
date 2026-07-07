"""
Servidor orquestador — Tal Cara, Tal Beat.

Expone DOS queries HTTP separadas, que llegan en momentos distintos:

  1) POST /session/start        -> los 4 parámetros (mood/instrument/era/casa)
                                    Lanza YA el proceso de música en GPU_MUSIC.
  2) POST /session/{id}/image   -> la imagen, ~5-10s después.
                                    Lanza el proceso de cara/vestuario en GPU_FACE.

Un hilo recolector por sesión espera los dos resultados (emparejados por
session_id) y, en cuanto están, genera el vídeo final localmente y lo deja
en outputs/final_video/ — sin QR, sin nada más.

Requisitos:
    pip install fastapi uvicorn python-multipart

Arrancar:
    python server.py
    # equivalente a: uvicorn server:app --host 0.0.0.0 --port 8000

Reutiliza las funciones ya definidas en main_2gpu.py (step_music,
workflow_crea_polaroid, step_rich_video, _pin_gpu, etc.) — este fichero
NO las reimplementa, solo las orquesta detrás de HTTP.
"""

import multiprocessing as mp
import shutil
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, Form, File
from fastapi.responses import JSONResponse

import main_2gpu as mpar  # reutiliza REPO_ROOT, step_*, _pin_gpu, etc.

app = FastAPI(title="Tal Cara, Tal Beat — Orquestador")

UPLOAD_DIR = mpar.REPO_ROOT / "inputs" / "_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# session_id -> dict con todo el estado de esa sesión
SESSIONS: dict[str, dict] = {}
SESSIONS_LOCK = threading.Lock()


# ==============================================================================
# Procesos hijo (idénticos a los de main_2gpu.py, reutilizados tal cual)
# ==============================================================================
def _music_process(mood, instrument, era, casa, gpu_id, queue):
    mpar._pin_gpu(gpu_id)
    t0 = time.perf_counter()
    mpar._log_gpu_binding("music-proc")
    try:
        result = mpar.step_music(mood, instrument, era, casa)
    except Exception as e:
        result = {"success": False, "error": str(e)}
    result["wall_time_s"] = time.perf_counter() - t0
    queue.put(("music", result))


def _image_process(image_path, output_path, language, gpu_id, queue):
    mpar._pin_gpu(gpu_id)
    t0 = time.perf_counter()
    mpar._log_gpu_binding("face-proc")
    try:
        result = mpar.workflow_crea_polaroid(image_path, output_path, language)
    except Exception as e:
        result = {"success": False, "error": str(e)}
    result["wall_time_s"] = time.perf_counter() - t0
    queue.put(("image", result))


# ==============================================================================
# Hilo recolector: espera los DOS resultados de una sesión y genera el vídeo
# ==============================================================================
def _collector(session_id: str):
    sess = SESSIONS[session_id]
    queue = sess["queue"]
    received = {}

    # Bloquea hasta tener tanto "music" como "image" (en cualquier orden).
    while len(received) < 2:
        tag, result = queue.get()
        received[tag] = result
        with SESSIONS_LOCK:
            sess[f"{tag}_result"] = result
            sess["status"] = f"{tag}_done"

    with SESSIONS_LOCK:
        sess["status"] = "generating_video"

    music_result = received["music"]
    image_result = received["image"]

    if not image_result.get("success"):
        with SESSIONS_LOCK:
            sess["status"] = "error"
            sess["error"] = image_result.get("error", "face pipeline failed")
        return

    artist_match   = image_result["artist_match"]
    tribe_poster   = image_result["tribe_poster"]
    landmarks_path = image_result["landmarks_path"]
    audio_path     = music_result.get("audio_path") if music_result.get("success") else None

    final_video = None
    if tribe_poster and audio_path:
        video_output = str(
            mpar.OUTPUT_VIDEO_DIR / f"{session_id}_final_{sess['language']}.mp4"
        )
        final_video = mpar.step_rich_video(
            polaroid_path=tribe_poster,
            landmarks_path=landmarks_path,
            audio_path=audio_path,
            artist_match=artist_match,
            casa=mpar._normalise_tribe(artist_match.get("tribe") or sess["casa"]),
            output_path=video_output,
            language=sess["language"],
        )

    with SESSIONS_LOCK:
        sess["status"] = "done" if final_video else "error"
        sess["final_video"] = final_video
        sess["artist_match"] = artist_match


# ==============================================================================
# QUERY 1 — llegan los 4 parámetros → arranca la GPU de música
# ==============================================================================
@app.post("/session/start")
def start_session(
    mood: str = Form(...),
    instrument: str = Form(...),
    era: str = Form(...),
    casa: str = Form(...),
    language: str = Form("ca"),
    gpu_music: int = Form(0),
    gpu_face: int = Form(1),
):
    session_id = uuid.uuid4().hex[:8]
    queue = mp.Queue()

    p_music = mp.Process(
        target=_music_process,
        args=(mood, instrument, era, casa, gpu_music, queue),
    )
    p_music.start()

    with SESSIONS_LOCK:
        SESSIONS[session_id] = {
            "queue": queue,
            "p_music": p_music,
            "p_face": None,
            "music_result": None,
            "image_result": None,
            "language": language,
            "casa": casa,
            "gpu_face": gpu_face,
            "status": "waiting_for_image",
            "created_at": time.time(),
        }

    # El recolector arranca ya: se queda esperando en queue.get() hasta que
    # también llegue el resultado de imagen (cuando exista el 2º proceso).
    threading.Thread(target=_collector, args=(session_id,), daemon=True).start()

    print(f"[server] Sesión {session_id} iniciada. Música → GPU {gpu_music} (PID {p_music.pid})")
    return {"session_id": session_id, "status": "music_started", "gpu_music": gpu_music}


# ==============================================================================
# QUERY 2 — llega la imagen (5-10s más tarde) → arranca la GPU de cara
# ==============================================================================
@app.post("/session/{session_id}/image")
def submit_image(session_id: str, file: UploadFile = File(...)):
    with SESSIONS_LOCK:
        sess = SESSIONS.get(session_id)

    if sess is None:
        return JSONResponse(status_code=404, content={"error": "session_id desconocido"})

    image_path = UPLOAD_DIR / f"{session_id}_{file.filename}"
    with open(image_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    output_path = str(mpar.OUTPUT_IMAGES_DIR / f"{session_id}_styled_{sess['language']}.png")

    p_face = mp.Process(
        target=_image_process,
        args=(str(image_path), output_path, sess["language"], sess["gpu_face"], sess["queue"]),
    )
    p_face.start()

    with SESSIONS_LOCK:
        sess["p_face"] = p_face
        sess["status"] = "processing_image"

    print(f"[server] Sesión {session_id}: imagen recibida. Cara → GPU {sess['gpu_face']} (PID {p_face.pid})")
    return {"session_id": session_id, "status": "image_received", "gpu_face": sess["gpu_face"]}


# ==============================================================================
# Consulta de estado (polling) — para saber cuándo está listo el vídeo
# ==============================================================================
@app.get("/session/{session_id}/status")
def get_status(session_id: str):
    with SESSIONS_LOCK:
        sess = SESSIONS.get(session_id)

    if sess is None:
        return JSONResponse(status_code=404, content={"error": "session_id desconocido"})

    return {
        "session_id":   session_id,
        "status":       sess["status"],
        "final_video":  sess.get("final_video"),
        "artist_match": sess.get("artist_match", {}).get("name") if sess.get("artist_match") else None,
        "error":        sess.get("error"),
    }


if __name__ == "__main__":
    import uvicorn

    mp.set_start_method("spawn", force=True)
    uvicorn.run(app, host="0.0.0.0", port=8000)