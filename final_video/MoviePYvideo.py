"""
================================================================================
 GENERADOR AUTOMÁTICO DE VÍDEO - Festival Cruïlla
================================================================================
Genera un vídeo horizontal de 20 segundos a partir de los outputs de los
modelos (imagen de landmarks, polaroid, artistas afines, casa asignada
y pista de música).

Estructura del vídeo:
  IZQUIERDA (0-20s, fija, sin transiciones): Polaroid
  DERECHA (con transiciones en crossfade entre bloques):
      0-5s   -> Imagen "landmarks"        + texto "Así es cómo la IA te interpreta"
      5-10s  -> Collage 3 artistas afines + texto con el artista principal
      10-15s -> Sticker de la casa        + texto con el nombre de la casa
      15-20s -> Pantalla final            + texto sobre la música/identidad
  Audio: la pista de música de fondo durante los 20s.

Requisitos:
    pip install moviepy pillow numpy --break-system-packages

Uso:
    python3 video.py
(edita el diccionario CONFIG más abajo con tus rutas reales, o impórtalo
 como módulo y llama a generar_video(config) con tu propio dict)
================================================================================
"""

import os
import textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from moviepy import (
    ImageClip,
    CompositeVideoClip,
    clips_array,
    concatenate_videoclips,
    AudioFileClip,
    afx,
)


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
    "output_path": "/home/spG07/code/Festival-Cruilla/final_video/resultadoMOVIEPY.mp4",

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
    "texto_musica": "La música que suena representa tu identidad"
    #falta lo del artista??
}


# ==============================================================================
# UTILIDADES DE IMAGEN (PIL) — no dependen de ImageMagick
# ==============================================================================

def cargar_fuente(path, size):
    """Carga una fuente TTF, con fallback a la fuente por defecto de PIL."""
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def cover_resize(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Redimensiona + recorta una imagen para que cubra exactamente target_w x target_h
    (comportamiento tipo CSS object-fit: cover), sin deformarla."""
    img = img.convert("RGB")
    src_w, src_h = img.size
    src_ratio = src_w / src_h
    dst_ratio = target_w / target_h

    if src_ratio > dst_ratio:
        # la fuente es más ancha -> ajustar por alto y recortar los lados
        new_h = target_h
        new_w = int(new_h * src_ratio)
    else:
        # la fuente es más alta -> ajustar por ancho y recortar arriba/abajo
        new_w = target_w
        new_h = int(new_w / src_ratio)

    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def contain_resize(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Redimensiona una imagen para que quepa entera dentro de target_w x target_h,
    manteniendo proporción (para stickers/logos, sin recortar)."""
    img = img.convert("RGBA")
    img.thumbnail((target_w, target_h), Image.LANCZOS)
    return img


def dibujar_texto_envuelto(draw, texto, fuente, box_w, x, y, fill=(255, 255, 255, 255),
                            align="center", line_spacing=10, max_chars=28):
    """Dibuja texto centrado envolviendo líneas, devuelve la altura total usada."""
    lineas = textwrap.wrap(texto, width=max_chars)
    y_actual = y
    for linea in lineas:
        bbox = draw.textbbox((0, 0), linea, font=fuente)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if align == "center":
            x_linea = x + (box_w - w) / 2
        else:
            x_linea = x
        draw.text((x_linea, y_actual), linea, font=fuente, fill=fill)
        y_actual += h + line_spacing
    return y_actual - y


def barra_texto_inferior(size, texto, fuente_path, font_size=42, alto_barra_ratio=0.22,
                          bg_rgba=(0, 0, 0, 160)):
    """Genera una imagen RGBA del tamaño `size` totalmente transparente salvo
    una barra semitransparente en la parte inferior con el texto centrado."""
    w, h = size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    alto_barra = int(h * alto_barra_ratio)
    draw.rectangle([0, h - alto_barra, w, h], fill=bg_rgba)

    fuente = cargar_fuente(fuente_path, font_size)
    dibujar_texto_envuelto(
        draw, texto, fuente, box_w=w, x=0,
        y=h - alto_barra + int(alto_barra * 0.18),
        fill=(255, 255, 255, 255), max_chars=30,
    )
    return overlay


def imagen_a_array(img: Image.Image):
    return np.array(img.convert("RGBA"))


# ==============================================================================
# CONSTRUCCIÓN DE LOS FRAMES (imágenes compuestas) DE CADA BLOQUE
# ==============================================================================

def frame_landmarks(cfg, w, h):
    """Bloque 1: imagen de landmarks + texto inferior."""
    base = Image.open(cfg["landmarks_path"])
    base = cover_resize(base, w, h).convert("RGBA")
    overlay = barra_texto_inferior((w, h), cfg["texto_landmarks"], cfg["fuente_bold"])
    base.alpha_composite(overlay)
    return base


def frame_artistas(cfg, w, h):
    """Bloque 2: collage con hasta 3 artistas (principal grande + 2 miniaturas)
    y texto con el nombre del artista principal."""
    artistas = cfg["artistas"]
    base = Image.new("RGBA", (w, h), (15, 15, 15, 255))

    if not artistas:
        return base

    principal = artistas[0]
    secundarios = artistas[1:3]  # hasta 2 más

    if secundarios:
        # Imagen principal ocupa 65% del ancho a la izquierda del bloque
        w_principal = int(w * 0.62)
        img_p = Image.open(principal["image"])
        img_p = cover_resize(img_p, w_principal, h)
        base.paste(img_p, (0, 0))

        # Miniaturas apiladas a la derecha
        w_thumb = w - w_principal
        h_thumb = h // max(len(secundarios), 1)
        y_off = 0
        for art in secundarios:
            img_s = Image.open(art["image"])
            img_s = cover_resize(img_s, w_thumb, h_thumb)
            base.paste(img_s, (w_principal, y_off))
            y_off += h_thumb
    else:
        img_p = Image.open(principal["image"])
        img_p = cover_resize(img_p, w, h)
        base.paste(img_p, (0, 0))

    texto = cfg.get("texto_artista", f'{principal["name"]} ({principal["confidence"]}%)')
    overlay = barra_texto_inferior((w, h), texto, cfg["fuente_bold"], alto_barra_ratio=0.26)
    base.alpha_composite(overlay)
    return base


def frame_casa(cfg, w, h):
    """Bloque 3: sticker de la casa centrado sobre fondo + texto con el nombre."""
    base = Image.new("RGBA", (w, h), (20, 20, 20, 255))
    sticker = Image.open(cfg["casa_sticker_path"])
    max_w, max_h = int(w * 0.8), int(h * 0.7)
    sticker = contain_resize(sticker, max_w, max_h)
    px = (w - sticker.width) // 2
    py = (h - sticker.height) // 2 - int(h * 0.04)
    base.alpha_composite(sticker, (px, py))

    texto = f'{cfg["texto_casa_prefijo"]} {cfg["casa_nombre"]}'
    overlay = barra_texto_inferior((w, h), texto, cfg["fuente_bold"], alto_barra_ratio=0.20)
    base.alpha_composite(overlay)
    return base


def frame_musica(cfg, w, h):
    """Bloque 4: pantalla final, solo texto sobre fondo oscuro (identidad musical)."""
    base = Image.new("RGBA", (w, h), (10, 10, 10, 255))
    draw = ImageDraw.Draw(base)
    fuente = cargar_fuente(cfg["fuente_bold"], 50)
    lineas_h = dibujar_texto_envuelto(
        draw, cfg["texto_musica"], fuente, box_w=w, x=0, y=0, max_chars=22,
    )
    # centrar verticalmente: recalculamos dibujando de nuevo con el offset correcto
    base = Image.new("RGBA", (w, h), (10, 10, 10, 255))
    draw = ImageDraw.Draw(base)
    y_start = (h - lineas_h) / 2
    dibujar_texto_envuelto(
        draw, cfg["texto_musica"], fuente, box_w=w, x=0, y=y_start, max_chars=22,
    )
    return base


# ==============================================================================
# CONSTRUCCIÓN DEL VÍDEO CON MOVIEPY
# ==============================================================================

def construir_columna_derecha(cfg, w, h):
    """Construye los 4 bloques de la derecha con transición crossfade entre ellos."""
    dur = cfg["duracion_bloque"]
    trans = cfg["duracion_transicion"]
    fps = cfg["fps"]

    generadores = [frame_landmarks, frame_artistas, frame_casa, frame_musica]
    clips = []
    for i, gen in enumerate(generadores):
        frame_img = gen(cfg, w, h)
        clip = ImageClip(imagen_a_array(frame_img)).with_duration(dur + (trans if i > 0 else 0))
        if i > 0:
            clip = clip.with_effects([__import__("moviepy").vfx.CrossFadeIn(trans)])
        clips.append(clip)

    # concatenate_videoclips con padding negativo solapa el crossfade con el clip anterior
    derecha = concatenate_videoclips(clips, method="compose", padding=-trans)
    derecha = derecha.with_fps(fps)
    return derecha


def construir_columna_izquierda(cfg, w, h):
    """Polaroid estática durante toda la duración del vídeo, sin transiciones."""
    img = Image.open(cfg["polaroid_path"])
    img = cover_resize(img, w, h)
    clip = ImageClip(imagen_a_array(img.convert("RGBA"))).with_duration(cfg["duracion_total"])
    return clip


def generar_video(cfg=CONFIG):
    ancho_total, alto_total = cfg["resolucion"]
    w_mitad = ancho_total // 2
    h_total = alto_total

    print("-> Construyendo columna izquierda (polaroid)...")
    izquierda = construir_columna_izquierda(cfg, w_mitad, h_total)

    print("-> Construyendo columna derecha (bloques con transición)...")
    derecha = construir_columna_derecha(cfg, w_mitad, h_total)

    # Aseguramos que ambas duren exactamente lo mismo (recorte de seguridad)
    duracion = cfg["duracion_total"]
    izquierda = izquierda.with_duration(duracion)
    derecha = derecha.with_duration(duracion)

    print("-> Componiendo vídeo final (izquierda + derecha)...")
    video_final = clips_array([[izquierda, derecha]]).with_fps(cfg["fps"])

    print("-> Añadiendo audio de música...")
    audio = AudioFileClip(cfg["music_path"])
    if audio.duration < duracion:
        # si la pista es más corta que el vídeo, la repetimos en bucle
        audio = audio.with_effects([afx.AudioLoop(duration=duracion)])
    else:
        audio = audio.subclipped(0, duracion)
    video_final = video_final.with_audio(audio)

    os.makedirs(os.path.dirname(cfg["output_path"]), exist_ok=True)
    print(f"-> Renderizando a {cfg['output_path']} ...")
    video_final.write_videofile(
        cfg["output_path"],
        fps=cfg["fps"],
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="medium",
    )
    print("Listo!")


if __name__ == "__main__":
    generar_video(CONFIG)