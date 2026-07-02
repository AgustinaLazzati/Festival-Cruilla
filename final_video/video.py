"""
================================================================================
 GENERADOR DE VÍDEO ULTRA-RÁPIDO (ffmpeg puro) - Festival Cruïlla
================================================================================
Misma composición que generar_video.py (polaroid fija a la izquierda +
4 bloques con crossfade a la derecha + audio), pero sin moviepy:
 
  1. Python/PIL SOLO renderiza 5 imágenes estáticas (rapidísimo, <0.3s).
  2. UN ÚNICO comando ffmpeg hace el montaje completo: transiciones (filtro
     nativo `xfade`, en C), unión de columnas (`hstack`) y audio.
 
Esto es entre 10x y 30x más rápido que la versión con moviepy porque:
  - No hay overhead de Python evaluando frame a frame.
  - `xfade` corre en el core de ffmpeg, no en Python.
  - Se puede usar el encoder por hardware (NVENC) si hay GPU disponible.
  - Los stickers de las 5 casas se cachean en disco (no se regeneran cada vez).
 
Requisitos: ffmpeg instalado (con libx264 y, opcionalmente, h264_nvenc) + PIL.
    pip install pillow numpy --break-system-packages
 
Uso:
    python3 generar_video_rapido.py
================================================================================
"""
 
import os
import subprocess
import textwrap
import time
import hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ==============================================================================
# CONFIGURACIÓN - LINKS PRUEBA
# ==============================================================================
CONFIG = {
    # --- Rutas de entrada ---
    "polaroid_path":   "/home/spG07/code/Festival-Cruilla/outputs/images/sonia1_tribe_poster_ca.png",
    "landmarks_path":  "/home/spG07/code/Festival-Cruilla/outputs/images/sonia1_styled_ca.png",
    "music_path":      "/home/spG07/code/Festival-Cruilla/outputs/music/af05bfeb-bd23-859d-133c-cb776de370ad.wav",

    # --- Casa asignada ---
    "casa_nombre": "Tecno",
    "casa_sticker_path": "/home/spG07/code/Festival-Cruilla/final_video/casas/Casa_Techno.png",

    # --- Lista de artistas afines (puedes poner 1, 2, 3... los que quieras) ---
    # El primero de la lista se considera el "match principal".
    "artistas": [
        {"name": "Lena Pulse", "confidence": 8, "image": "/home/spG07/data/Fake_Artists/4/4_1.png"},
        {"name": "Artista 2",  "confidence": 6, "image": "/home/spG07/data/Fake_Artists/2/2_1.png"},
        {"name": "Artista 3",  "confidence": 5, "image": "/home/spG07/data/Fake_Artists/19/image (1).png"},
    ],

    # --- Salida ---
    "output_path": "/home/spG07/code/Festival-Cruilla/final_video/resultado_ffmpeg.mp4",

    # --- Parámetros técnicos ---
    "resolucion": (1920, 1080),   # ancho x alto (horizontal)
    "fps": 30,
    "duracion_total": 20,
    "duracion_bloque": 5,         # cada bloque de la derecha dura 5s
    "duracion_transicion": 1.0,   # crossfade entre bloques de la derecha
    "fuente_bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "fuente_regular": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",

    # --- Textos (edítalos a tu gusto) ---
    "texto_landmarks": "Así es cómo la IA te interpreta",
    "texto_casa_prefijo": "Perteneces a la casa",
    "texto_musica": "La música que suena representa tu identidad",
    #falta lo del artista??

     
    # --- Rendimiento ---
    "cache_dir":"/tmp/festival_cache",      # cache de stickers de casa (solo 5)
    "usar_gpu": True,             # True -> intenta h264_nvenc si hay GPU NVIDIA
    "ffmpeg_preset":"ultrafast",  # ultrafast/superfast/veryfast (CPU) — cuanto
                                    # más a la izquierda en esta lista, más rápido
                                    # y más pesa el archivo resultante
    "crf": 23,                      # calidad libx264 (18=alta calidad/pesado,
                                    # 28=más compresión/ligero). 23 es buen punto medio
    "threads": 0                   # 0 = ffmpeg usa todos los cores disponibles
}
 

# ==============================================================================
# UTILIDADES DE IMAGEN (idénticas a la versión anterior)
# ==============================================================================
 
def cargar_fuente(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()
 
 
def cover_resize(img, target_w, target_h):
    img = img.convert("RGB")
    src_w, src_h = img.size
    src_ratio = src_w / src_h
    dst_ratio = target_w / target_h
    if src_ratio > dst_ratio:
        new_h = target_h
        new_w = int(new_h * src_ratio)
    else:
        new_w = target_w
        new_h = int(new_w / src_ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))
 
 
def contain_resize(img, target_w, target_h):
    img = img.convert("RGBA")
    img.thumbnail((target_w, target_h), Image.LANCZOS)
    return img
 
 
def dibujar_texto_envuelto(draw, texto, fuente, box_w, x, y, fill=(255, 255, 255, 255),
                            line_spacing=10, max_chars=28):
    lineas = textwrap.wrap(texto, width=max_chars)
    y_actual = y
    for linea in lineas:
        bbox = draw.textbbox((0, 0), linea, font=fuente)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x_linea = x + (box_w - w) / 2
        draw.text((x_linea, y_actual), linea, font=fuente, fill=fill)
        y_actual += h + line_spacing
    return y_actual - y
 
 
def barra_texto_inferior(size, texto, fuente_path, font_size=42, alto_barra_ratio=0.22,
                          bg_rgba=(0, 0, 0, 160)):
    w, h = size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    alto_barra = int(h * alto_barra_ratio)
    draw.rectangle([0, h - alto_barra, w, h], fill=bg_rgba)
    fuente = cargar_fuente(fuente_path, font_size)
    dibujar_texto_envuelto(draw, texto, fuente, box_w=w, x=0,
                            y=h - alto_barra + int(alto_barra * 0.18),
                            fill=(255, 255, 255, 255), max_chars=30)
    return overlay
 
 
# ==============================================================================
# GENERACIÓN DE LOS 5 FRAMES ESTÁTICOS (izquierda + 4 bloques derecha)
# ==============================================================================
 
def frame_izquierda(cfg, w, h):
    img = Image.open(cfg["polaroid_path"])
    return cover_resize(img, w, h).convert("RGBA")
 
 
def frame_landmarks(cfg, w, h):
    base = Image.open(cfg["landmarks_path"])
    base = cover_resize(base, w, h).convert("RGBA")
    base.alpha_composite(barra_texto_inferior((w, h), cfg["texto_landmarks"], cfg["fuente_bold"]))
    return base
 
 
def frame_artistas(cfg, w, h):
    artistas = cfg["artistas"]
    base = Image.new("RGBA", (w, h), (15, 15, 15, 255))
    if not artistas:
        return base
    principal = artistas[0]
    secundarios = artistas[1:3]
    if secundarios:
        w_principal = int(w * 0.62)
        img_p = cover_resize(Image.open(principal["image"]), w_principal, h)
        base.paste(img_p, (0, 0))
        w_thumb = w - w_principal
        h_thumb = h // max(len(secundarios), 1)
        y_off = 0
        for art in secundarios:
            img_s = cover_resize(Image.open(art["image"]), w_thumb, h_thumb)
            base.paste(img_s, (w_principal, y_off))
            y_off += h_thumb
    else:
        base.paste(cover_resize(Image.open(principal["image"]), w, h), (0, 0))
    texto = cfg.get("texto_artista", f'{principal["name"]} ({principal["confidence"]}%)')
    base.alpha_composite(barra_texto_inferior((w, h), texto, cfg["fuente_bold"], alto_barra_ratio=0.26))
    return base
 
 
def _casa_cache_key(cfg, w, h):
    raw = f'{cfg["casa_sticker_path"]}|{cfg["casa_nombre"]}|{w}x{h}'
    return hashlib.md5(raw.encode()).hexdigest()
 
 
def frame_casa(cfg, w, h):
    """Este frame se cachea en disco: solo hay 5 casas posibles, así que tras
    la primera vez que se genera cada una, las siguientes veces es instantáneo."""
    os.makedirs(cfg["cache_dir"], exist_ok=True)
    cache_path = os.path.join(cfg["cache_dir"], f'casa_{_casa_cache_key(cfg, w, h)}.png')
    if os.path.exists(cache_path):
        return Image.open(cache_path)
 
    base = Image.new("RGBA", (w, h), (20, 20, 20, 255))
    sticker = contain_resize(Image.open(cfg["casa_sticker_path"]), int(w * 0.8), int(h * 0.7))
    px = (w - sticker.width) // 2
    py = (h - sticker.height) // 2 - int(h * 0.04)
    base.alpha_composite(sticker, (px, py))
    texto = f'{cfg["texto_casa_prefijo"]} {cfg["casa_nombre"]}'
    base.alpha_composite(barra_texto_inferior((w, h), texto, cfg["fuente_bold"], alto_barra_ratio=0.20))
    base.convert("RGB").save(cache_path)
    return base
 
 
def frame_musica(cfg, w, h):
    base = Image.new("RGBA", (w, h), (10, 10, 10, 255))
    draw = ImageDraw.Draw(base)
    fuente = cargar_fuente(cfg["fuente_bold"], 50)
    # calculamos alto para centrar
    tmp = Image.new("RGBA", (w, h))
    tmp_draw = ImageDraw.Draw(tmp)
    lineas_h = dibujar_texto_envuelto(tmp_draw, cfg["texto_musica"], fuente, box_w=w, x=0, y=0, max_chars=22)
    y_start = (h - lineas_h) / 2
    dibujar_texto_envuelto(draw, cfg["texto_musica"], fuente, box_w=w, x=0, y=y_start, max_chars=22)
    return base
 
 
# ==============================================================================
# MONTAJE CON FFMPEG (filtro xfade nativo, un único proceso)
# ==============================================================================
 
def detectar_encoder(cfg):
    """Si usar_gpu=True, comprueba que h264_nvenc esté realmente disponible
    (binario compilado con soporte Y GPU NVIDIA presente); si no, usa CPU."""
    if not cfg["usar_gpu"]:
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
    print("[!] GPU NVENC no disponible, usando CPU (libx264).")
    return "libx264", ["-preset", cfg["ffmpeg_preset"], "-crf", str(cfg["crf"])]
 
 
def generar_video(cfg=CONFIG):
    t0 = time.time()
    ancho_total, alto_total = cfg["resolucion"]
    w_mitad = ancho_total // 2
    h = alto_total
    fps = cfg["fps"]
    dur = cfg["duracion_bloque"]
    trans = cfg["duracion_transicion"]
 
    workdir = "/tmp/festival_render"
    os.makedirs(workdir, exist_ok=True)
 
    # ---- 1) Renderizar las 5 imágenes estáticas (Python/PIL, muy rápido) ----
    print("-> Renderizando imágenes base (PIL)...")
    frame_izquierda(cfg, w_mitad, h).convert("RGB").save(f"{workdir}/left.png")
    frame_landmarks(cfg, w_mitad, h).convert("RGB").save(f"{workdir}/b0.png")
    frame_artistas(cfg, w_mitad, h).convert("RGB").save(f"{workdir}/b1.png")
    frame_casa(cfg, w_mitad, h).convert("RGB").save(f"{workdir}/b2.png")
    frame_musica(cfg, w_mitad, h).convert("RGB").save(f"{workdir}/b3.png")
    t1 = time.time()
    print(f"   ({t1 - t0:.2f}s)")
 
    # ---- 2) Un único comando ffmpeg: loop de imágenes + xfade + hstack + audio ----
    # Duraciones de cada bloque de entrada (mismo esquema que produce 20s exactos
    # con 3 transiciones de `trans` segundos): d0=dur, d1..d3=dur+trans
    d0 = dur
    d1 = d2 = d3 = dur + trans
    duracion_total = d0 + d1 + d2 + d3 - 3 * trans   # = 20s con los valores por defecto
 
    off1 = d0 - trans
    off2 = (d0 + d1 - trans) - trans
    off3 = (d0 + d1 + d2 - 2 * trans) - trans
 
    encoder, encoder_flags = detectar_encoder(cfg)
 
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-framerate", str(fps), "-t", str(d0), "-i", f"{workdir}/b0.png",
        "-loop", "1", "-framerate", str(fps), "-t", str(d1), "-i", f"{workdir}/b1.png",
        "-loop", "1", "-framerate", str(fps), "-t", str(d2), "-i", f"{workdir}/b2.png",
        "-loop", "1", "-framerate", str(fps), "-t", str(d3), "-i", f"{workdir}/b3.png",
        "-loop", "1", "-framerate", str(fps), "-t", str(duracion_total), "-i", f"{workdir}/left.png",
        "-stream_loop", "-1", "-i", cfg["music_path"],
    ]
 
    filter_complex = (
        f"[0:v]format=yuv420p[b0];"
        f"[1:v]format=yuv420p[b1];"
        f"[2:v]format=yuv420p[b2];"
        f"[3:v]format=yuv420p[b3];"
        f"[b0][b1]xfade=transition=fade:duration={trans}:offset={off1}[x1];"
        f"[x1][b2]xfade=transition=fade:duration={trans}:offset={off2}[x2];"
        f"[x2][b3]xfade=transition=fade:duration={trans}:offset={off3}[right];"
        f"[4:v]format=yuv420p[left];"
        f"[left][right]hstack=inputs=2[video]"
    )
 
    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[video]",
        "-map", "5:a",
        "-t", str(duracion_total),
        "-c:v", encoder, *encoder_flags,
        "-c:a", "aac", "-b:a", "192k",
        "-threads", str(cfg["threads"]),
        "-movflags", "+faststart",
        cfg["output_path"],
    ]
 
    os.makedirs(os.path.dirname(cfg["output_path"]), exist_ok=True)
    print("-> Renderizando vídeo final (ffmpeg, un solo proceso)...")
    resultado = subprocess.run(cmd, capture_output=True, text=True)
    t2 = time.time()
 
    if resultado.returncode != 0:
        print("ERROR en ffmpeg:")
        print(resultado.stderr[-3000:])
        raise RuntimeError("ffmpeg falló, revisa el log de arriba")
 
    print(f"   ({t2 - t1:.2f}s)")
    print(f"Listo en {t2 - t0:.2f}s totales -> {cfg['output_path']}")
    return cfg["output_path"]
 
 
if __name__ == "__main__":
    generar_video(CONFIG)
