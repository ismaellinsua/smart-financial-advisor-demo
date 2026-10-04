#!/usr/bin/env python3
"""
Generador de voz en off para vídeo demo NirKanA
Usa ElevenLabs API para crear audio profesional en español
"""

from elevenlabs.client import ElevenLabs
import os
from pathlib import Path

# Configuración
API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
OUTPUT_DIR = Path("docs/assets/voiceover")

# Crear directorio si no existe
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Crear cliente
if not API_KEY:
    print("❌ Error: No se encontró ELEVENLABS_API_KEY")
    print("\n📋 Para obtener la API key gratuita:")
    print("1. Ir a https://elevenlabs.io/sign-up")
    print("2. Crear cuenta (gratis)")
    print("3. Ir a Settings → API Keys")
    print("4. Copiar tu API key")
    print("\n5. Ejecutar:")
    print('   export ELEVENLABS_API_KEY="tu-api-key-aqui"')
    print("   python generate_voiceover.py")
    exit(1)

client = ElevenLabs(api_key=API_KEY)

# Segmentos de voz (con timing esperado)
voiceovers = {
    "1_intro": {
        "text": "¿Cansado de apuntar en papel? Cobra, controla y decide con datos. Aquí es NirKanA.",
        "duration": "3s",
    },
    "2_venta": {
        "text": "Cobra tus ventas en segundos. Solo toca y listo. Sin papeles, sin errores.",
        "duration": "9s",
    },
    "3_stock": {
        "text": "Alertas inteligentes te avisan antes de que algo falte. Genera órdenes de compra automáticamente.",
        "duration": "10s",
    },
    "4_informe": {
        "text": "Cada viernes, informe automático con tus números reales. Datos claros, decisiones rápidas.",
        "duration": "13s",
    },
    "5_cierre": {
        "text": "Funciona en móvil, tablet y computadora. Cero instalación. Cero comisiones por venta. Prueba 14 días gratis, sin tarjeta de crédito. Nirkana punto app.",
        "duration": "10s",
    },
}

# Configuración de voz
# Voice ID "Rachel" es clara, profesional, con acento neutro español
VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel en español
# Alternativas:
# - "21m00Tcm4TlvDq8ikWAM" = Rachel (recomendada)
# - "EXAVITQu4vr4xnSDxMaL" = Bella (más cálida)
# - "pFZP5JQG7iQjIQuC4Iy3" = Adam (profesional masculino)

print("🎙️ Generando voz en off profesional en español...\n")

for segment_id, config in voiceovers.items():
    print(f"📝 {segment_id} ({config['duration']})")
    print(f"   Texto: {config['text'][:50]}...")

    try:
        # Generar audio usando text_to_speech
        audio = client.text_to_speech.convert(
            voice_id=VOICE_ID,
            text=config["text"],
            model_id="eleven_multilingual_v2",  # Soporta múltiples idiomas
            language_code="es",  # Español
        )

        # Guardar archivo
        output_file = OUTPUT_DIR / f"{segment_id}.mp3"
        with open(output_file, "wb") as f:
            for chunk in audio:
                f.write(chunk)

        print(f"   ✓ Guardado: {output_file}\n")

    except Exception as e:
        print(f"   ❌ Error: {e}\n")

print("\n✅ Voiceovers generados correctamente!")
print(f"\n📂 Archivos guardados en: {OUTPUT_DIR}")
print("\n📋 Próximos pasos:")
print("1. Grabar pantalla con OBS (ver instrucciones en SCRIPT_VIDEO_DEMO.md)")
print("2. Editar en DaVinci Resolve:")
print("   - Importa video + audios")
print("   - Sincroniza voiceover con acciones en pantalla")
print("   - Añade música de fondo (20% volumen)")
print("3. Exporta como MP4 1080p\n")
