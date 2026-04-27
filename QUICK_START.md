# 🚀 Quick Start - Tal Cara, Tal Beat

## 1️⃣ VERIFICAR INSTALACIÓN

### Opción A: Comprobar Streamlit (1 comando)

```bash
python -c "import streamlit; print(f'✅ Streamlit {streamlit.__version__} OK')"
```

### Opción B: Instalar si falta

```bash
pip install streamlit
```

---

## 2️⃣ EJECUTAR LA APP

### Paso 1: Ir al directorio

```bash
cd /hhome/ps2g07/code/Festival-Cruilla
```

### Paso 2: Iniciar Streamlit

```bash
streamlit run ui/streamlit_app.py
```

### Paso 3: Abrir en navegador

La terminal te mostrará algo como:

```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
```

**Copia la URL `http://localhost:8501` y abre en navegador**

---

## 3️⃣ PROBAR FUNCIONALIDADES

### ✅ Paso 1: Preguntas Emoji
- Selecciona emojis gigantes
- Prueba los 3 selectores (Mood, Instrumento, Combustible)
- Verifica que se guardan las respuestas

### ✅ Paso 2: Cámara
- Haz clic en el botón de cámara
- Permite acceso a la cámara del dispositivo
- Captura una foto
- Puedes retomar si no te gusta

### ✅ Paso 3: Artista (simulado)
- Muestra un artista de prueba (Bad Bunny)
- Verifica confianza

### ✅ Paso 4: Música
- Haz clic en "Generar mi canción"
- Debería procesarse (verificar que ACE-Step funciona)
- Verifica el prompt generado
- Escucha el audio

### ✅ Paso 5: Tribu
- Muestra resumen con emojis
- Tribu según el género

### ✅ Paso 6: Descargar
- Botón para empezar de nuevo

---

## 🎥 CÓMO FUNCIONA LA CÁMARA

La cámara usa **Streamlit nativo** (`st.camera_input()`):

1. **Navegador da permiso**: Primera vez te pedirá acceso a cámara
2. **Captura en tiempo real**: Ves lo que captura
3. **Guardado**: Se guarda en `session_state` para usarla después

### ⚠️ Si la cámara NO funciona:

**Problema 1: Navegador bloqueado**
- Verifica que diste permisos a la cámara
- Recarga la página (F5)

**Problema 2: Sin cámara en dispositivo**
- Si es PC de escritorio sin cámara, no funcionará
- Para pantalla táctil en stand, debe tener cámara integrada

**Problema 3: HTTPS requerido en algunos casos**
- Si usas desde otra máquina en red, Streamlit puede requerir HTTPS
- Por ahora usa `http://localhost:8501` en la misma máquina

---

## 📝 TROUBLESHOOTING

### Error: `ModuleNotFoundError: No module named 'streamlit'`

```bash
pip install streamlit
```

### Error: `Port 8501 already in use`

Otro Streamlit está corriendo. Usa otro puerto:

```bash
streamlit run ui/streamlit_app.py --server.port 8502
```

### Error: `Cannot find module 'acestep'`

El generador de música necesita ACE-Step. Verifica que:

```bash
ls models/models/ACE-Step-1.5/
```

Si falta, necesitas descargar el modelo.

### Cámara pide permisos pero no funciona

Algunos navegadores/dispositivos requieren HTTPS. Por ahora:
- Usa `http://localhost:8501` (mismo dispositivo)
- NO intentes `http://192.168.x.x:8501` de otra máquina (puede necesitar HTTPS)

---

## 🎯 COMANDOS ÚTILES

### Ejecutar y abrir navegador automático

```bash
streamlit run ui/streamlit_app.py --logger.level=error
```

### Ver logs en detalle

```bash
streamlit run ui/streamlit_app.py --logger.level=debug
```

### Ejecutar con hot reload (cambios en vivo)

```bash
streamlit run ui/streamlit_app.py --client.showErrorDetails=false
```

### Optimizar para pantalla táctil

```bash
streamlit run ui/streamlit_app.py \
  --client.showErrorDetails=false \
  --logger.level=error \
  --theme.primaryColor=#FF6B6B
```

---

## ✨ SIGUIENTES PASOS

Después de confirmar que funciona:

1. **Probar integración de fotos** → Verificar que se guarden
2. **Probar generador de música** → Ver si ACE-Step funciona
3. **Integrar facial recognition** → Cuando tengas modelo listo
4. **Implementar QR** → Para descargas finales
5. **Optimizar para CPU** → Si es necesario

---

## 🆘 ¿PREGUNTAS?

Si algo no funciona:
1. Revisa que Streamlit está instalado
2. Verifica que estás en `/code/Festival-Cruilla`
3. Intenta con `streamlit run ui/streamlit_app.py --logger.level=debug`
4. Mira los errores en la terminal

