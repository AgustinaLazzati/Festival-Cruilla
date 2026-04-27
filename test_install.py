#!/usr/bin/env python3
"""
Script para verificar la instalación de Tal Cara, Tal Beat
"""

import sys
import os
import subprocess
from pathlib import Path

def print_header():
    print("\n🎵 Tal Cara, Tal Beat - Test de Instalación")
    print("=" * 50)
    print()

def check_python():
    """Verifica versión de Python"""
    print("✓ Test 1: Verificando Python...")
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"  ✅ Python {version}")
    return True

def check_streamlit():
    """Verifica que Streamlit esté instalado"""
    print("\n✓ Test 2: Verificando Streamlit...")
    try:
        import streamlit
        print(f"  ✅ Streamlit {streamlit.__version__} instalado")
        return True
    except ImportError:
        print("  ⚠️ Streamlit NO instalado")
        print("  Instalando Streamlit...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "streamlit", "-q"])
            import streamlit
            print(f"  ✅ Streamlit {streamlit.__version__} instalado correctamente")
            return True
        except:
            print("  ❌ Error al instalar Streamlit")
            return False

def check_files():
    """Verifica que los archivos existan"""
    print("\n✓ Test 3: Verificando archivos...")
    
    files_to_check = [
        "ui/config.json",
        "ui/streamlit_app.py",
        "api/music_generator.py",
    ]
    
    all_ok = True
    for file_path in files_to_check:
        if os.path.exists(file_path):
            print(f"  ✅ {file_path} encontrado")
        else:
            print(f"  ❌ {file_path} NO encontrado")
            all_ok = False
    
    return all_ok

def check_models():
    """Verifica disponibilidad de modelos"""
    print("\n✓ Test 4: Verificando modelos...")
    
    if os.path.exists("models/models/ACE-Step-1.5"):
        print("  ✅ ACE-Step v1.5 encontrado")
        return True
    else:
        print("  ⚠️ ACE-Step NO encontrado (se necesita para generar música)")
        return False

def check_json_config():
    """Verifica que config.json sea válido"""
    print("\n✓ Test 5: Verificando JSON config...")
    try:
        import json
        with open("ui/config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        
        questions = len(config.get("onboarding_questions", []))
        tribes = len(config.get("tribes", {}))
        
        print(f"  ✅ Config válido ({questions} preguntas, {tribes} tribus)")
        return True
    except Exception as e:
        print(f"  ❌ Error en config.json: {e}")
        return False

def main():
    os.chdir(Path(__file__).parent)
    
    print_header()
    
    results = {
        "Python": check_python(),
        "Streamlit": check_streamlit(),
        "Archivos": check_files(),
        "Modelos": check_models(),
        "Config JSON": check_json_config(),
    }
    
    print("\n" + "=" * 50)
    
    if all(results.values()):
        print("✅ Todos los tests pasaron correctamente")
        print("\n🚀 Ahora ejecuta:")
        print("   streamlit run ui/streamlit_app.py")
        print("\n📱 Se abrirá en: http://localhost:8501")
    else:
        failed = [name for name, result in results.items() if not result]
        print(f"⚠️ Algunos tests fallaron: {', '.join(failed)}")
        print("\nFix: Revisa los errores arriba")
        return 1
    
    print()
    return 0

if __name__ == "__main__":
    sys.exit(main())
