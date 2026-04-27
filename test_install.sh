#!/bin/bash

# Script para probar la instalación de Tal Cara, Tal Beat

echo "🎵 Tal Cara, Tal Beat - Test de Instalación"
echo "==========================================="
echo ""

# Test 1: Python disponible
echo "✓ Test 1: Verificando Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "  ✅ $PYTHON_VERSION"
else
    echo "  ❌ Python no encontrado"
    exit 1
fi

echo ""

# Test 2: Streamlit instalado
echo "✓ Test 2: Verificando Streamlit..."
if python3 -c "import streamlit" 2>/dev/null; then
    STREAMLIT_VERSION=$(python3 -c "import streamlit; print(streamlit.__version__)")
    echo "  ✅ Streamlit $STREAMLIT_VERSION instalado"
else
    echo "  ⚠️ Streamlit NO instalado"
    echo "  Instalando Streamlit..."
    pip install streamlit
    if [ $? -eq 0 ]; then
        echo "  ✅ Streamlit instalado correctamente"
    else
        echo "  ❌ Error al instalar Streamlit"
        exit 1
    fi
fi

echo ""

# Test 3: Config.json existe
echo "✓ Test 3: Verificando archivos..."
if [ -f "ui/config.json" ]; then
    echo "  ✅ ui/config.json encontrado"
else
    echo "  ❌ ui/config.json no encontrado"
    exit 1
fi

if [ -f "ui/streamlit_app.py" ]; then
    echo "  ✅ ui/streamlit_app.py encontrado"
else
    echo "  ❌ ui/streamlit_app.py no encontrado"
    exit 1
fi

if [ -f "api/music_generator.py" ]; then
    echo "  ✅ api/music_generator.py encontrado"
else
    echo "  ❌ api/music_generator.py no encontrado"
    exit 1
fi

echo ""

# Test 4: ACE-Step disponible
echo "✓ Test 4: Verificando modelos ACE-Step..."
if [ -d "models/models/ACE-Step-1.5" ]; then
    echo "  ✅ ACE-Step encontrado"
else
    echo "  ⚠️ ACE-Step NO encontrado (se necesita para generar música)"
fi

echo ""
echo "==========================================="
echo "✅ Tests completados correctamente"
echo ""
echo "🚀 Ahora ejecuta:"
echo "   streamlit run ui/streamlit_app.py"
echo ""
