# Script Variables en Saludo + Configuración del Agente

**Fecha:** 2026-05-13  
**Estado:** Aprobado  

---

## Resumen

Dos mejoras al sistema de scripts:

1. **Variables en el saludo** — el campo `greeting` soporta la misma sintaxis `{{param}}` que el prompt. Las variables se extraen de ambos y se combinan en `input_params`. Se renderizan antes de TTS tanto en prueba como en batch.

2. **Configuración del agente por script** — cada script puede configurar voz, velocidad, tono, temperatura LLM, timeout de silencio y duración máxima. Un modelo `AgentGlobalConfig` singleton define los valores por defecto que se usan cuando el script no los sobreescribe.

---

## 1. Modelo de datos

### 1.1 Cambios a `Script`

Nuevos campos opcionales (`null=True`, `blank=True`). Si están vacíos, el runtime usa `AgentGlobalConfig`:

| Campo | Tipo | Rango | Descripción |
|---|---|---|---|
| `tts_voice` | CharField(50) choices | ver lista | Voz Google TTS |
| `tts_speed` | FloatField | 0.5 – 2.0 | Velocidad de habla |
| `tts_pitch` | FloatField | -10.0 – 10.0 | Tono de voz |
| `llm_temperature` | FloatField | 0.0 – 1.0 | Creatividad del LLM |
| `llm_max_tokens` | IntegerField | 50 – 1000 | Longitud máxima de respuesta |
| `vad_silence_ms` | IntegerField | 300 – 3000 | Ms de silencio para cortar turno |
| `max_call_duration_seconds` | IntegerField | 60 – 1800 | Duración máxima de la llamada |

**Voces disponibles (Google TTS Neural2 en español):**
- Mujer: `es-US-Neural2-A` (natural), `es-US-Neural2-C` (formal)
- Hombre: `es-US-Neural2-B` (natural), `es-US-Neural2-D` (formal)

### 1.2 Nuevo modelo `AgentGlobalConfig` (singleton)

Mismos campos que los de configuración en `Script`, pero con valores por defecto concretos. Solo puede existir una instancia (se crea automáticamente si no existe).

**Valores por defecto:**

| Campo | Default |
|---|---|
| `tts_voice` | `es-US-Neural2-A` |
| `tts_speed` | `1.0` |
| `tts_pitch` | `0.0` |
| `llm_temperature` | `0.5` |
| `llm_max_tokens` | `300` |
| `vad_silence_ms` | `900` |
| `max_call_duration_seconds` | `600` |

### 1.3 Migración

Una migración Django para los nuevos campos en `Script` y la tabla `AgentGlobalConfig`.

---

## 2. Parser

### 2.1 Cambio a `parse_template()`

El parser recibe `prompt_template` y `greeting` por separado, extrae `{{params}}` de ambos y los combina deduplicados en orden de aparición (greeting primero, luego prompt).

```python
def parse_template(prompt: str, greeting: str = "") -> ParsedTemplate:
    all_text = greeting + "\n" + prompt
    return ParsedTemplate(
        input_params=_unique_in_order(INPUT_PATTERN.findall(all_text)),
        output_params=_unique_in_order(OUTPUT_PATTERN.findall(prompt)),  # outputs solo en prompt
    )
```

### 2.2 `Script.save()`

Llama al parser pasando tanto `prompt_template` como `greeting`:
```python
parsed = parse_template(self.prompt_template, self.greeting)
```

---

## 3. Resolución de configuración en runtime

### 3.1 Función `resolve_agent_config(script)`

Ubicación: `apps/scripts/config_resolver.py`

Hace merge campo a campo: script → global. Retorna un dataclass `ResolvedAgentConfig` con todos los campos garantizados (no nulos).

```python
@dataclass
class ResolvedAgentConfig:
    tts_voice: str
    tts_speed: float
    tts_pitch: float
    llm_temperature: float
    llm_max_tokens: int
    vad_silence_ms: int
    max_call_duration_seconds: int
```

### 3.2 Uso en el WebSocket consumer

En `consumers.py`, al cargar el script:
1. Llama `resolve_agent_config(script)` → `cfg`
2. Renderiza greeting: `render_template(script.greeting, test_values)`
3. Renderiza system prompt: `render_template(script.prompt_template, test_values)`
4. Pasa `cfg.tts_voice`, `cfg.tts_speed`, `cfg.tts_pitch` al método `tts.synthesize()`
5. Pasa `cfg.llm_temperature`, `cfg.llm_max_tokens` al `llm.generate_streaming()`
6. Usa `cfg.vad_silence_ms` como el threshold de silencio en el VAD del cliente

### 3.3 Cambios a `GoogleTTS.synthesize()`

Agrega parámetros `speed: float = 1.0` y `pitch: float = 0.0`:
```python
async def synthesize(self, text: str, language=None, voice=None, speed=1.0, pitch=0.0) -> bytes
```

### 3.4 Cambios a `GeminiClient.generate_streaming()`

Agrega `temperature: float` y `max_tokens: int` opcionales que sobreescriben los valores del modelo.

---

## 4. UI

### 4.1 Formulario de script — 3 pestañas (Bootstrap tabs)

**Pestaña "Contenido"** (existente, sin cambios estructurales):
- Nombre, descripción
- Saludo — hint: soporta `{{variables}}`
- Prompt/instrucciones — hint de sintaxis completa
- Variables detectadas (auto-refresh en JS al escribir)

**Pestaña "Voz":**
- Selector de voz con 4 opciones agrupadas (Mujer / Hombre) + botón "▶ Muestra"
- Slider velocidad: 0.5x → 2.0x, paso 0.1, valor actual visible
- Slider tono: -10 → +10, paso 1
- Texto gris si vacío: "Usando default global: [valor]"

**Pestaña "Comportamiento":**
- Slider timeout silencio: 300ms → 3000ms
- Input duración máxima: 1 – 30 minutos
- Slider temperatura LLM: 0.0 → 1.0, con labels "Preciso ← → Creativo"
- Input tokens máximos: 50 – 1000

### 4.2 Página `/settings/agente/`

Vista Django con el mismo layout de 3 secciones (Voz / Comportamiento / LLM). Edita la instancia singleton de `AgentGlobalConfig`. Accesible desde el sidebar bajo "Herramientas".

### 4.3 Bot de prueba — variables de entrada

El formulario de prueba muestra los `input_params` combinados (greeting + prompt). Si el script tiene `{{nombre}}` en el greeting y `{{fecha_agenda}}` en el prompt, ambos aparecen como campos de texto antes de iniciar la llamada.

Los valores se envían al WebSocket en el mensaje `load_script`:
```json
{
  "type": "load_script",
  "script_id": "1",
  "test_values": {"nombre": "Juan", "concesionaria": "Chery Norte", "fecha_agenda": "15/05"}
}
```

### 4.4 Batch

`BatchJob` ya almacena las columnas del CSV. El servicio de procesamiento usa `render_template()` en el greeting Y el prompt antes de iniciar cada llamada. Los `input_params` del script definen exactamente qué columnas son obligatorias en el CSV.

---

## 5. Flujo completo de datos

```
Script.greeting = "Hola {{nombre}} desde {{concesionaria}}"
Script.prompt_template = "Confirmar {{fecha_agenda}} ... [[confirmacion]]"

→ parse_template() extrae:
  input_params = [nombre, concesionaria, fecha_agenda]
  output_params = [confirmacion]

En prueba:
  test_values = {nombre: "Juan", concesionaria: "Chery", fecha_agenda: "15/05"}
  greeting_rendered = "Hola Juan desde Chery"
  prompt_rendered = "Confirmar 15/05 ... [[confirmacion]]"
  cfg = resolve_agent_config(script)
  tts.synthesize(greeting_rendered, voice=cfg.tts_voice, speed=cfg.tts_speed)

En batch:
  row = {nombre: "María", concesionaria: "Chery Sur", fecha_agenda: "16/05"}
  greeting_rendered = render_template(script.greeting, row)
  prompt_rendered = render_template(script.prompt_template, row)
```

---

## 6. Archivos a modificar / crear

| Archivo | Acción |
|---|---|
| `apps/scripts/models.py` | Agregar campos de config + nuevo modelo `AgentGlobalConfig` |
| `apps/scripts/parsers.py` | Actualizar `parse_template()` para recibir greeting |
| `apps/scripts/config_resolver.py` | Crear — función `resolve_agent_config()` |
| `apps/scripts/views.py` | Agregar vista `global_config_view` |
| `apps/scripts/urls.py` | Agregar ruta `/settings/agente/` |
| `apps/scripts/forms.py` | Actualizar con nuevos campos + tabs |
| `apps/scripts/migrations/` | Nueva migración |
| `templates/scripts/form.html` | Rediseñar con pestañas Bootstrap |
| `templates/scripts/global_config.html` | Crear — página de settings globales |
| `templates/calls/bot_test.html` | Agregar campos de test_values al formulario |
| `templates/base.html` | Agregar "Configuración" en sidebar |
| `call-workspace/apps/calls/consumers.py` | Usar resolved config + render greeting |
| `src/tts/google_tts.py` | Agregar params `speed` y `pitch` |
| `src/llm/gemini_client.py` | Agregar params `temperature` y `max_tokens` |

---

## 7. Tests

- `test_parser_greeting_variables`: variables extraídas de greeting + prompt combinados
- `test_render_greeting_with_values`: greeting renderizado correctamente
- `test_resolve_config_script_overrides_global`: merge campo a campo
- `test_resolve_config_uses_global_when_null`: fallback a global
- `test_script_form_saves_voice_config`: campos de config guardados correctamente
