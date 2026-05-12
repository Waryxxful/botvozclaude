#!/bin/bash
# Provisioning inicial de recursos GCP para el bot de voz
# Uso: bash scripts/setup_gcp.sh
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Variable GCP_PROJECT_ID requerida}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="voicebot"

echo "=== Configurando proyecto: $PROJECT_ID ==="

# Habilitar APIs necesarias
echo "→ Habilitando APIs GCP..."
gcloud services enable \
  speech.googleapis.com \
  texttospeech.googleapis.com \
  aiplatform.googleapis.com \
  firestore.googleapis.com \
  pubsub.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  --project="$PROJECT_ID"

# Crear Artifact Registry
echo "→ Creando Artifact Registry..."
gcloud artifacts repositories create voicebot \
  --repository-format=docker \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  --description="Voice bot Docker images" 2>/dev/null || echo "  (ya existe)"

# Crear Pub/Sub topic
echo "→ Creando Pub/Sub topic..."
gcloud pubsub topics create voice-bot-call-events \
  --project="$PROJECT_ID" 2>/dev/null || echo "  (ya existe)"

# Inicializar Firestore (modo nativo)
echo "→ Firestore debe estar en modo nativo. Verificar en consola si es necesario."

# Crear Service Account para Cloud Run
SA_NAME="voicebot-sa"
SA_EMAIL="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"

echo "→ Creando Service Account $SA_EMAIL..."
gcloud iam service-accounts create "$SA_NAME" \
  --display-name="Voice Bot Service Account" \
  --project="$PROJECT_ID" 2>/dev/null || echo "  (ya existe)"

# Asignar roles necesarios
echo "→ Asignando roles IAM..."
for ROLE in \
  roles/speech.client \
  roles/texttospeech.serviceAgent \
  roles/aiplatform.user \
  roles/datastore.user \
  roles/pubsub.publisher; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="$ROLE" \
    --quiet
done

echo ""
echo "=== Setup completado ==="
echo "Próximo paso: configurar TELNYX_SIP_CONNECTION_ID y LIVEKIT_URL en .env"
echo "Luego ejecutar: gcloud run deploy $SERVICE_NAME --source . --region $REGION --service-account $SA_EMAIL"
