from pydantic import BaseModel, Field


class GuardrailConfig(BaseModel):
    forbidden_topics: list[str] = Field(default_factory=list)
    max_call_duration_seconds: int = Field(600)
    require_customer_identification: bool = Field(False)
    post_response_validation: bool = Field(True)


class MemoryConfig(BaseModel):
    max_history_turns: int = Field(20)
    include_customer_data: bool = Field(True)


class ToolsConfig(BaseModel):
    enabled: list[str] = Field(default_factory=list)


class BotProfileSchema(BaseModel):
    name: str
    description: str
    language: str = Field("es-419")
    tts_voice: str = Field("es-US-Neural2-A")
    system_prompt: str
    greeting: str
    farewell: str
    guardrails: GuardrailConfig = Field(default_factory=GuardrailConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
