# 🎵 Tal Cara, Tal Beat - Interface Inicial

## Estructura de Archivos

```
Festival-Cruilla/
├── ui/
│   ├── config.json          # Configuración de preguntas y emojis
│   └── streamlit_app.py     # Aplicación principal Streamlit
├── api/
│   ├── __init__.py
│   └── music_generator.py   # Generador de música con respuestas del usuario
```

## Cómo ejecutar

### Opción 1: Instalar Streamlit (si no tienes)

```bash
pip install streamlit
```

### Opción 2: Ejecutar la app

```bash
cd Festival-Cruilla
streamlit run ui/streamlit_app.py
```

Abrirá la app en: `http://localhost:8501`

## Características Implementadas

✅ **Paso 1: Onboarding con 3 preguntas emoji**
- 🔥 Mood (4 opciones con emojis)
- 🎸 Instrumento (4 opciones con emojis)
- 🍻 Combustible/Género (4 opciones con emojis)

✅ **Integración con generador de música**
- Las respuestas se convierten a descripciones para la IA
- El prompt de música incluye todas las respuestas del usuario

✅ **Placeholder para futuros componentes**
- Paso 2: Captura de cámara (próximamente)
- Paso 3: Facial matching (próximamente)
- Paso 6: QR y descarga (próximamente)

## Mapeo de Emojis a Descripciones IA

### Mood 🎭

| Emoji | Descripción |
|-------|-----------|
| 🔥 | Tempo rápido, intenso, eufórico, banger |
| 🫠 | Tempo lento, relajado, acústico, chill |
| 👽 | Tempo medio-rápido, experimental, raro, psicodélico |
| 🤪 | Tempo muy rápido, caótico, divertido, ritmo saltarín |

### Instrumento 🎸

| Emoji | Descripción |
|-------|-----------|
| 🎸 | Guitarras eléctricas, bajo potente, estilo Rock/Indie |
| 🎛️ | Sintetizadores, caja de ritmos, estilo Techno/Electrónica |
| 🎷 | Vientos, línea de bajo cálida, estilo Funk/Soul/Groove |
| 🥁 | Beats urbanos, percusión pesada, estilo Hip-Hop/Reggaeton/Trap |

### Combustible 🍻

| Emoji | Descripción |
|-------|-----------|
| 🍻 | Sonido de estadio, himno de festival, coros grupales |
| 💧 | Sonido limpio, fresco, pop luminoso, melodía clara |
| 🍕 | Sonido pesado, fat bass, contundente, stoner rock o dubstep |
| 🍹 | Sonido tropical, ritmos latinos, percusión caribeña, reggae |

## Ejemplo de Prompt Generado

Si un usuario selecciona:
- Mood: 🔥 (energetic)
- Instrumento: 🎛️ (synth)
- Combustible: 🍹 (tropical)

El prompt para ACE-Step será:

```
Create an instrumental track in the style of Bad Bunny. Genre: reggaeton.

Mood characteristics: Tempo rápido, intenso, eufórico, banger.

Instrumentation: Sintetizadores, caja de ritmos, estilo Techno/Electrónica.

Overall vibe: Sonido tropical, ritmos latinos, percusión caribeña, reggae.

Festival atmosphere, perfect for celebration and dancing. Duration: 15-30 seconds.
```

## Próximos Pasos

1. Implementar captura de cámara (Paso 2) con `streamlit_webrtc`
2. Integrar modelo de reconocimiento facial (Paso 3)
3. Implementar sistema de QR y descarga (Paso 6)
4. Optimizar modelos para ejecución en CPU
5. Testing en pantalla táctil

## Requisitos

- Python 3.8+
- Streamlit
- ACE-Step (ya disponible en `/models/models/ACE-Step-1.5/`)
- PyTorch (con soporte CUDA o CPU)

## Notas

- La app está diseñada para pantallas táctiles (botones grandes, fuentes legibles)
- De momento, el facial matching es simulado con "Bad Bunny"
- Las fotos se guardarán en `/outputs/` una vez implementado el Paso 2
