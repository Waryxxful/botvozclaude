import pytest
from src.media.audio_utils import (
    mulaw_to_pcm16,
    chunk_audio,
    get_audio_duration_ms,
    STT_SAMPLE_RATE,
)


def test_mulaw_to_pcm16_returns_bytes():
    # 160 bytes de mulaw 8kHz = 20ms de audio
    mulaw_data = bytes(160)
    result = mulaw_to_pcm16(mulaw_data)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_chunk_audio_correct_count():
    # 1 segundo de PCM 16kHz = 32000 bytes, chunks de 20ms = 50 chunks
    pcm_1s = bytes(32000)
    chunks = chunk_audio(pcm_1s, chunk_size_ms=20, sample_rate=STT_SAMPLE_RATE)
    assert len(chunks) == 50


def test_get_audio_duration_ms():
    pcm_1s = bytes(32000)  # 1s a 16kHz 16-bit
    duration = get_audio_duration_ms(pcm_1s, STT_SAMPLE_RATE)
    assert abs(duration - 1000.0) < 1.0
