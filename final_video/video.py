"""
================================================================================
 GENERADOR DE VÍDEO ULTRA-RÁPIDO (ffmpeg puro) - Festival Cruïlla
================================================================================
Genera un vídeo horizontal de 20s usando plantillas PNG como overlay.

Arquitectura por frame (1920×1080):
  LEFT  half (0–959):   polaroid image (static across all 4 blocks)
  RIGHT half (960–1919): dynamic content per block
  OVERLAY (full frame):  template PNG — luminance used as alpha so black areas
                         are transparent (photo shows through) and colored/golden
                         areas are opaque (float on top).

Bloques (derecha, con xfade entre ellos):
  0-5s   foto1_landmarks.png  + imagen de landmarks
  5-10s  foto2_artists.png    + collage 3 artistas
  10-15s foto3_house.png      + sticker de la casa
  15-20s foto4_final.png      + frame final (XX Cruïlla, sin imagen extra)

Audio: pista de música durante los 20s.

Requisitos: ffmpeg + pillow + numpy
================================================================================
"""

import os
import subprocess
import time
import numpy as np
from PIL import Image

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

# ==============================================================================
# CONFIGURACIÓN - LINKS PRUEBA
# ==============================================================================
CONFIG = {
    "polaroid_path":     "/home/spG07/code/Festival-Cruilla/outputs/images/sonia1_tribe_poster_ca.png",
    "landmarks_path":    "/home/spG07/code/Festival-Cruilla/outputs/landmarks/sonia1_landmarks.png",
    "music_path":        "/home/spG07/code/Festival-Cruilla/outputs/music/af05bfeb-bd23-859d-133c-cb776de370ad.wav",
    "casa_sticker_path": "/home/spG07/code/Festival-Cruilla/final_video/casas/Casa_Techno.png",
    "artistas": [
        {"name": "Lena Pulse", "confidence": 8,  "image": "/home/spG07/data/Fake_Artists/4/4_1.png"},
        {"name": "Artista 2",  "confidence": 6,  "image": "/home/spG07/data/Fake_Artists/2/2_1.png"},
        {"name": "Artista 3",  "confidence": 5,  "image": "/home/spG07/data/Fake_Artists/19/image (1).png"},
    ],
    "output_path": "/home/spG07/code/Festival-Cruilla/final_video/resultado_ffmpeg.mp4",

    # Templates
    "template_landmarks": os.path.join(_TEMPLATES_DIR, "1_landmarks.png"),
    "template_artists":   os.path.join(_TEMPLATES_DIR, "2_artists.png"),
    "template_casa":      os.path.join(_TEMPLATES_DIR, "3_house.png"),
    "template_musica":    os.path.join(_TEMPLATES_DIR, "4_final.png"),

    # Technical parameters
    "resolucion":          (1920, 1080),
    "fps":                 30,
    "duracion_total":      20,
    "duracion_bloque":     5,
    "duracion_transicion": 1.0,
    "usar_gpu":            True,
    "ffmpeg_preset":       "ultrafast",
    "crf":                 23,
    "threads":             0,
}


# ==============================================================================
# IMAGE UTILITIES
# ==============================================================================

def cover_resize(img, target_w, target_h):
    """Resize + center-crop to fill target_w × target_h (CSS object-fit: cover)."""
    img = img.convert("RGB")
    src_w, src_h = img.size
    if src_w / src_h > target_w / target_h:
        new_h, new_w = target_h, int(target_h * src_w / src_h)
    else:
        new_w, new_h = target_w, int(target_w * src_h / src_w)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top  = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def contain_resize(img, target_w, target_h):
    """Resize to fit entirely within target_w × target_h (no crop)."""
    img = img.convert("RGBA")
    img.thumbnail((target_w, target_h), Image.LANCZOS)
    return img


def _load_template_overlay(path, W, H):
    """
    Load an RGB template and derive its alpha from distance-to-white:
      - pure white (255,255,255) → alpha 0   (fully transparent → photo shows through)
      - yellow/black pixels      → alpha 255  (fully opaque → float on top)
    The gradient edge between white and yellow creates a smooth blend.
    """
    tpl = Image.open(path).convert("RGB").resize((W, H), Image.LANCZOS)
    arr = np.array(tpl, dtype=np.int32)
    # distance from white = 255 - min(R,G,B); amplify so near-white also fades quickly
    dist = 255 - arr.min(axis=2)
    alpha = np.clip(dist * 3, 0, 255).astype(np.uint8)
    rgba = np.dstack([arr.astype(np.uint8), alpha])
    return Image.fromarray(rgba, "RGBA")


# ==============================================================================
# RIGHT-SIDE CONTENT GENERATORS (each returns an RGBA image at w_half × H)
# ==============================================================================

def _right_landmarks(cfg, w, h):
    return cover_resize(Image.open(cfg["landmarks_path"]), w, h).convert("RGBA")


def _right_artistas(cfg, w, h):
    artistas = cfg.get("artistas", [])
    base = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    if not artistas:
        return base
    principal   = artistas[0]
    secundarios = artistas[1:3]
    if secundarios:
        w_p = int(w * 0.62)
        base.paste(cover_resize(Image.open(principal["image"]), w_p, h), (0, 0))
        w_t = w - w_p
        h_t = h // max(len(secundarios), 1)
        for i, art in enumerate(secundarios):
            if art.get("image") and os.path.exists(art["image"]):
                base.paste(cover_resize(Image.open(art["image"]), w_t, h_t), (w_p, i * h_t))
    else:
        if principal.get("image") and os.path.exists(principal["image"]):
            base.paste(cover_resize(Image.open(principal["image"]), w, h), (0, 0))
    return base


def _right_casa(cfg, w, h):
    base = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    sticker = contain_resize(Image.open(cfg["casa_sticker_path"]), int(w * 0.75), int(h * 0.75))
    px = (w - sticker.width) // 2
    py = (h - sticker.height) // 2
    base.alpha_composite(sticker, (px, py))
    return base


def _right_musica(cfg, w, h):
    # Template (foto4_final) carries the full Cruïlla branding — right side stays black
    return Image.new("RGBA", (w, h), (0, 0, 0, 255))


# ==============================================================================
# FULL-FRAME COMPOSERS (polaroid left + content right + template overlay)
# ==============================================================================

def _compose(cfg, W, H, right_fn, template_key):
    w_half = W // 2
    base = Image.new("RGBA", (W, H), (0, 0, 0, 255))

    # Left half: polaroid (static)
    left = cover_resize(Image.open(cfg["polaroid_path"]), w_half, H).convert("RGBA")
    base.paste(left, (0, 0))

    # Right half: dynamic content
    right = right_fn(cfg, w_half, H)
    base.paste(right.convert("RGB"), (w_half, 0))

    # Template overlay on full frame
    tpl_path = cfg.get(template_key)
    if tpl_path and os.path.exists(tpl_path):
        tpl = _load_template_overlay(tpl_path, W, H)
        base.alpha_composite(tpl)

    return base


def frame_landmarks(cfg, W, H):
    return _compose(cfg, W, H, _right_landmarks, "template_landmarks")

def frame_artistas(cfg, W, H):
    return _compose(cfg, W, H, _right_artistas, "template_artists")

def frame_casa(cfg, W, H):
    return _compose(cfg, W, H, _right_casa, "template_casa")

def frame_musica(cfg, W, H):
    return _compose(cfg, W, H, _right_musica, "template_musica")


# ==============================================================================
# FFMPEG ENCODER SELECTION
# ==============================================================================

def _detectar_encoder(cfg):
    if not cfg.get("usar_gpu", True):
        return "libx264", ["-preset", cfg["ffmpeg_preset"], "-crf", str(cfg["crf"])]
    try:
        test = subprocess.run(
            ["ffmpeg", "-hide_banner", "-f", "lavfi", "-i", "color=black:s=64x64:d=0.1",
             "-c:v", "h264_nvenc", "-f", "null", "-"],
            capture_output=True, timeout=10,
        )
        if test.returncode == 0:
            return "h264_nvenc", ["-preset", "p1", "-tune", "ll"]
    except Exception:
        pass
    print("[!] GPU NVENC not available, using CPU (libx264).")
    return "libx264", ["-preset", cfg["ffmpeg_preset"], "-crf", str(cfg["crf"])]


# ==============================================================================
# MAIN VIDEO GENERATOR
# ==============================================================================

def generar_video(cfg=CONFIG):
    t0 = time.time()
    W, H   = cfg["resolucion"]
    fps    = cfg["fps"]
    dur    = cfg["duracion_bloque"]
    trans  = cfg["duracion_transicion"]

    workdir = "/tmp/festival_render"
    os.makedirs(workdir, exist_ok=True)

    # ---- 1) Render 4 full-frame static images (PIL, fast) ----
    print("-> Rendering frames (PIL)...")
    frame_landmarks(cfg, W, H).convert("RGB").save(f"{workdir}/b0.png")
    frame_artistas( cfg, W, H).convert("RGB").save(f"{workdir}/b1.png")
    frame_casa(     cfg, W, H).convert("RGB").save(f"{workdir}/b2.png")
    frame_musica(   cfg, W, H).convert("RGB").save(f"{workdir}/b3.png")
    t1 = time.time()
    print(f"   ({t1 - t0:.2f}s)")

    # ---- 2) Single ffmpeg call: xfade transitions + audio ----
    # Block durations: d0=dur, d1/d2/d3=dur+trans so xfade offsets line up to 20s exactly
    d0 = dur
    d1 = d2 = d3 = dur + trans
    duracion_total = d0 + d1 + d2 + d3 - 3 * trans  # = 20s with defaults

    off1 = d0 - trans
    off2 = d0 + d1 - 2 * trans
    off3 = d0 + d1 + d2 - 3 * trans

    encoder, encoder_flags = _detectar_encoder(cfg)

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-framerate", str(fps), "-t", str(d0), "-i", f"{workdir}/b0.png",
        "-loop", "1", "-framerate", str(fps), "-t", str(d1), "-i", f"{workdir}/b1.png",
        "-loop", "1", "-framerate", str(fps), "-t", str(d2), "-i", f"{workdir}/b2.png",
        "-loop", "1", "-framerate", str(fps), "-t", str(d3), "-i", f"{workdir}/b3.png",
        "-stream_loop", "-1", "-i", cfg["music_path"],
    ]

    filter_complex = (
        f"[0:v]format=yuv420p[b0];"
        f"[1:v]format=yuv420p[b1];"
        f"[2:v]format=yuv420p[b2];"
        f"[3:v]format=yuv420p[b3];"
        f"[b0][b1]xfade=transition=fade:duration={trans}:offset={off1}[x1];"
        f"[x1][b2]xfade=transition=fade:duration={trans}:offset={off2}[x2];"
        f"[x2][b3]xfade=transition=fade:duration={trans}:offset={off3}[video]"
    )

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[video]",
        "-map", "4:a",
        "-t", str(duracion_total),
        "-c:v", encoder, *encoder_flags,
        "-c:a", "aac", "-b:a", "192k",
        "-threads", str(cfg.get("threads", 0)),
        "-movflags", "+faststart",
        cfg["output_path"],
    ]

    os.makedirs(os.path.dirname(cfg["output_path"]), exist_ok=True)
    print("-> Rendering video (ffmpeg)...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    t2 = time.time()

    if result.returncode != 0:
        print("ERROR in ffmpeg:")
        print(result.stderr[-3000:])
        raise RuntimeError("ffmpeg failed — see log above")

    print(f"   ({t2 - t1:.2f}s)")
    print(f"Done in {t2 - t0:.2f}s total -> {cfg['output_path']}")
    return cfg["output_path"]


if __name__ == "__main__":
    generar_video(CONFIG)
