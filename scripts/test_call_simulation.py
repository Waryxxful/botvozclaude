"""Script de simulación de llamada para pruebas locales.

Modos:
  --mode stt    → Transcribe un archivo WAV
  --mode tts    → Sintetiza texto a audio
  --mode llm    → Conversación multi-turno de texto sin audio
  --mode full   → Pipeline completo (requiere LiveKit local)
"""
import asyncio
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def test_stt(wav_path: str) -> None:
    from src.stt.google_stt import GoogleSTT

    print(f"[STT] Transcribiendo: {wav_path}")

    import soundfile as sf
    import numpy as np
    from src.media.audio_utils import float32_to_pcm16, STT_SAMPLE_RATE

    audio, sr = sf.read(wav_path, dtype="float32")
    if sr != STT_SAMPLE_RATE:
        print(f"  Advertencia: sample rate {sr}Hz, se esperaba {STT_SAMPLE_RATE}Hz")

    pcm = float32_to_pcm16(audio)

    async def audio_gen():
        yield pcm

    stt = GoogleSTT()
    async for text, is_final in stt.transcribe_stream(audio_gen()):
        marker = "[FINAL]" if is_final else "[interim]"
        print(f"  {marker} {text}")

    await stt.close()
    print("[STT] Listo.")


async def test_tts(text: str) -> None:
    from src.tts.google_tts import GoogleTTS

    print(f"[TTS] Sintetizando: \"{text}\"")
    tts = GoogleTTS()
    audio = await tts.synthesize(text)
    output_path = "scripts/output_tts.wav"

    import soundfile as sf
    import numpy as np
    samples = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
    sf.write(output_path, samples, 24000)
    print(f"[TTS] Audio guardado en {output_path} ({len(audio)} bytes)")
    await tts.close()


async def test_llm() -> None:
    from config.bot_config import get_default_profile
    from src.session.session_manager import create_session, close_session
    from src.llm.gemini_client import GeminiClient
    from src.persistence.models import TranscriptionRole

    print("[LLM] Iniciando conversación de prueba (escribe 'salir' para terminar)\n")

    session = create_session("test-call-001", "+5491112345678", "default")
    gemini = GeminiClient()

    while True:
        user_input = input("Usuario: ").strip()
        if user_input.lower() in ("salir", "exit", "quit"):
            break
        if not user_input:
            continue

        session.add_message(TranscriptionRole.USER, user_input)
        response, tool_calls = await gemini.generate_response(session, user_input)
        session.add_message(TranscriptionRole.ASSISTANT, response)

        print(f"Bot: {response}")
        if tool_calls:
            print(f"  → Tools ejecutadas: {[t['name'] for t in tool_calls]}")

    print("\n[LLM] Guardando sesión en Firestore...")
    await close_session("test-call-001")
    print("[LLM] Listo.")


def main():
    parser = argparse.ArgumentParser(description="Simulación de llamada Voice Bot")
    parser.add_argument("--mode", choices=["stt", "tts", "llm", "full"], required=True)
    parser.add_argument("--input", help="Archivo WAV de entrada (modo stt)")
    parser.add_argument("--text", help="Texto a sintetizar (modo tts)")
    parser.add_argument("--livekit-room", help="Room LiveKit (modo full)")
    args = parser.parse_args()

    if args.mode == "stt":
        if not args.input:
            print("Error: --input requerido para modo stt")
            sys.exit(1)
        asyncio.run(test_stt(args.input))

    elif args.mode == "tts":
        text = args.text or "Hola, ¿en qué le puedo ayudar hoy?"
        asyncio.run(test_tts(text))

    elif args.mode == "llm":
        asyncio.run(test_llm())

    elif args.mode == "full":
        print("[FULL] Modo full_pipeline requiere LiveKit local (docker-compose up livekit)")
        print("  Implementación completa disponible en Fase 4+")


if __name__ == "__main__":
    main()
