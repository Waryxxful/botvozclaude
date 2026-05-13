import base64
import struct
import uuid
import structlog
import json
from typing import AsyncIterator

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from config.bot_config import get_default_profile
from src.llm.gemini_client import GeminiClient
from src.persistence.models import TranscriptionRole
from src.session.session_state import SessionState
from src.stt.stt_factory import get_stt_client
from src.tts.google_tts import GoogleTTS

router = APIRouter(prefix="/test", tags=["Test UI"])
logger = structlog.get_logger(__name__)

_tts: GoogleTTS | None = None
_llm: GeminiClient | None = None


def _get_tts() -> GoogleTTS:
    global _tts
    if _tts is None:
        _tts = GoogleTTS()
    return _tts


def _get_llm() -> GeminiClient:
    global _llm
    if _llm is None:
        _llm = GeminiClient()
    return _llm


def _wrap_wav(pcm: bytes, sample_rate: int = 24000) -> bytes:
    """Add a standard WAV header to raw PCM16 mono audio."""
    size = len(pcm)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + size, b"WAVE",
        b"fmt ", 16, 1, 1,
        sample_rate, sample_rate * 2, 2, 16,
        b"data", size,
    )
    return header + pcm


@router.get("/", response_class=HTMLResponse)
async def test_page() -> HTMLResponse:
    return HTMLResponse(_HTML)


@router.websocket("/ws")
async def test_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    session_id = str(uuid.uuid4())
    logger.info("test_session_accepted", session_id=session_id)

    profile = None
    script_data = None

    try:
        tts = _get_tts()
        llm = _get_llm()
    except Exception as exc:
        logger.error("test_client_init_failed", error=str(exc))
        await websocket.send_json({"type": "error", "message": f"No se pudieron iniciar los clientes GCP: {exc}"})
        await websocket.close()
        return

    # Esperar el script cargado (máximo 3 segundos)
    import asyncio
    start_time = asyncio.get_event_loop().time()
    logger.info("test_waiting_for_script", timeout_seconds=3)
    while asyncio.get_event_loop().time() - start_time < 3:
        try:
            msg = await asyncio.wait_for(websocket.receive(), timeout=0.5)
            logger.info("test_ws_msg_received", msg_type=msg.get("type"), has_text="text" in msg)
            if "text" in msg and msg["text"]:
                try:
                    data = json.loads(msg["text"])
                    logger.info("test_json_received", data_type=data.get("type"))
                    if data.get("type") == "load_script":
                        script_data = data
                        logger.info("test_script_received", script_id=data.get("script_id"), script_name=data.get("script_name"))
                        break
                except json.JSONDecodeError as e:
                    logger.warning("test_json_decode_failed", error=str(e))
                    pass
        except asyncio.TimeoutError:
            continue

    if not script_data:
        logger.info("test_no_script_received", timeout_seconds=3)

    # Cargar perfil (desde script vía HTTP a Django, o predeterminado)
    if script_data and script_data.get("script_id"):
        try:
            import httpx
            script_id = script_data["script_id"]
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"http://localhost:8001/scripts/api/{script_id}/json/")
                resp.raise_for_status()
                s = resp.json()
            from config.bot_config import BotProfileSchema
            profile = BotProfileSchema(
                name=f"script_{script_id}",
                system_prompt=s["system_prompt"],
                greeting=s["greeting"],
                farewell="Gracias por la llamada.",
                guardrails={},
                memory={},
                tools={"enabled": []}
            )
            logger.info("test_script_loaded_ws", script_id=script_id, script_name=s.get("name"))
        except Exception as exc:
            logger.warning("test_script_load_failed", error=str(exc))
            profile = None

    if not profile:
        try:
            profile = get_default_profile()
        except Exception as exc:
            logger.error("test_profile_load_failed", error=str(exc))
            await websocket.send_json({"type": "error", "message": f"No se pudo cargar el perfil: {exc}"})
            await websocket.close()
            return

    session = SessionState(
        call_id=session_id,
        caller_number="web-test",
        bot_profile=profile,
    )

    try:
        greeting_pcm = await tts.synthesize(profile.greeting)
        await websocket.send_json({
            "type": "greeting",
            "text": profile.greeting,
            "audio": base64.b64encode(_wrap_wav(greeting_pcm)).decode(),
        })
        logger.info("test_greeting_sent", session_id=session_id)
    except Exception as exc:
        logger.error("test_greeting_failed", error=str(exc))
        await websocket.send_json({"type": "error", "message": f"Error TTS saludo: {exc}"})

    try:
        while True:
            msg = await websocket.receive()

            if msg.get("type") == "websocket.disconnect":
                break

            if "bytes" in msg and msg["bytes"] is not None:
                audio_bytes: bytes = msg["bytes"]
                if len(audio_bytes) < 400:
                    await websocket.send_json({"type": "ready"})
                    continue

                await websocket.send_json({"type": "status", "text": "Transcribiendo..."})

                try:
                    user_text = await _run_stt(audio_bytes)
                except Exception as exc:
                    logger.error("test_stt_failed", error=str(exc))
                    await websocket.send_json({"type": "error", "message": f"Error STT: {exc}"})
                    continue

                if not user_text:
                    await websocket.send_json({
                        "type": "error",
                        "message": "No se detectó audio reconocible. Intenta de nuevo.",
                    })
                    continue

                await websocket.send_json({"type": "transcript", "text": user_text})
                try:
                    await _build_response(websocket, session, llm, tts, user_text)
                except Exception as exc:
                    logger.error("test_response_failed", error=str(exc))
                    await websocket.send_json({"type": "error", "message": f"Error generando respuesta: {exc}"})

    except WebSocketDisconnect:
        logger.info("test_session_disconnected", session_id=session_id)
    except Exception as exc:
        logger.error("test_session_error", session_id=session_id, error=str(exc), exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass


async def _run_stt(audio_bytes: bytes) -> str:
    """Transcribe raw PCM16 16kHz audio via the configured STT provider."""
    stt = get_stt_client()
    result = ""

    async def _gen() -> AsyncIterator[bytes]:
        yield audio_bytes

    async for text, is_final in stt.transcribe_stream(_gen()):
        if text:
            result = text
        if is_final:
            break
    return result


async def _build_response(
    ws: WebSocket,
    session: SessionState,
    llm: GeminiClient,
    tts: GoogleTTS,
    user_text: str,
) -> None:
    await ws.send_json({"type": "status", "text": "Pensando..."})

    parts: list[str] = []
    async for chunk in llm.generate_streaming(session, user_text):
        parts.append(chunk)
    response_text = "".join(parts).strip()

    session.add_message(TranscriptionRole.USER, user_text)
    session.add_message(TranscriptionRole.ASSISTANT, response_text)

    await ws.send_json({"type": "status", "text": "Sintetizando voz..."})
    audio_pcm = await tts.synthesize(response_text)

    await ws.send_json({
        "type": "response",
        "text": response_text,
        "audio": base64.b64encode(_wrap_wav(audio_pcm)).decode(),
    })


# ── HTML (Duralux Admin layout) ──────────────────────────────────────────────

_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Bot de Prueba — Voice Bot CRM</title>
<link rel="stylesheet" href="/static/assets/vendors/css/vendors.min.css"/>
<link rel="stylesheet" href="/static/assets/css/bootstrap.min.css"/>
<link rel="stylesheet" href="/static/assets/css/theme.min.css"/>
<style>
/* ── call bubbles ── */
.bubble{animation:fade .3s}
.bubble .lbl{font-size:10px;opacity:.6;text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px}
@keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}

/* ── call button ── */
.call-btn{
  width:80px;height:80px;border-radius:50%;border:none;cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  font-size:32px;color:#fff;
  transition:transform .15s,box-shadow .25s;
  box-shadow:0 4px 16px rgba(0,0,0,.25);
}
.call-btn:hover:not(:disabled){transform:scale(1.06)}
.call-btn:disabled{opacity:.5;cursor:not-allowed}
.call-btn.start{background:linear-gradient(135deg,#10b981,#059669)}
.call-btn.end{background:linear-gradient(135deg,#dc2626,#991b1b)}

/* listening pulse */
.listening{position:relative}
.listening::before{
  content:'';position:absolute;inset:-6px;border-radius:50%;
  border:2px solid #10b981;opacity:.6;
  animation:ring 1.4s ease-out infinite;
}
@keyframes ring{0%{transform:scale(.95);opacity:.7}100%{transform:scale(1.35);opacity:0}}

/* messages area */
#msgs{height:380px;overflow-y:auto;display:flex;flex-direction:column;gap:10px;padding:4px 0;}
#msgs::-webkit-scrollbar{width:4px}
#msgs::-webkit-scrollbar-thumb{background:#dee2e6;border-radius:2px}
</style>
</head>
<body>

<!-- SIDEBAR -->
<nav class="nxl-navigation">
  <div class="navbar-wrapper">
    <div class="m-header">
      <a href="http://localhost:8001/calls/dashboard/" class="b-brand">
        <span class="nxl-mtext fw-bold fs-5">Voice Bot</span>
      </a>
    </div>
    <div class="navbar-content">
      <ul class="nxl-navbar">
        <li class="nxl-item nxl-caption"><label>Navegación</label></li>

        <li class="nxl-item">
          <a href="http://localhost:8001/calls/dashboard/" class="nxl-link">
            <span class="nxl-micon"><i class="feather-monitor"></i></span>
            <span class="nxl-mtext">Dashboard</span>
          </a>
        </li>

        <li class="nxl-item nxl-hasmenu">
          <a href="javascript:void(0);" class="nxl-link">
            <span class="nxl-micon"><i class="feather-phone-incoming"></i></span>
            <span class="nxl-mtext">Llamadas</span>
            <span class="nxl-arrow"><i class="feather-chevron-right"></i></span>
          </a>
          <ul class="nxl-submenu">
            <li class="nxl-item"><a class="nxl-link" href="http://localhost:8001/calls/">Lista de llamadas</a></li>
          </ul>
        </li>

        <li class="nxl-item nxl-hasmenu">
          <a href="javascript:void(0);" class="nxl-link">
            <span class="nxl-micon"><i class="feather-layers"></i></span>
            <span class="nxl-mtext">Lotes</span>
            <span class="nxl-arrow"><i class="feather-chevron-right"></i></span>
          </a>
          <ul class="nxl-submenu">
            <li class="nxl-item"><a class="nxl-link" href="http://localhost:8001/batch/">Ver lotes</a></li>
            <li class="nxl-item"><a class="nxl-link" href="http://localhost:8001/batch/nuevo/">Nuevo lote</a></li>
          </ul>
        </li>

        <li class="nxl-item nxl-hasmenu">
          <a href="javascript:void(0);" class="nxl-link">
            <span class="nxl-micon"><i class="feather-code"></i></span>
            <span class="nxl-mtext">Scripts</span>
            <span class="nxl-arrow"><i class="feather-chevron-right"></i></span>
          </a>
          <ul class="nxl-submenu">
            <li class="nxl-item"><a class="nxl-link" href="http://localhost:8001/scripts/">Ver scripts</a></li>
            <li class="nxl-item"><a class="nxl-link" href="http://localhost:8001/scripts/nuevo/">Nuevo script</a></li>
          </ul>
        </li>

        <li class="nxl-item nxl-hasmenu">
          <a href="javascript:void(0);" class="nxl-link">
            <span class="nxl-micon"><i class="feather-target"></i></span>
            <span class="nxl-mtext">Campañas</span>
            <span class="nxl-arrow"><i class="feather-chevron-right"></i></span>
          </a>
          <ul class="nxl-submenu">
            <li class="nxl-item"><a class="nxl-link" href="http://localhost:8001/campaigns/">Ver campañas</a></li>
            <li class="nxl-item"><a class="nxl-link" href="http://localhost:8001/campaigns/nueva/">Nueva campaña</a></li>
          </ul>
        </li>

        <li class="nxl-item nxl-caption"><label>Herramientas</label></li>

        <li class="nxl-item nxl-active">
          <a href="/test/" class="nxl-link">
            <span class="nxl-micon"><i class="feather-mic"></i></span>
            <span class="nxl-mtext">Bot de Prueba</span>
          </a>
        </li>
      </ul>
    </div>
  </div>
</nav>

<!-- HEADER -->
<header class="nxl-header">
  <div class="header-wrapper">
    <div class="header-left d-flex align-items-center gap-4">
      <div class="nxl-navigation-toggle">
        <a href="javascript:void(0);" id="menu-mini-button"><i class="feather-align-left"></i></a>
      </div>
    </div>
    <div class="header-right ms-auto d-flex align-items-center gap-3">
      <span id="chip" class="badge bg-secondary">Sin conectar</span>
      <span class="d-flex align-items-center gap-1">
        <span class="dot" id="dot" style="width:9px;height:9px;border-radius:50%;background:#6c757d;transition:background .3s;display:inline-block;"></span>
      </span>
    </div>
  </div>
</header>

<!-- MAIN CONTENT -->
<main class="nxl-container">
  <div class="nxl-content">
    <div class="page-header">
      <div class="page-header-left d-flex align-items-center">
        <div class="page-header-title">
          <h5 class="m-b-10">Bot de Prueba</h5>
        </div>
        <ul class="breadcrumb">
          <li class="breadcrumb-item"><a href="http://localhost:8001/calls/dashboard/">Home</a></li>
          <li class="breadcrumb-item active">Bot de Prueba</li>
        </ul>
      </div>
    </div>

    <div class="main-content">
      <div class="row g-3">

        <!-- Chat messages -->
        <div class="col-xl-8">
          <div class="card h-100">
            <div class="card-header d-flex justify-content-between align-items-center">
              <h6 class="mb-0"><i class="feather-message-circle me-2"></i>Conversación</h6>
              <span id="chip2" class="badge bg-secondary">Sin conectar</span>
            </div>
            <div class="card-body">
              <div id="msgs">
                <div class="text-center text-muted small fst-italic py-4">Presiona el botón verde para iniciar la llamada.</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Call control -->
        <div class="col-xl-4">
          <div class="card">
            <div class="card-header"><h6 class="mb-0"><i class="feather-phone me-2"></i>Control de llamada</h6></div>
            <div class="card-body d-flex flex-column align-items-center gap-4 py-5">
              <button class="call-btn start" id="call">📞</button>
              <div id="hint" class="text-muted small text-center"><b>Iniciar llamada</b></div>
              <div class="text-muted" style="font-size:11px;">
                El bot usará el micrófono de tu computador.<br>
                Habla cuando el botón pulse en verde.
              </div>
            </div>
          </div>

          <!-- Script cargado -->
          <div class="card mt-3">
            <div class="card-header"><h6 class="mb-0"><i class="feather-file-text me-2"></i>Script activo</h6></div>
            <div class="card-body p-3">
              <div id="script-card-loaded" style="display:none;">
                <div class="d-flex align-items-center gap-2 mb-2">
                  <span class="badge bg-success">Cargado</span>
                  <strong id="loaded-script-name" style="font-size:0.9rem;"></strong>
                </div>
                <button type="button" class="btn btn-sm btn-outline-secondary w-100" id="unload-script">
                  <i class="feather-x me-1"></i>Quitar script
                </button>
              </div>
              <div id="script-card-empty">
                <p class="text-muted small mb-2 text-center">Sin script cargado</p>
                <a href="http://localhost:8001/scripts/" class="btn btn-sm btn-outline-primary w-100">
                  <i class="feather-list me-1"></i>Seleccionar script
                </a>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  </div>
</main>

<script>
// ── globals ────────────────────────────────────────────────────────────────
const proto    = location.protocol === 'https:' ? 'wss' : 'ws';
const WS_URL   = `${proto}://${location.host}/test/ws`;
const TARGET_RATE = 16000;
const SILENCE_DB        = -50;      // umbral en dBFS para considerar silencio
const SILENCE_MS_TO_END = 900;      // ms de silencio para cortar el turno
const MIN_SPEECH_MS     = 350;      // mínimo ms de voz para enviar

const msgsEl  = document.getElementById('msgs');
const chipEl  = document.getElementById('chip');
const dotEl   = document.getElementById('dot');
const callBtn = document.getElementById('call');
const hintEl  = document.getElementById('hint');
const scriptCardLoaded = document.getElementById('script-card-loaded');
const scriptCardEmpty = document.getElementById('script-card-empty');
const loadedScriptNameEl = document.getElementById('loaded-script-name');
const unloadScriptBtn = document.getElementById('unload-script');

let ws          = null;
let audioCtx    = null;
let workletNode = null;
let mediaStream = null;
let inCall      = false;       // call active
let listening   = false;       // currently capturing user speech
let speaking    = false;       // bot is currently playing audio
let speechMs    = 0;           // accumulated speech duration this turn
let silenceMs   = 0;           // accumulated silence
let loadedScriptId = null;     // ID of loaded script
let loadedScriptName = null;   // Name of loaded script

// ── Manejo de script cargado ────────────────────────────────────────────────
function updateLoadedScriptDisplay() {
  const params = new URLSearchParams(window.location.search);
  const scriptId = params.get('script_id');
  const scriptName = params.get('script_name');

  if (scriptId && scriptName) {
    loadedScriptId = scriptId;
    loadedScriptName = decodeURIComponent(scriptName);
    loadedScriptNameEl.textContent = loadedScriptName;
    scriptCardLoaded.style.display = 'block';
    scriptCardEmpty.style.display = 'none';
    console.log('✅ Script en URL:', {scriptId, scriptName: loadedScriptName});
  } else {
    loadedScriptId = null;
    loadedScriptName = null;
    scriptCardLoaded.style.display = 'none';
    scriptCardEmpty.style.display = 'block';
    console.log('⚠️ Sin script en URL');
  }
}

unloadScriptBtn.addEventListener('click', () => { window.location.href = '/test/'; });

// Ejecutar inmediatamente (no esperar DOMContentLoaded porque el script es inline al final del body)
updateLoadedScriptDisplay();

// ── AudioWorklet processor (inline blob) ───────────────────────────────────
function makeProcessorURL() {
  const code = `
class PCMRecorder extends AudioWorkletProcessor {
  constructor() {
    super();
    this._chunks  = [];
    this._on      = false;
    this._frameMs = (128 / sampleRate) * 1000;  // ~2.67 ms at 48kHz
    this.port.onmessage = (e) => {
      if (e.data === 'start') { this._on = true; this._chunks = []; return; }
      if (e.data === 'stop')  {
        this._on = false;
        const total = this._chunks.reduce((n,c) => n + c.length, 0);
        const out   = new Int16Array(total);
        let off = 0;
        for (const c of this._chunks) { out.set(c, off); off += c.length; }
        this.port.postMessage({ kind: 'audio', data: out.buffer }, [out.buffer]);
        this._chunks = [];
      }
    };
  }
  process(inputs) {
    if (!this._on || !inputs[0].length) return true;
    const src = inputs[0][0];                  // Float32 mono
    // dBFS for the frame
    let sumSq = 0;
    for (let i = 0; i < src.length; i++) sumSq += src[i] * src[i];
    const rms  = Math.sqrt(sumSq / src.length) || 1e-9;
    const dbfs = 20 * Math.log10(rms);

    // downsample to 16 kHz
    const ratio = sampleRate / 16000;
    const len   = Math.floor(src.length / ratio);
    const out   = new Int16Array(len);
    for (let i = 0; i < len; i++) {
      const s = Math.max(-1, Math.min(1, src[Math.floor(i * ratio)]));
      out[i]  = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    this._chunks.push(out);

    this.port.postMessage({ kind: 'level', dbfs, ms: this._frameMs });
    return true;
  }
}
registerProcessor('pcm-recorder', PCMRecorder);
`;
  return URL.createObjectURL(new Blob([code], { type: 'application/javascript' }));
}

async function ensureAudio() {
  if (audioCtx) return;
  audioCtx = new AudioContext({ sampleRate: 48000 });
  await audioCtx.audioWorklet.addModule(makeProcessorURL());
}

// ── recording (continuous, VAD on the client) ──────────────────────────────
async function startListening() {
  if (listening || speaking) return;
  if (!mediaStream) {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: { noiseSuppression: true, echoCancellation: true }, video: false });
  }
  if (!workletNode) {
    const src   = audioCtx.createMediaStreamSource(mediaStream);
    workletNode = new AudioWorkletNode(audioCtx, 'pcm-recorder');
    workletNode.port.onmessage = onWorkletMessage;
    src.connect(workletNode);
    workletNode.connect(audioCtx.destination);
  }
  speechMs  = 0;
  silenceMs = 0;
  listening = true;
  workletNode.port.postMessage('start');
  setChip('Escuchándote…');
  callBtn.classList.add('listening');
}

function stopListening(send) {
  if (!listening) return;
  listening = false;
  callBtn.classList.remove('listening');
  if (workletNode) workletNode.port.postMessage('stop');  // worklet will post the buffered audio
  if (!send) {
    // worklet will still send; we drop on receive if needed
    droppingNextBuffer = true;
  }
}

let droppingNextBuffer = false;

function onWorkletMessage(e) {
  const d = e.data;
  if (d.kind === 'level') {
    if (!listening) return;
    if (d.dbfs > SILENCE_DB) {
      speechMs += d.ms;
      silenceMs = 0;
    } else if (speechMs > 0) {
      silenceMs += d.ms;
      if (silenceMs >= SILENCE_MS_TO_END && speechMs >= MIN_SPEECH_MS) {
        // user finished speaking → cut and send
        stopListening(true);
      }
    }
    return;
  }
  if (d.kind === 'audio') {
    if (droppingNextBuffer) { droppingNextBuffer = false; return; }
    if (ws?.readyState === WebSocket.OPEN && speechMs >= MIN_SPEECH_MS) {
      ws.send(d.data);
      setChip('Enviando audio…');
    } else {
      // not enough speech — keep listening
      if (inCall && !speaking) startListening();
    }
  }
}

// ── audio playback ─────────────────────────────────────────────────────────
async function playWav(b64) {
  if (!b64) return;
  await ensureAudio();
  if (audioCtx.state === 'suspended') await audioCtx.resume();
  const raw = atob(b64);
  const buf = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) buf[i] = raw.charCodeAt(i);
  const ab  = await audioCtx.decodeAudioData(buf.buffer);

  speaking = true;
  setChip('Asistente hablando…');
  const node = audioCtx.createBufferSource();
  node.buffer = ab;
  node.connect(audioCtx.destination);
  await new Promise(res => { node.onended = res; node.start(); });
  speaking = false;
  if (inCall) startListening();
}

// ── UI helpers ─────────────────────────────────────────────────────────────
function addMsg(role, text) {
  const d = document.createElement('div');
  d.className = 'bubble mb-2';
  if (role === 'bot') {
    d.innerHTML = `<div class="lbl text-primary">Asistente</div><div class="bg-light rounded p-2 d-inline-block" style="max-width:85%;font-size:14px;">${text}</div>`;
  } else if (role === 'user') {
    d.className += ' text-end';
    d.innerHTML = `<div class="lbl text-secondary">Tú</div><div class="bg-primary text-white rounded p-2 d-inline-block" style="max-width:85%;font-size:14px;">${text}</div>`;
  } else {
    d.innerHTML = `<div class="text-center text-muted small fst-italic">${text}</div>`;
  }
  msgsEl.appendChild(d);
  msgsEl.scrollTop = msgsEl.scrollHeight;
}

function setChip(t) {
  chipEl.textContent = t;
  const c2 = document.getElementById('chip2');
  if (c2) c2.textContent = t;
}

function setButtonState(state) {
  if (state === 'start') {
    callBtn.classList.remove('end','listening');
    callBtn.classList.add('start');
    callBtn.textContent = '📞';
    hintEl.innerHTML = '<b>Iniciar llamada</b>';
  } else {
    callBtn.classList.remove('start','listening');
    callBtn.classList.add('end');
    callBtn.textContent = '⏹';
    hintEl.innerHTML = '<b>Colgar</b>';
  }
}

// ── call lifecycle ─────────────────────────────────────────────────────────
async function startCall() {
  if (inCall) return;
  callBtn.disabled = true;
  try {
    await ensureAudio();
    if (audioCtx.state === 'suspended') await audioCtx.resume();
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: { noiseSuppression: true, echoCancellation: true }, video: false });
  } catch (e) {
    addMsg('sys', '⚠ No se pudo acceder al micrófono: ' + e.message);
    callBtn.disabled = false;
    return;
  }
  inCall = true;
  setButtonState('end');
  setChip('Conectando…');
  connect();
}

function endCall() {
  inCall = false;
  listening = false;
  speaking  = false;
  if (workletNode) { workletNode.disconnect(); workletNode = null; }
  if (mediaStream) { mediaStream.getTracks().forEach(t => t.stop()); mediaStream = null; }
  if (ws && ws.readyState === WebSocket.OPEN) ws.close(1000, 'user_hangup');
  ws = null;
  setButtonState('start');
  setChip('Llamada finalizada');
  dotEl.classList.remove('ok');
  addMsg('sys', '— Fin de la llamada —');
  callBtn.disabled = false;
}

callBtn.addEventListener('click', () => {
  if (inCall) endCall();
  else        startCall();
});

// ── websocket ──────────────────────────────────────────────────────────────
function connect() {
  ws = new WebSocket(WS_URL);
  ws.binaryType = 'arraybuffer';

  ws.onopen = () => {
    dotEl.style.background = '#10b981';
    dotEl.style.boxShadow = '0 0 8px #10b981';
    chipEl.className = 'badge bg-success';
    const c2 = document.getElementById('chip2'); if(c2) c2.className = 'badge bg-success';
    setChip('Conectado');
    callBtn.disabled = false;

    // Enviar script cargado si existe (leer de URL)
    const params = new URLSearchParams(window.location.search);
    const scriptId = params.get('script_id');
    const scriptName = params.get('script_name');
    if (scriptId && scriptName) {
      console.log('✅ Enviando script al servidor:', {scriptId, scriptName});
      ws.send(JSON.stringify({
        type: 'load_script',
        script_id: scriptId,
        script_name: scriptName
      }));
    } else {
      console.log('⚠️ Sin script en URL - usando perfil predeterminado');
    }
  };

  ws.onmessage = async (ev) => {
    let d;
    try { d = JSON.parse(ev.data); }
    catch { return; }

    switch (d.type) {
      case 'greeting':
        addMsg('bot', d.text);
        await playWav(d.audio);
        break;
      case 'status':
        setChip(d.text);
        break;
      case 'transcript':
        addMsg('user', d.text);
        break;
      case 'response':
        addMsg('bot', d.text);
        await playWav(d.audio);
        break;
      case 'ready':
        if (inCall && !speaking) startListening();
        break;
      case 'error':
        addMsg('sys', '⚠ ' + d.message);
        setChip('Error');
        if (inCall && !speaking) startListening();
        break;
    }
  };

  ws.onclose = (ev) => {
    dotEl.style.background = '#6c757d';
    dotEl.style.boxShadow = 'none';
    if (inCall) {
      addMsg('sys', `Conexión cerrada (${ev.code}). Finalizando llamada…`);
      endCall();
    }
  };

  ws.onerror = () => {
    setChip('Error de conexión');
    dotEl.style.background = '#dc3545';
  };
}
</script>
<script src="/static/assets/vendors/js/vendors.min.js"></script>
<script src="/static/assets/js/common-init.min.js"></script>
</body>
</html>
"""
