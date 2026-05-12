import base64
import struct
import uuid
import structlog
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
        tts = _get_tts()
        llm = _get_llm()
    except Exception as exc:
        logger.error("test_client_init_failed", error=str(exc))
        await websocket.send_json({"type": "error", "message": f"No se pudieron iniciar los clientes GCP: {exc}"})
        await websocket.close()
        return

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


# ── HTML (voice-only single-button UI) ───────────────────────────────────────

_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Voice Bot — Llamada de prueba</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,-apple-system,sans-serif;
     background:linear-gradient(135deg,#0f1117 0%,#1a1f2e 100%);
     color:#e2e8f0;height:100dvh;display:flex;flex-direction:column;overflow:hidden}

/* ── header ── */
header{padding:16px 24px;border-bottom:1px solid #1e2130;display:flex;align-items:center;gap:10px;flex-shrink:0}
.dot{width:9px;height:9px;border-radius:50%;background:#374151;transition:background .3s}
.dot.ok{background:#10b981;box-shadow:0 0 8px #10b981}
h1{font-size:16px;font-weight:600;color:#f1f5f9;flex:1}
#chip{font-size:11px;color:#94a3b8;background:#1e293b;padding:3px 10px;border-radius:20px;white-space:nowrap}

/* ── messages ── */
#msgs{flex:1;overflow-y:auto;padding:24px;display:flex;flex-direction:column;gap:10px}
.bubble{max-width:78%;padding:11px 15px;border-radius:14px;font-size:14px;line-height:1.55;animation:fade .3s}
.bubble .lbl{font-size:10px;margin-bottom:4px;opacity:.6;text-transform:uppercase;letter-spacing:.06em}
.bubble.bot{background:#1e293b;align-self:flex-start;border-bottom-left-radius:3px}
.bubble.user{background:#1d4ed8;align-self:flex-end;border-bottom-right-radius:3px}
.bubble.sys{background:transparent;align-self:center;font-size:12px;color:#64748b;font-style:italic;max-width:90%;text-align:center}
@keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}

/* ── call control area ── */
#control{padding:24px;border-top:1px solid #1e2130;display:flex;flex-direction:column;align-items:center;gap:14px;flex-shrink:0;background:#0a0d14}

.call-btn{
  width:84px;height:84px;border-radius:50%;border:none;cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  font-size:34px;color:#fff;
  transition:transform .15s,box-shadow .25s;
  box-shadow:0 4px 16px rgba(0,0,0,.4);
}
.call-btn:hover:not(:disabled){transform:scale(1.05)}
.call-btn:disabled{opacity:.5;cursor:not-allowed}

.call-btn.start{background:linear-gradient(135deg,#10b981 0%,#059669 100%)}
.call-btn.end{background:linear-gradient(135deg,#dc2626 0%,#991b1b 100%)}

#hint{font-size:12px;color:#64748b;letter-spacing:.02em}
#hint b{color:#cbd5e1}

/* listening pulse */
.listening{position:relative}
.listening::before{
  content:'';position:absolute;inset:-6px;border-radius:50%;
  border:2px solid #10b981;opacity:.6;
  animation:ring 1.4s ease-out infinite;
}
@keyframes ring{
  0%{transform:scale(.95);opacity:.7}
  100%{transform:scale(1.35);opacity:0}
}

/* scrollbar */
#msgs::-webkit-scrollbar{width:4px}
#msgs::-webkit-scrollbar-thumb{background:#1e293b;border-radius:2px}
</style>
</head>
<body>

<header>
  <div class="dot" id="dot"></div>
  <h1>Voice Bot &mdash; Llamada de prueba</h1>
  <div id="chip">Sin conectar</div>
</header>

<div id="msgs">
  <div class="bubble sys">Presiona el botón verde para iniciar la llamada.</div>
</div>

<div id="control">
  <button class="call-btn start" id="call">📞</button>
  <div id="hint"><b>Iniciar llamada</b></div>
</div>

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

let ws          = null;
let audioCtx    = null;
let workletNode = null;
let mediaStream = null;
let inCall      = false;       // call active
let listening   = false;       // currently capturing user speech
let speaking    = false;       // bot is currently playing audio
let speechMs    = 0;           // accumulated speech duration this turn
let silenceMs   = 0;           // accumulated silence

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
  d.className = `bubble ${role}`;
  if (role !== 'sys') {
    const lbl = document.createElement('div');
    lbl.className = 'lbl';
    lbl.textContent = role === 'bot' ? 'Asistente' : 'Tú';
    d.appendChild(lbl);
  }
  const p = document.createElement('p');
  p.textContent = text;
  d.appendChild(p);
  msgsEl.appendChild(d);
  msgsEl.scrollTop = msgsEl.scrollHeight;
}

function setChip(t) { chipEl.textContent = t; }

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
    dotEl.classList.add('ok');
    setChip('Conectado');
    callBtn.disabled = false;
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
    dotEl.classList.remove('ok');
    if (inCall) {
      addMsg('sys', `Conexión cerrada (${ev.code}). Finalizando llamada…`);
      endCall();
    }
  };

  ws.onerror = () => {
    setChip('Error de conexión');
  };
}
</script>
</body>
</html>
"""
