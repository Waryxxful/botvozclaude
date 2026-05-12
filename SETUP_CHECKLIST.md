# ✅ Voice Bot Setup Checklist

## 1️⃣ GCP Configuration

- [ ] **Crear proyecto GCP** (si no lo hiciste)
  - Ir a: https://console.cloud.google.com
  - Crear nuevo proyecto

- [ ] **Habilitar APIs en GCP**
  - Cloud Speech-to-Text v2
  - Cloud Text-to-Speech
  - Vertex AI APIs
  - Firestore
  - Pub/Sub

- [ ] **Crear Service Account**
  - Ir a: IAM y administración → Cuentas de servicio
  - Crear cuenta: `voicebot-sa`
  - Roles: Firestore Editor, Pub/Sub Editor, Speech-to-Text Viewer, Text-to-Speech Viewer, Vertex AI User

- [ ] **Descargar credentials.json**
  - Ir a: https://console.cloud.google.com/iam-admin/serviceaccounts
  - Click en `voicebot-sa`
  - Pestaña "Claves" → "Agregar clave" → "JSON"
  - Guardar como: `C:\Users\tomas\Desktop\trabajo\botvoz\BOT_VOZ\credentials.json`

## 2️⃣ Telnyx Configuration

- [ ] **Crear cuenta Telnyx**
  - Ir a: https://telnyx.com/sign-up
  - Registrate y completa el perfil

- [ ] **Comprar número telefónico**
  - En dashboard → Numbers → Buy Numbers
  - Elegir región (España: +34)
  - Comprar número

- [ ] **Crear SIP Connection para Media Streaming**
  - Dashboard → Connections → SIP Connections
  - Click "Create Connection"
  - Nombre: `voicebot-connection`
  - Habilitar Inbound Settings

- [ ] **Obtener credenciales Telnyx**
  - API Keys → Copiar API Key v2 → `TELNYX_API_KEY`
  - Public Key → Copiar → `TELNYX_PUBLIC_KEY`
  - SIP Connection ID → Copiar → `TELNYX_SIP_CONNECTION_ID`
  - Pegar en `.env`

- [ ] **Configurar Webhook**
  - (Luego cuando despliegues a Cloud Run)
  - URL: `https://tu-cloud-run-url/webhooks/telnyx`
  - Events: call.initiated, call.answered, call.hangup

## 3️⃣ Configuración Local

- [ ] **Instalar dependencias**
  ```bash
  pip install -r requirements.txt
  ```

- [ ] **Archivo .env**
  - `.env` ya está creado ✓
  - Solo rellena: `TELNYX_API_KEY`, `TELNYX_PUBLIC_KEY`, `TELNYX_SIP_CONNECTION_ID`

- [ ] **Validar setup**
  ```bash
  python scripts/validate_gcp_setup.py
  ```
  - Debería mostrar: [OK] ¡GCP ESTÁ COMPLETAMENTE CONFIGURADO!

## 4️⃣ Testing Local (Opcional)

- [ ] **Iniciar la app**
  ```bash
  python -m uvicorn src.api.app:create_app --factory --reload
  ```

- [ ] **Simular webhook de Telnyx**
  ```bash
  python scripts/simulate_telnyx_webhook.py
  ```

- [ ] **Verificar logs**
  - Debería ver eventos de inicio/fin de llamada

## 5️⃣ Deployment a Cloud Run

- [ ] **Configurar secrets en GCP**
  - Telnyx API keys en Secret Manager

- [ ] **Deploy**
  ```bash
  gcloud builds submit --config cloudbuild.yaml
  ```

- [ ] **Configurar webhook real en Telnyx**
  - URL: `https://tu-cloud-run-url/webhooks/telnyx`

- [ ] **Hacer llamada de prueba**
  - Llamar a tu número Telnyx
  - El bot debería responder

---

## 📊 Estado Actual

```
GCP:        ✅ Configurado (solo falta descargar credentials.json)
Telnyx:     ❌ Falta completar
Local:      ⏳ Listo después de .env + dependencias
```

## 🎯 Próximo Paso

1. Descarga `credentials.json` (5 minutos)
2. Rellena Telnyx en `.env` (2 minutos)
3. Ejecuta: `python scripts/validate_gcp_setup.py`
4. ✅ ¡Listo para probar!
