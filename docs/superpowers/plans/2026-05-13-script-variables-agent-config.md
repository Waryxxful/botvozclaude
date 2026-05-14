# Script Variables en Saludo + Configuración del Agente — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Soportar `{{variables}}` en el saludo del script y agregar configuración por script (voz, velocidad, temperatura, etc.) con defaults globales.

**Architecture:** Se extiende el modelo `Script` con campos de configuración opcionales y un nuevo modelo singleton `AgentGlobalConfig` para los defaults. Un `config_resolver` hace el merge en runtime. El parser se actualiza para extraer variables tanto del greeting como del prompt.

**Tech Stack:** Django 6, Django Channels (consumers.py), Google TTS, Gemini Vertex AI, Bootstrap 5 tabs

---

## File Map

| Archivo | Acción |
|---|---|
| `call-workspace/apps/scripts/parsers.py` | Modificar — `parse_template()` acepta `greeting` como segundo param |
| `call-workspace/apps/scripts/models.py` | Modificar — agregar campos de config a `Script` + nuevo modelo `AgentGlobalConfig` |
| `call-workspace/apps/scripts/migrations/` | Crear — nueva migración |
| `call-workspace/apps/scripts/config_resolver.py` | Crear — `resolve_agent_config(script)` |
| `call-workspace/apps/scripts/forms.py` | Modificar — `ScriptForm` incluye campos de config |
| `call-workspace/apps/scripts/views.py` | Modificar — agregar `global_config_view` |
| `call-workspace/apps/scripts/urls.py` | Modificar — agregar ruta `/settings/agente/` |
| `call-workspace/templates/scripts/form.html` | Modificar — 3 pestañas Bootstrap |
| `call-workspace/templates/scripts/global_config.html` | Crear — página de settings globales |
| `call-workspace/templates/calls/bot_test.html` | Modificar — formulario de test_values + envío al WS |
| `call-workspace/templates/base.html` | Modificar — link "Configuración" en sidebar |
| `call-workspace/apps/calls/consumers.py` | Modificar — test_values + resolved config + render greeting |
| `src/tts/google_tts.py` | Modificar — params `speed` y `pitch` en `synthesize()` |
| `src/llm/gemini_client.py` | Modificar — params `temperature` y `max_tokens` en `generate_streaming()` |
| `call-workspace/tests/scripts/test_parsers.py` | Crear — tests del parser actualizado |
| `call-workspace/tests/scripts/test_config_resolver.py` | Crear — tests del resolver |

---

### Task 1: Actualizar el parser para variables en greeting

**Files:**
- Modify: `call-workspace/apps/scripts/parsers.py`
- Create: `call-workspace/tests/scripts/test_parsers.py`

- [ ] **Step 1: Crear el archivo de tests**

```python
# call-workspace/tests/scripts/test_parsers.py
import pytest
from apps.scripts.parsers import parse_template, render_template


def test_parse_prompt_only():
    result = parse_template("Llama a {{nombre}} sobre {{fecha}}", "")
    assert result.input_params == ["nombre", "fecha"]
    assert result.output_params == []


def test_parse_greeting_only():
    result = parse_template("", "Hola {{nombre}} desde {{concesionaria}}")
    assert result.input_params == ["nombre", "concesionaria"]


def test_parse_combined_deduplicates():
    result = parse_template(
        prompt="Confirmar con {{nombre}} para {{fecha}} [[confirmacion]]",
        greeting="Hola {{nombre}} desde {{concesionaria}}",
    )
    assert result.input_params == ["nombre", "concesionaria", "fecha"]
    assert result.output_params == ["confirmacion"]


def test_parse_greeting_first_in_order():
    # Variables del greeting aparecen antes en input_params
    result = parse_template(
        prompt="Fecha: {{fecha}}",
        greeting="Hola {{nombre}}",
    )
    assert result.input_params == ["nombre", "fecha"]


def test_render_template_with_greeting_vars():
    rendered = render_template("Hola {{nombre}} de {{empresa}}", {"nombre": "Juan", "empresa": "Chery"})
    assert rendered == "Hola Juan de Chery"


def test_render_template_missing_value_raises():
    with pytest.raises(KeyError, match="empresa"):
        render_template("Hola {{nombre}} de {{empresa}}", {"nombre": "Juan"})
```

- [ ] **Step 2: Verificar que los tests fallan**

```bash
cd call-workspace
py -3.13 -m pytest tests/scripts/test_parsers.py -v
```
Esperado: `FAILED` — `parse_template() takes 1 positional argument but 2 were given`

- [ ] **Step 3: Actualizar `parse_template()` para aceptar `greeting`**

```python
# call-workspace/apps/scripts/parsers.py
def parse_template(prompt: str, greeting: str = "") -> ParsedTemplate:
    """Extract {{input}} and [[output]] params from greeting + prompt combined.

    Greeting variables appear first in input_params. Outputs only from prompt.
    """
    combined_inputs = _unique_in_order(
        INPUT_PATTERN.findall(greeting) + INPUT_PATTERN.findall(prompt)
    )
    return ParsedTemplate(
        input_params=combined_inputs,
        output_params=_unique_in_order(OUTPUT_PATTERN.findall(prompt)),
    )
```

- [ ] **Step 4: Actualizar `Script.save()` para pasar el greeting al parser**

En `call-workspace/apps/scripts/models.py`, cambiar el método `save()`:

```python
def save(self, *args, **kwargs):
    parsed = parse_template(self.prompt_template, self.greeting)
    self.input_params = parsed.input_params
    self.output_params = parsed.output_params
    super().save(*args, **kwargs)
```

- [ ] **Step 5: Correr los tests**

```bash
cd call-workspace
py -3.13 -m pytest tests/scripts/test_parsers.py -v
```
Esperado: todos `PASSED`

- [ ] **Step 6: Commit**

```bash
git add call-workspace/apps/scripts/parsers.py call-workspace/apps/scripts/models.py call-workspace/tests/scripts/test_parsers.py
git commit -m "feat(scripts): parse {{variables}} from greeting + prompt combined"
```

---

### Task 2: Campos de configuración en `Script` + modelo `AgentGlobalConfig`

**Files:**
- Modify: `call-workspace/apps/scripts/models.py`
- Create: `call-workspace/apps/scripts/migrations/000X_script_config_fields.py` (auto-generada)

- [ ] **Step 1: Agregar choices de voces y campos al modelo `Script`**

```python
# call-workspace/apps/scripts/models.py
from django.db import models
from .parsers import parse_template

TTS_VOICE_CHOICES = [
    ("es-US-Neural2-A", "Mujer — Natural (es-US-Neural2-A)"),
    ("es-US-Neural2-C", "Mujer — Formal (es-US-Neural2-C)"),
    ("es-US-Neural2-B", "Hombre — Natural (es-US-Neural2-B)"),
    ("es-US-Neural2-D", "Hombre — Formal (es-US-Neural2-D)"),
]


class AgentGlobalConfig(models.Model):
    """Singleton con valores por defecto para todos los scripts."""
    tts_voice = models.CharField(max_length=50, choices=TTS_VOICE_CHOICES, default="es-US-Neural2-A")
    tts_speed = models.FloatField(default=1.0)
    tts_pitch = models.FloatField(default=0.0)
    llm_temperature = models.FloatField(default=0.5)
    llm_max_tokens = models.IntegerField(default=300)
    vad_silence_ms = models.IntegerField(default=900)
    max_call_duration_seconds = models.IntegerField(default=600)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración global del agente"

    @classmethod
    def get(cls) -> "AgentGlobalConfig":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Script(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, default="")
    prompt_template = models.TextField()
    greeting = models.CharField(max_length=500)
    input_params = models.JSONField(default=list, blank=True)
    output_params = models.JSONField(default=list, blank=True)
    # Configuración de voz (null = usa el global)
    tts_voice = models.CharField(max_length=50, choices=TTS_VOICE_CHOICES, null=True, blank=True)
    tts_speed = models.FloatField(null=True, blank=True)
    tts_pitch = models.FloatField(null=True, blank=True)
    # Configuración del LLM
    llm_temperature = models.FloatField(null=True, blank=True)
    llm_max_tokens = models.IntegerField(null=True, blank=True)
    # Configuración de conversación
    vad_silence_ms = models.IntegerField(null=True, blank=True)
    max_call_duration_seconds = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        parsed = parse_template(self.prompt_template, self.greeting)
        self.input_params = parsed.input_params
        self.output_params = parsed.output_params
        super().save(*args, **kwargs)
```

- [ ] **Step 2: Generar y aplicar la migración**

```bash
cd call-workspace
py -3.13 manage.py makemigrations scripts
py -3.13 manage.py migrate
```
Esperado: `Applying scripts.0002_script_config_fields... OK`

- [ ] **Step 3: Verificar en shell**

```bash
py -3.13 manage.py shell -c "
from apps.scripts.models import AgentGlobalConfig
cfg = AgentGlobalConfig.get()
print('Global config OK:', cfg.tts_voice, cfg.tts_speed)
"
```
Esperado: `Global config OK: es-US-Neural2-A 1.0`

- [ ] **Step 4: Commit**

```bash
git add call-workspace/apps/scripts/models.py call-workspace/apps/scripts/migrations/
git commit -m "feat(scripts): add AgentGlobalConfig model + per-script config fields"
```

---

### Task 3: `config_resolver.py` — merge script → global

**Files:**
- Create: `call-workspace/apps/scripts/config_resolver.py`
- Create: `call-workspace/tests/scripts/test_config_resolver.py`

- [ ] **Step 1: Escribir los tests**

```python
# call-workspace/tests/scripts/test_config_resolver.py
import pytest
from apps.scripts.config_resolver import ResolvedAgentConfig, resolve_agent_config


@pytest.mark.django_db
def test_resolve_uses_script_value_when_set(script_with_voice):
    """Si el script tiene tts_voice, se usa ese valor."""
    cfg = resolve_agent_config(script_with_voice)
    assert cfg.tts_voice == "es-US-Neural2-B"


@pytest.mark.django_db
def test_resolve_falls_back_to_global_when_null(script_no_config):
    """Si el script no tiene config, se usan los defaults globales."""
    cfg = resolve_agent_config(script_no_config)
    assert cfg.tts_voice == "es-US-Neural2-A"
    assert cfg.tts_speed == 1.0
    assert cfg.llm_temperature == 0.5
    assert cfg.vad_silence_ms == 900


@pytest.mark.django_db
def test_resolve_partial_override(script_partial_config):
    """Solo los campos definidos sobreescriben el global."""
    cfg = resolve_agent_config(script_partial_config)
    assert cfg.tts_speed == 1.5       # del script
    assert cfg.tts_voice == "es-US-Neural2-A"  # del global


# conftest.py fixtures needed:
# @pytest.fixture
# def script_with_voice():
#     return Script.objects.create(name="test_voice", prompt_template="hola", greeting="hi", tts_voice="es-US-Neural2-B")
```

- [ ] **Step 2: Verificar que los tests fallan**

```bash
cd call-workspace
py -3.13 -m pytest tests/scripts/test_config_resolver.py -v
```
Esperado: `ImportError: cannot import name 'resolve_agent_config'`

- [ ] **Step 3: Crear `config_resolver.py`**

```python
# call-workspace/apps/scripts/config_resolver.py
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
    """Merge script config → global defaults. Script fields override global when not None."""
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
```

- [ ] **Step 4: Crear fixtures en `call-workspace/tests/conftest.py`**

```python
# call-workspace/tests/conftest.py
import pytest
from apps.scripts.models import Script, AgentGlobalConfig


@pytest.fixture(autouse=True)
def global_config(db):
    AgentGlobalConfig.objects.get_or_create(pk=1)


@pytest.fixture
def script_with_voice(db):
    return Script.objects.create(
        name="test_voice", prompt_template="hola [[ok]]",
        greeting="hi", tts_voice="es-US-Neural2-B"
    )


@pytest.fixture
def script_no_config(db):
    return Script.objects.create(
        name="test_no_config", prompt_template="hola [[ok]]", greeting="hi"
    )


@pytest.fixture
def script_partial_config(db):
    return Script.objects.create(
        name="test_partial", prompt_template="hola [[ok]]",
        greeting="hi", tts_speed=1.5
    )
```

- [ ] **Step 5: Correr los tests**

```bash
cd call-workspace
py -3.13 -m pytest tests/scripts/test_config_resolver.py -v
```
Esperado: todos `PASSED`

- [ ] **Step 6: Commit**

```bash
git add call-workspace/apps/scripts/config_resolver.py call-workspace/tests/
git commit -m "feat(scripts): config_resolver merges script → global agent config"
```

---

### Task 4: Actualizar `GoogleTTS.synthesize()` con speed y pitch

**Files:**
- Modify: `src/tts/google_tts.py`

- [ ] **Step 1: Actualizar el método `synthesize()`**

```python
# src/tts/google_tts.py  — reemplazar el método synthesize completo
async def synthesize(
    self,
    text: str,
    language: str | None = None,
    voice: str | None = None,
    speed: float = 1.0,
    pitch: float = 0.0,
) -> bytes:
    lang = language or self._default_language
    voice_name = voice or self._default_voice

    cache_key = hashlib.md5(f"{voice_name}:{lang}:{speed}:{pitch}:{text}".encode()).hexdigest()
    if cache_key in _cache:
        logger.debug("tts_cache_hit", text_length=len(text))
        return _cache[cache_key]

    synthesis_input = tts.SynthesisInput(text=text)
    voice_params = tts.VoiceSelectionParams(
        language_code=lang,
        name=voice_name,
    )
    audio_config = tts.AudioConfig(
        audio_encoding=tts.AudioEncoding.LINEAR16,
        sample_rate_hertz=24000,
        speaking_rate=speed,
        pitch=pitch,
    )

    try:
        response = await self._client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config,
        )
        audio_bytes = response.audio_content

        if len(_cache) < _CACHE_MAX_SIZE:
            _cache[cache_key] = audio_bytes

        logger.debug("tts_synthesized", text_length=len(text), audio_bytes=len(audio_bytes))
        return audio_bytes

    except Exception as exc:
        logger.error("google_tts_error", error=str(exc), text_preview=text[:50])
        raise
```

- [ ] **Step 2: Verificar que los tests existentes no se rompen**

```bash
cd C:\Users\tomas\Desktop\trabajo\botvoz\BOT_VOZ
py -3.13 -m pytest tests/unit/ -v -m "not integration"
```
Esperado: sin nuevos fallos

- [ ] **Step 3: Commit**

```bash
git add src/tts/google_tts.py
git commit -m "feat(tts): add speed and pitch params to GoogleTTS.synthesize()"
```

---

### Task 5: Actualizar `GeminiClient.generate_streaming()` con temperature y max_tokens

**Files:**
- Modify: `src/llm/gemini_client.py`

- [ ] **Step 1: Actualizar `generate_streaming()`**

```python
# src/llm/gemini_client.py — reemplazar generate_streaming completo
async def generate_streaming(
    self,
    session: SessionState,
    user_text: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> AsyncIterator[str]:
    """Genera respuesta en streaming. temperature y max_tokens sobreescriben el config por defecto."""
    system_prompt = build_system_prompt(session)

    gen_config = GenerationConfig(
        temperature=temperature if temperature is not None else self._generation_config.temperature,
        max_output_tokens=max_tokens if max_tokens is not None else self._generation_config.max_output_tokens,
        top_p=0.9,
    )

    model = GenerativeModel(
        model_name=self._model_id,
        system_instruction=system_prompt,
        generation_config=gen_config,
    )

    history = [
        Content(role=msg["role"], parts=[Part.from_text(msg["parts"][0]["text"])])
        for msg in session.get_history_for_llm()
    ]

    chat = model.start_chat(history=history)

    try:
        async for chunk in await chat.send_message_async(user_text, stream=True):
            for part in chunk.candidates[0].content.parts:
                if part.text:
                    yield part.text
    except Exception as exc:
        logger.error("gemini_streaming_error", call_id=session.call_id, error=str(exc))
        raise
```

- [ ] **Step 2: Correr tests unitarios**

```bash
py -3.13 -m pytest tests/unit/ -v -m "not integration"
```
Esperado: sin nuevos fallos

- [ ] **Step 3: Commit**

```bash
git add src/llm/gemini_client.py
git commit -m "feat(llm): add temperature and max_tokens params to generate_streaming()"
```

---

### Task 6: Actualizar `consumers.py` — test_values + resolved config + render greeting

**Files:**
- Modify: `call-workspace/apps/calls/consumers.py`

- [ ] **Step 1: Reemplazar `_load_script()` completo**

```python
# call-workspace/apps/calls/consumers.py
# Al inicio del archivo, agregar imports:
import sys
from pathlib import Path
BOT_VOZ_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(BOT_VOZ_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_VOZ_ROOT))

# Reemplazar _load_script():
async def _load_script(self, script_id, script_name, test_values: dict = None):
    """Carga el script, renderiza greeting con test_values, aplica resolved config."""
    try:
        from apps.scripts.models import Script
        from apps.scripts.config_resolver import resolve_agent_config
        from apps.scripts.parsers import render_template
        from config.bot_config import BotProfileSchema
        from src.session.session_state import SessionState

        script = await asyncio.get_event_loop().run_in_executor(
            None, lambda: Script.objects.get(pk=script_id)
        )

        cfg = await asyncio.get_event_loop().run_in_executor(
            None, lambda: resolve_agent_config(script)
        )

        values = test_values or {}
        try:
            greeting_rendered = render_template(script.greeting, values)
        except KeyError:
            greeting_rendered = script.greeting  # fallback sin reemplazar

        try:
            prompt_rendered = render_template(script.prompt_template, values)
        except KeyError:
            prompt_rendered = script.prompt_template

        self.profile = BotProfileSchema(
            name=f"script_{script.pk}",
            system_prompt=prompt_rendered,
            greeting=greeting_rendered,
            farewell="Gracias por la llamada.",
            guardrails={},
            memory={},
            tools={"enabled": []},
        )
        self.session = SessionState(
            call_id=self.session_id,
            caller_number="web-test",
            bot_profile=self.profile,
        )
        self.resolved_cfg = cfg
        logger.info("bot_test_script_loaded", script_id=script_id, name=script.name)
        await self._send_greeting()
    except Exception as exc:
        logger.warning("bot_test_script_failed", error=str(exc))
        self.resolved_cfg = None
        await self._init_session_default()
```

- [ ] **Step 2: Actualizar `receive()` para pasar `test_values`**

```python
# En el método receive(), cambiar el bloque load_script:
if data.get("type") == "load_script":
    test_values = data.get("test_values", {})
    await self._load_script(
        data.get("script_id"),
        data.get("script_name"),
        test_values=test_values,
    )
    return
```

- [ ] **Step 3: Actualizar `_send_greeting()` para usar resolved config**

```python
async def _send_greeting(self):
    try:
        cfg = getattr(self, "resolved_cfg", None)
        voice = cfg.tts_voice if cfg else None
        speed = cfg.tts_speed if cfg else 1.0
        pitch = cfg.tts_pitch if cfg else 0.0

        pcm = await self.tts.synthesize(
            self.profile.greeting,
            voice=voice,
            speed=speed,
            pitch=pitch,
        )
        wav_b64 = base64.b64encode(_wrap_wav(pcm)).decode()
        await self.send(text_data=json.dumps({
            "type": "greeting",
            "text": self.profile.greeting,
            "audio": wav_b64,
        }))
    except Exception as exc:
        await self.send(text_data=json.dumps({"type": "error", "message": f"TTS saludo: {exc}"}))
```

- [ ] **Step 4: Actualizar `_build_response()` para usar resolved config**

```python
async def _build_response(self, user_text: str):
    from src.persistence.models import TranscriptionRole
    await self.send(text_data=json.dumps({"type": "status", "text": "Pensando..."}))

    cfg = getattr(self, "resolved_cfg", None)
    temperature = cfg.llm_temperature if cfg else None
    max_tokens = cfg.llm_max_tokens if cfg else None

    parts = []
    async for chunk in self.llm.generate_streaming(
        self.session, user_text,
        temperature=temperature,
        max_tokens=max_tokens,
    ):
        parts.append(chunk)
    response_text = "".join(parts).strip()
    self.session.add_message(TranscriptionRole.USER, user_text)
    self.session.add_message(TranscriptionRole.ASSISTANT, response_text)

    voice = cfg.tts_voice if cfg else None
    speed = cfg.tts_speed if cfg else 1.0
    pitch = cfg.tts_pitch if cfg else 0.0
    try:
        pcm = await self.tts.synthesize(response_text, voice=voice, speed=speed, pitch=pitch)
        wav_b64 = base64.b64encode(_wrap_wav(pcm)).decode()
        await self.send(text_data=json.dumps({
            "type": "response", "text": response_text, "audio": wav_b64,
        }))
    except Exception as exc:
        await self.send(text_data=json.dumps({"type": "response", "text": response_text}))
```

- [ ] **Step 5: Commit**

```bash
git add call-workspace/apps/calls/consumers.py
git commit -m "feat(bot): consumers uses resolved config + renders greeting with test_values"
```

---

### Task 7: Actualizar `bot_test.html` — formulario de test_values

**Files:**
- Modify: `call-workspace/templates/calls/bot_test.html`

- [ ] **Step 1: Reemplazar la sección del formulario de variables en el panel Script activo**

En el bloque `{% if script %}`, después del saludo, reemplazar la sección existente de variables por este formulario:

```html
{% if script.input_params %}
<div class="mb-3 small">
  <strong>Variables de prueba:</strong>
  <div class="mt-2" id="test-vars-form">
    {% for p in script.input_params %}
    <div class="mb-2">
      <label class="form-label mb-1" style="font-size:0.75rem;">
        <code>&#123;&#123;{{ p }}&#125;&#125;</code>
      </label>
      <input type="text" id="var_{{ p }}" data-param="{{ p }}"
             class="form-control form-control-sm test-var-input"
             placeholder="{{ p }}" />
    </div>
    {% endfor %}
  </div>
</div>
{% endif %}
```

- [ ] **Step 2: Actualizar el JavaScript para recoger los valores y enviarlos al WS**

En el bloque `<script>`, reemplazar la sección `ws.onopen`:

```javascript
ws.onopen = () => {
  setStatus('Conectado', 'success');

  if (SCRIPT_ID) {
    // Recoger valores de los inputs
    const testValues = {};
    document.querySelectorAll('.test-var-input').forEach(input => {
      testValues[input.dataset.param] = input.value;
    });

    ws.send(JSON.stringify({
      type: 'load_script',
      script_id: SCRIPT_ID,
      script_name: SCRIPT_NAME,
      test_values: testValues,
    }));
  }
};
```

- [ ] **Step 3: Commit**

```bash
git add call-workspace/templates/calls/bot_test.html
git commit -m "feat(ui): bot test form sends test_values for greeting + prompt variables"
```

---

### Task 8: Formulario de script con 3 pestañas Bootstrap

**Files:**
- Modify: `call-workspace/apps/scripts/forms.py`
- Modify: `call-workspace/templates/scripts/form.html`

- [ ] **Step 1: Actualizar `ScriptForm` para incluir los nuevos campos**

```python
# call-workspace/apps/scripts/forms.py
from django import forms
from .models import Script, TTS_VOICE_CHOICES


class ScriptForm(forms.ModelForm):
    class Meta:
        model = Script
        fields = [
            "name", "description", "greeting", "prompt_template",
            "tts_voice", "tts_speed", "tts_pitch",
            "llm_temperature", "llm_max_tokens",
            "vad_silence_ms", "max_call_duration_seconds",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
            "greeting": forms.TextInput(attrs={"class": "form-control"}),
            "prompt_template": forms.Textarea(attrs={"rows": 12, "class": "form-control font-monospace"}),
            "tts_voice": forms.Select(attrs={"class": "form-select"}),
            "tts_speed": forms.NumberInput(attrs={"class": "form-control", "step": "0.1", "min": "0.5", "max": "2.0"}),
            "tts_pitch": forms.NumberInput(attrs={"class": "form-control", "step": "1", "min": "-10", "max": "10"}),
            "llm_temperature": forms.NumberInput(attrs={"class": "form-control", "step": "0.05", "min": "0", "max": "1"}),
            "llm_max_tokens": forms.NumberInput(attrs={"class": "form-control", "min": "50", "max": "1000"}),
            "vad_silence_ms": forms.NumberInput(attrs={"class": "form-control", "min": "300", "max": "3000", "step": "100"}),
            "max_call_duration_seconds": forms.NumberInput(attrs={"class": "form-control", "min": "60", "max": "1800"}),
        }
```

- [ ] **Step 2: Reemplazar `templates/scripts/form.html` con versión de 3 pestañas**

```html
{% extends "base.html" %}
{% block page_title %}{{ title }}{% endblock %}
{% block breadcrumb_items %}
<li class="breadcrumb-item"><a href="{% url 'scripts:list' %}">Scripts</a></li>
<li class="breadcrumb-item active">{{ title }}</li>
{% endblock %}
{% block content %}
<div class="row g-3">
  <div class="col-lg-8">
    <div class="card">
      <div class="card-header"><h6 class="mb-0"><i class="feather-edit-3 me-2"></i>{{ title }}</h6></div>
      <div class="card-body">
        <form method="post">
          {% csrf_token %}
          <!-- Tabs nav -->
          <ul class="nav nav-tabs mb-4" id="scriptTabs" role="tablist">
            <li class="nav-item"><button class="nav-link active" data-bs-toggle="tab" data-bs-target="#tab-contenido"><i class="feather-file-text me-1"></i>Contenido</button></li>
            <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-voz"><i class="feather-mic me-1"></i>Voz</button></li>
            <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-comportamiento"><i class="feather-settings me-1"></i>Comportamiento</button></li>
          </ul>

          <!-- Tab: Contenido -->
          <div class="tab-content">
            <div class="tab-pane fade show active" id="tab-contenido">
              <div class="mb-3">
                <label class="form-label fw-semibold">Nombre</label>
                {{ form.name }}
                {% if form.name.errors %}<div class="text-danger small">{{ form.name.errors }}</div>{% endif %}
              </div>
              <div class="mb-3">
                <label class="form-label fw-semibold">Descripción</label>
                {{ form.description }}
              </div>
              <div class="mb-3">
                <label class="form-label fw-semibold">Saludo inicial</label>
                {{ form.greeting }}
                <small class="text-muted">Soporta <code>&#123;&#123;variables&#125;&#125;</code></small>
                {% if form.greeting.errors %}<div class="text-danger small">{{ form.greeting.errors }}</div>{% endif %}
              </div>
              <div class="mb-3">
                <label class="form-label fw-semibold">Prompt / instrucciones</label>
                <div class="alert alert-light border small mb-2 py-2">
                  <code>&#123;&#123;var&#125;&#125;</code> entrada &nbsp;|&nbsp; <code>[[var]]</code> captura &nbsp;|&nbsp; <code>## comentario ##</code>
                </div>
                {{ form.prompt_template }}
              </div>
              {% if script %}
              <div class="alert alert-info small">
                <strong>Inputs detectados:</strong> {{ script.input_params|join:", "|default:"—" }}<br>
                <strong>Outputs detectados:</strong> {{ script.output_params|join:", "|default:"—" }}
              </div>
              {% endif %}
            </div>

            <!-- Tab: Voz -->
            <div class="tab-pane fade" id="tab-voz">
              {% load scripts_global_config %}
              {% global_config as gcfg %}
              <div class="mb-4">
                <label class="form-label fw-semibold">Voz del agente</label>
                {{ form.tts_voice }}
                <small class="text-muted">Default global: {{ gcfg.tts_voice }}</small>
              </div>
              <div class="mb-4">
                <label class="form-label fw-semibold">Velocidad <span id="speed-val">{{ form.tts_speed.value|default:"1.0" }}x</span></label>
                {{ form.tts_speed }}
                <small class="text-muted">Default global: {{ gcfg.tts_speed }}x | Rango: 0.5 – 2.0</small>
              </div>
              <div class="mb-4">
                <label class="form-label fw-semibold">Tono (pitch) <span id="pitch-val">{{ form.tts_pitch.value|default:"0" }}</span></label>
                {{ form.tts_pitch }}
                <small class="text-muted">Default global: {{ gcfg.tts_pitch }} | Rango: -10 – +10</small>
              </div>
            </div>

            <!-- Tab: Comportamiento -->
            <div class="tab-pane fade" id="tab-comportamiento">
              {% if not gcfg %} {% load scripts_global_config %} {% global_config as gcfg %} {% endif %}
              <div class="row g-3">
                <div class="col-md-6">
                  <label class="form-label fw-semibold">Temperatura LLM</label>
                  {{ form.llm_temperature }}
                  <small class="text-muted">0 = preciso, 1 = creativo. Default: {{ gcfg.llm_temperature }}</small>
                </div>
                <div class="col-md-6">
                  <label class="form-label fw-semibold">Tokens máximos</label>
                  {{ form.llm_max_tokens }}
                  <small class="text-muted">Longitud máxima de respuesta. Default: {{ gcfg.llm_max_tokens }}</small>
                </div>
                <div class="col-md-6">
                  <label class="form-label fw-semibold">Timeout de silencio (ms)</label>
                  {{ form.vad_silence_ms }}
                  <small class="text-muted">Ms de silencio para cortar turno. Default: {{ gcfg.vad_silence_ms }}</small>
                </div>
                <div class="col-md-6">
                  <label class="form-label fw-semibold">Duración máxima (seg)</label>
                  {{ form.max_call_duration_seconds }}
                  <small class="text-muted">Default: {{ gcfg.max_call_duration_seconds }}</small>
                </div>
              </div>
            </div>
          </div>

          <div class="d-flex gap-2 mt-4">
            <button type="submit" class="btn btn-primary"><i class="feather-save me-2"></i>Guardar</button>
            <a href="{% url 'scripts:list' %}" class="btn btn-outline-secondary">Cancelar</a>
            {% if script %}<a href="{% url 'scripts:preview' script.pk %}" class="btn btn-outline-info ms-auto"><i class="feather-eye me-2"></i>Probar</a>{% endif %}
          </div>
        </form>
      </div>
    </div>
  </div>

  <!-- Panel referencia -->
  <div class="col-lg-4">
    <div class="card">
      <div class="card-header"><h6 class="mb-0"><i class="feather-book-open me-2"></i>Ejemplo</h6></div>
      <div class="card-body small">
        <pre class="bg-light p-2 rounded" style="font-size:0.8rem;">Saludo:
Hola {{nombre}} desde
{{concesionaria}}

Prompt:
Confirmar {{fecha_agenda}}
¿Asistirás?
[[confirmacion]]

## Opciones: asistira,
   re-agenda, cancela ##</pre>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 3: Pasar `gcfg` desde las vistas `create_view` y `edit_view`**

En `views.py`, actualizar ambas vistas para incluir `gcfg` en el contexto:

```python
from .models import Script, AgentGlobalConfig

@login_required
def create_view(request):
    if request.method == "POST":
        form = ScriptForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("scripts:list")
    else:
        form = ScriptForm()
    return render(request, "scripts/form.html", {
        "form": form, "title": "Nuevo script",
        "gcfg": AgentGlobalConfig.get(),
    })


@login_required
def edit_view(request, pk: int):
    script = get_object_or_404(Script, pk=pk)
    if request.method == "POST":
        form = ScriptForm(request.POST, instance=script)
        if form.is_valid():
            form.save()
            return redirect("scripts:list")
    else:
        form = ScriptForm(instance=script)
    return render(request, "scripts/form.html", {
        "form": form, "title": f"Editar: {script.name}",
        "script": script, "gcfg": AgentGlobalConfig.get(),
    })
```

Y en `form.html` eliminar `{% load scripts_global_config %}` y `{% global_config as gcfg %}` — el contexto ya tiene `gcfg`.

- [ ] **Step 4: Commit**

```bash
git add call-workspace/apps/scripts/forms.py call-workspace/templates/scripts/form.html call-workspace/apps/scripts/templatetags/
git commit -m "feat(ui): script form with 3 Bootstrap tabs (Contenido/Voz/Comportamiento)"
```

---

### Task 9: Vista y template de configuración global del agente

**Files:**
- Modify: `call-workspace/apps/scripts/views.py`
- Modify: `call-workspace/apps/scripts/urls.py`
- Create: `call-workspace/templates/scripts/global_config.html`

- [ ] **Step 1: Agregar `GlobalConfigForm` en `forms.py`**

```python
# Agregar al final de call-workspace/apps/scripts/forms.py
from .models import AgentGlobalConfig

class GlobalConfigForm(forms.ModelForm):
    class Meta:
        model = AgentGlobalConfig
        fields = ["tts_voice", "tts_speed", "tts_pitch", "llm_temperature",
                  "llm_max_tokens", "vad_silence_ms", "max_call_duration_seconds"]
        widgets = {
            "tts_voice": forms.Select(attrs={"class": "form-select"}),
            "tts_speed": forms.NumberInput(attrs={"class": "form-control", "step": "0.1", "min": "0.5", "max": "2.0"}),
            "tts_pitch": forms.NumberInput(attrs={"class": "form-control", "step": "1", "min": "-10", "max": "10"}),
            "llm_temperature": forms.NumberInput(attrs={"class": "form-control", "step": "0.05", "min": "0", "max": "1"}),
            "llm_max_tokens": forms.NumberInput(attrs={"class": "form-control", "min": "50", "max": "1000"}),
            "vad_silence_ms": forms.NumberInput(attrs={"class": "form-control", "min": "300", "max": "3000", "step": "100"}),
            "max_call_duration_seconds": forms.NumberInput(attrs={"class": "form-control", "min": "60", "max": "1800"}),
        }
```

- [ ] **Step 2: Agregar vista en `views.py`**

```python
# Agregar en call-workspace/apps/scripts/views.py
from .forms import ScriptForm, GlobalConfigForm
from .models import Script, AgentGlobalConfig

@login_required
def global_config_view(request):
    instance = AgentGlobalConfig.get()
    if request.method == "POST":
        form = GlobalConfigForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            from django.contrib import messages
            messages.success(request, "Configuración global guardada.")
            return redirect("scripts:global_config")
    else:
        form = GlobalConfigForm(instance=instance)
    return render(request, "scripts/global_config.html", {"form": form})
```

- [ ] **Step 3: Agregar URL**

```python
# call-workspace/apps/scripts/urls.py — agregar:
path("settings/agente/", views.global_config_view, name="global_config"),
```

- [ ] **Step 4: Crear template `global_config.html`**

```html
{% extends "base.html" %}
{% block page_title %}Configuración del Agente{% endblock %}
{% block breadcrumb_items %}<li class="breadcrumb-item active">Configuración global</li>{% endblock %}
{% block content %}
<div class="row">
  <div class="col-lg-7">
    <div class="card">
      <div class="card-header"><h6 class="mb-0"><i class="feather-settings me-2"></i>Valores por defecto del agente</h6></div>
      <div class="card-body">
        <p class="text-muted small mb-4">Estos valores se usan para todos los scripts que no tengan configuración propia.</p>
        <form method="post">
          {% csrf_token %}
          <h6 class="mb-3 text-muted">Voz</h6>
          <div class="mb-3">
            <label class="form-label fw-semibold">Voz por defecto</label>
            {{ form.tts_voice }}
          </div>
          <div class="row g-3 mb-4">
            <div class="col-md-6">
              <label class="form-label fw-semibold">Velocidad (0.5 – 2.0)</label>
              {{ form.tts_speed }}
            </div>
            <div class="col-md-6">
              <label class="form-label fw-semibold">Tono pitch (-10 – +10)</label>
              {{ form.tts_pitch }}
            </div>
          </div>
          <h6 class="mb-3 text-muted">LLM</h6>
          <div class="row g-3 mb-4">
            <div class="col-md-6">
              <label class="form-label fw-semibold">Temperatura (0 – 1)</label>
              {{ form.llm_temperature }}
              <small class="text-muted">0 = preciso, 1 = creativo</small>
            </div>
            <div class="col-md-6">
              <label class="form-label fw-semibold">Tokens máximos</label>
              {{ form.llm_max_tokens }}
            </div>
          </div>
          <h6 class="mb-3 text-muted">Conversación</h6>
          <div class="row g-3 mb-4">
            <div class="col-md-6">
              <label class="form-label fw-semibold">Timeout silencio (ms)</label>
              {{ form.vad_silence_ms }}
            </div>
            <div class="col-md-6">
              <label class="form-label fw-semibold">Duración máxima (seg)</label>
              {{ form.max_call_duration_seconds }}
            </div>
          </div>
          <button type="submit" class="btn btn-primary"><i class="feather-save me-2"></i>Guardar</button>
        </form>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 5: Commit**

```bash
git add call-workspace/apps/scripts/ call-workspace/templates/scripts/global_config.html
git commit -m "feat(ui): global agent config page at /scripts/settings/agente/"
```

---

### Task 10: Actualizar `base.html` — link de configuración en sidebar

**Files:**
- Modify: `call-workspace/templates/base.html`

- [ ] **Step 1: Agregar "Configuración" al sidebar**

En `base.html`, dentro de `<li class="nxl-item nxl-caption"><label>Herramientas</label></li>`, agregar después del Bot de Prueba:

```html
<!-- Configuración del agente -->
<li class="nxl-item {% if '/scripts/settings/' in request.path %}nxl-active{% endif %}">
  <a href="{% url 'scripts:global_config' %}" class="nxl-link">
    <span class="nxl-micon"><i class="feather-sliders"></i></span>
    <span class="nxl-mtext">Config. Agente</span>
  </a>
</li>
```

- [ ] **Step 2: Verificar que el sidebar muestra el nuevo link**

```bash
curl -s http://127.0.0.1:8001/scripts/settings/agente/ | grep -c "Configuración"
```
Esperado: número mayor a 0 (requiere login)

- [ ] **Step 3: Commit**

```bash
git add call-workspace/templates/base.html
git commit -m "feat(ui): add agent config link to sidebar"
```

---

### Task 11: Migrar datos existentes y verificar end-to-end

- [ ] **Step 1: Verificar que el script existente mantiene sus datos**

```bash
cd call-workspace
py -3.13 manage.py shell -c "
from apps.scripts.models import Script, AgentGlobalConfig
from apps.scripts.config_resolver import resolve_agent_config
s = Script.objects.first()
print('Script:', s.name)
print('Input params (includes greeting vars):', s.input_params)
cfg = resolve_agent_config(s)
print('Resolved voice:', cfg.tts_voice)
print('Resolved speed:', cfg.tts_speed)
"
```

- [ ] **Step 2: Re-guardar scripts existentes para actualizar input_params con greeting vars**

```bash
py -3.13 manage.py shell -c "
from apps.scripts.models import Script
for s in Script.objects.all():
    s.save()
    print(f'Re-saved: {s.name} | inputs: {s.input_params}')
"
```

- [ ] **Step 3: Correr toda la suite de tests**

```bash
cd call-workspace
py -3.13 -m pytest tests/ -v
```
Esperado: todos `PASSED`

- [ ] **Step 4: Commit final**

```bash
git add -A
git commit -m "feat: script variables in greeting + agent config options complete"
```
