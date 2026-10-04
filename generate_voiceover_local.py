#!/usr/bin/env python3
"""
Generador local de voz en off para vídeo demo NirKanA
Usa espeak-ng + ffmpeg (sin API keys, cero coste)
"""

import subprocess
import os
from pathlib import Path

OUTPUT_DIR = Path("docs/assets/voiceover")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Segmentos de voz
voiceovers = {
    "1_intro": {
        "text": "¿Cansado de apuntar en papel? Cobra, controla y decide con datos. Aquí es NirKanA.",
        "duration": "3s",
        "rate": 140,  # palabras por minuto
    },
    "2_venta": {
        "text": "Cobra tus ventas en segundos. Solo toca y listo. Sin papeles, sin errores.",
        "duration": "9s",
        "rate": 140,
    },
    "3_stock": {
        "text": "Alertas inteligentes te avisan antes de que algo falte. Genera órdenes de compra automáticamente.",
        "duration": "10s",
        "rate": 130,
    },
    "4_informe": {
        "text": "Cada viernes, informe automático con tus números reales. Datos claros, decisiones rápidas.",
        "duration": "13s",
        "rate": 130,
    },
    "5_cierre": {
        "text": "Funciona en móvil, tablet y computadora. Cero instalación. Cero comisiones por venta. Prueba 14 días gratis, sin tarjeta de crédito. Nirkana punto app.",
        "duration": "10s",
        "rate": 145,
    },
}

print("🎙️ Generando voiceovers locales con espeak-ng...\n")

for segment_id, config in voiceovers.items():
    print(f"📝 {segment_id} ({config['duration']})")
    print(f"   Texto: {config['text'][:50]}...")

    try:
        # Archivo temporal WAV
        wav_file = OUTPUT_DIR / f"{segment_id}.wav"
        mp3_file = OUTPUT_DIR / f"{segment_id}.mp3"

        # Generar WAV con espeak-ng (voz española)
        cmd_espeak = [
            "espeak-ng",
            "-v", "es",  # Español
            "-s", str(config["rate"]),  # Velocidad (palabras/min)
            "-w", str(wav_file),  # Output WAV
            config["text"],
        ]

        result = subprocess.run(cmd_espeak, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"   ❌ Error espeak: {result.stderr}")
            continue

        # Convertir a MP3 con ffmpeg (mejor calidad, comprimido)
        cmd_ffmpeg = [
            "ffmpeg",
            "-i", str(wav_file),
            "-codec:a", "libmp3lame",
            "-q:a", "4",  # Buena calidad (0-9, menor = mejor)
            "-y",  # Sobreescribir
            str(mp3_file),
        ]

        result = subprocess.run(cmd_ffmpeg, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"   ❌ Error ffmpeg: {result.stderr}")
            continue

        # Eliminar WAV temporal
        wav_file.unlink()

        # Obtener duración real del MP3
        cmd_duration = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1:0",
            str(mp3_file),
        ]
        duration_result = subprocess.run(cmd_duration, capture_output=True, text=True)
        duration = float(duration_result.stdout.strip()) if duration_result.returncode == 0 else 0

        print(f"   ✓ Guardado: {mp3_file} ({duration:.1f}s)\n")

    except Exception as e:
        print(f"   ❌ Error: {e}\n")

print("\n✅ Voiceovers generados correctamente!\n")
print(f"📂 Archivos en: {OUTPUT_DIR}")
print(f"📋 Total: 5 segmentos MP3 listos para editar")
print("\n🎬 Próximos pasos:")
print("1. Grabar pantalla con OBS (30 min)")
print("2. Editar en DaVinci Resolve:")
print("   - Importa video + estos 5 audios MP3")
print("   - Sincroniza timing con acciones")
print("   - Añade música de fondo (20% volumen)")
print("3. Exporta como MP4 1080p")
print("\n⏱️ Tiempo total: ~2 horas")
