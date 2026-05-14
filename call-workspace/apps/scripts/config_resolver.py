from dataclasses import dataclass


@dataclass(frozen=True)
class ResolvedAgentConfig:
    tts_voice: str
    tts_speed: float
    tts_pitch: float
    llm_temperature: float
    llm_max_tokens: int
    vad_silence_ms: int
    max_call_duration_seconds: int


def resolve_agent_config(script) -> ResolvedAgentConfig:
    """Merge script config fields over global defaults. None fields fall back to global."""
    from .models import AgentGlobalConfig
    g = AgentGlobalConfig.get()
    return ResolvedAgentConfig(
        tts_voice=script.tts_voice or g.tts_voice,
        tts_speed=script.tts_speed if script.tts_speed is not None else g.tts_speed,
        tts_pitch=script.tts_pitch if script.tts_pitch is not None else g.tts_pitch,
        llm_temperature=script.llm_temperature if script.llm_temperature is not None else g.llm_temperature,
        llm_max_tokens=script.llm_max_tokens if script.llm_max_tokens is not None else g.llm_max_tokens,
        vad_silence_ms=script.vad_silence_ms if script.vad_silence_ms is not None else g.vad_silence_ms,
        max_call_duration_seconds=script.max_call_duration_seconds if script.max_call_duration_seconds is not None else g.max_call_duration_seconds,
    )
