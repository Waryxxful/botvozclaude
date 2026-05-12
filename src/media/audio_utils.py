"""Utilidades de conversión de formatos de audio para el pipeline de voz."""
import struct
import numpy as np

PSTN_SAMPLE_RATE = 8000    # Hz — PSTN / Telnyx mulaw
STT_SAMPLE_RATE = 16000    # Hz — Google STT / Deepgram
TTS_SAMPLE_RATE = 24000    # Hz — Google TTS output


def _resample(pcm_bytes: bytes, in_rate: int, out_rate: int) -> bytes:
    """Linear-interpolation resampler (mono PCM16)."""
    if in_rate == out_rate:
        return pcm_bytes
    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
    n_out = int(len(samples) * out_rate / in_rate)
    x_in = np.linspace(0, 1, len(samples), endpoint=False)
    x_out = np.linspace(0, 1, n_out, endpoint=False)
    return np.interp(x_out, x_in, samples).clip(-32768, 32767).astype(np.int16).tobytes()


def _ulaw2lin(ulaw_bytes: bytes) -> bytes:
    """μ-law → PCM16 (pure numpy, replaces audioop.ulaw2lin)."""
    s = np.frombuffer(ulaw_bytes, dtype=np.uint8).astype(np.int32)
    s = ~s & 0xFF
    sign = np.where(s & 0x80, -1, 1)
    exp = (s >> 4) & 0x07
    mantissa = s & 0x0F
    linear = sign * (((mantissa + 16) << (exp + 3)) - 132)
    return np.clip(linear, -32768, 32767).astype(np.int16).tobytes()


def _lin2ulaw(pcm_bytes: bytes) -> bytes:
    """PCM16 → μ-law (pure numpy, replaces audioop.lin2ulaw)."""
    MU = 255.0
    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    sign = np.sign(samples)
    compressed = sign * np.log1p(MU * np.abs(samples)) / np.log1p(MU)
    ulaw = np.round(compressed * 127.5 + 127.5).clip(0, 255).astype(np.uint8)
    return (~ulaw & 0xFF).astype(np.uint8).tobytes()


def mulaw_to_pcm16(mulaw_bytes: bytes, source_rate: int = PSTN_SAMPLE_RATE) -> bytes:
    """Convierte audio μ-law (8kHz) a PCM 16-bit signed (16kHz)."""
    pcm_8k = _ulaw2lin(mulaw_bytes)
    return _resample(pcm_8k, source_rate, STT_SAMPLE_RATE)


def pcm16_to_mulaw(pcm_bytes: bytes, source_rate: int = TTS_SAMPLE_RATE, target_rate: int = PSTN_SAMPLE_RATE) -> bytes:
    """Convierte PCM 16-bit a μ-law (8kHz) para enviar a PSTN."""
    resampled = _resample(pcm_bytes, source_rate, target_rate)
    return _lin2ulaw(resampled)


def pcm16_to_float32(pcm_bytes: bytes) -> np.ndarray:
    """Convierte PCM 16-bit bytes a array float32 normalizado [-1.0, 1.0]."""
    samples = np.frombuffer(pcm_bytes, dtype=np.int16)
    return samples.astype(np.float32) / 32768.0


def float32_to_pcm16(audio: np.ndarray) -> bytes:
    """Convierte array float32 a PCM 16-bit bytes."""
    samples = (audio * 32767).clip(-32768, 32767).astype(np.int16)
    return samples.tobytes()


def chunk_audio(audio_bytes: bytes, chunk_size_ms: int = 20, sample_rate: int = STT_SAMPLE_RATE) -> list[bytes]:
    """Divide audio en chunks de duración fija (en milisegundos).

    Útil para enviar audio al STT en streaming con chunks de 20ms (WebRTC VAD requirement).
    """
    bytes_per_ms = (sample_rate * 2) // 1000  # 2 bytes por sample (16-bit)
    chunk_size = bytes_per_ms * chunk_size_ms
    return [audio_bytes[i:i + chunk_size] for i in range(0, len(audio_bytes), chunk_size)]


def get_audio_duration_ms(pcm_bytes: bytes, sample_rate: int = STT_SAMPLE_RATE) -> float:
    """Calcula la duración en ms de un buffer PCM 16-bit."""
    num_samples = len(pcm_bytes) // 2  # 2 bytes por sample
    return (num_samples / sample_rate) * 1000
