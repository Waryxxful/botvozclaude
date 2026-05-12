import os
import ssl
import sys
import tempfile

import certifi
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Push .env into os.environ so GCP SDKs (which read GOOGLE_APPLICATION_CREDENTIALS
# directly from the environment) can find the credentials.
load_dotenv()


def _build_ca_bundle() -> str:
    """Merge certifi roots with the Windows trust store (when on Windows).

    Needed when an antivirus/corporate proxy (e.g. Avast HTTPS scanning) is
    rewriting TLS certificates — certifi alone doesn't trust the interceptor's
    root, but Windows does. No-op on non-Windows: just returns certifi's path.
    """
    pem_chunks: list[bytes] = []
    with open(certifi.where(), "rb") as f:
        pem_chunks.append(f.read())

    if sys.platform == "win32":
        try:
            for store in ("ROOT", "CA"):
                for cert_der, _enc, _trust in ssl.enum_certificates(store):
                    pem_chunks.append(
                        ssl.DER_cert_to_PEM_cert(cert_der).encode()
                    )
        except Exception:
            pass  # fall back to certifi-only

    fd, path = tempfile.mkstemp(prefix="voicebot_ca_", suffix=".pem")
    with os.fdopen(fd, "wb") as f:
        for chunk in pem_chunks:
            f.write(chunk)
            f.write(b"\n")
    return path


_ca = _build_ca_bundle()
os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = _ca
os.environ["SSL_CERT_FILE"] = _ca
os.environ["REQUESTS_CA_BUNDLE"] = _ca


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # GCP
    gcp_project_id: str = Field(..., alias="GCP_PROJECT_ID")
    gcp_region: str = Field("us-central1", alias="GCP_REGION")
    google_application_credentials: str | None = Field(None, alias="GOOGLE_APPLICATION_CREDENTIALS")

    # Telnyx
    telnyx_api_key: str = Field(..., alias="TELNYX_API_KEY")
    telnyx_public_key: str = Field(..., alias="TELNYX_PUBLIC_KEY")
    telnyx_sip_connection_id: str = Field(..., alias="TELNYX_SIP_CONNECTION_ID")


    # Deepgram (optional - if not provided, use Google STT)
    deepgram_api_key: str | None = Field(None, alias="DEEPGRAM_API_KEY")

    # Bot
    bot_profile: str = Field("default", alias="BOT_PROFILE")
    bot_default_language: str = Field("es-419", alias="BOT_DEFAULT_LANGUAGE")
    bot_tts_voice: str = Field("es-US-Neural2-A", alias="BOT_TTS_VOICE")

    # Firestore
    firestore_calls_collection: str = Field("calls", alias="FIRESTORE_CALLS_COLLECTION")
    firestore_transcriptions_collection: str = Field("transcriptions", alias="FIRESTORE_TRANSCRIPTIONS_COLLECTION")
    firestore_customers_collection: str = Field("customers", alias="FIRESTORE_CUSTOMERS_COLLECTION")
    firestore_bot_profiles_collection: str = Field("bot_profiles", alias="FIRESTORE_BOT_PROFILES_COLLECTION")

    # Pub/Sub
    pubsub_topic_call_events: str = Field("voice-bot-call-events", alias="PUBSUB_TOPIC_CALL_EVENTS")

    # App
    app_host: str = Field("0.0.0.0", alias="APP_HOST")
    app_port: int = Field(8080, alias="APP_PORT")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    environment: str = Field("development", alias="ENVIRONMENT")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
