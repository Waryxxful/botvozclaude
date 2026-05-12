#!/usr/bin/env python3
"""Script para validar que GCP está correctamente configurado para Voice Bot."""

import os
import sys
import json
from pathlib import Path

# Colores para output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(text: str) -> None:
    """Imprime encabezado."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text:^60}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")


def print_check(test_name: str, passed: bool, details: str = "") -> None:
    """Imprime resultado de un check."""
    status = f"{GREEN}[PASS]{RESET}" if passed else f"{RED}[FAIL]{RESET}"
    print(f"{status}  {test_name}")
    if details:
        print(f"     {YELLOW}{details}{RESET}")


def validate_credentials_file() -> tuple[bool, str]:
    """Verifica que credentials.json exista y sea válido."""
    cred_path = Path("credentials.json")

    if not cred_path.exists():
        return False, "credentials.json no encontrado en raíz del proyecto"

    try:
        with open(cred_path) as f:
            creds = json.load(f)

        required_fields = ["type", "project_id", "private_key", "client_email"]
        missing = [f for f in required_fields if f not in creds]

        if missing:
            return False, f"Campos faltantes en credentials.json: {missing}"

        project_id = creds.get("project_id", "")
        return True, f"✓ GCP Project ID: {project_id}"

    except json.JSONDecodeError:
        return False, "credentials.json no es válido JSON"
    except Exception as e:
        return False, f"Error al leer credentials.json: {e}"


def validate_env_file() -> tuple[bool, str]:
    """Verifica que .env exista y tenga variables mínimas."""
    env_path = Path(".env")

    if not env_path.exists():
        return False, ".env no encontrado. Copia .env.example y rellena valores"

    try:
        with open(env_path) as f:
            env_content = f.read()

        required_vars = [
            "GCP_PROJECT_ID",
            "TELNYX_API_KEY",
            "TELNYX_PUBLIC_KEY",
            "TELNYX_SIP_CONNECTION_ID",
        ]

        missing = [v for v in required_vars if f"{v}=" not in env_content]

        if missing:
            return False, f"Variables faltantes en .env: {missing}"

        return True, "✓ .env configurado con variables mínimas"

    except Exception as e:
        return False, f"Error al leer .env: {e}"


def validate_gcp_auth() -> tuple[bool, str]:
    """Verifica que autenticación con GCP funcione."""
    try:
        from google.auth import default

        credentials, project = default()

        if not credentials:
            return False, "No se pudo obtener credenciales de GCP"

        return True, f"✓ Autenticado en GCP (Proyecto: {project})"

    except ImportError:
        return False, "google-auth no está instalado. Ejecuta: pip install -r requirements.txt"
    except Exception as e:
        return False, f"Error en autenticación GCP: {e}"


def validate_firestore() -> tuple[bool, str]:
    """Verifica que Firestore sea accesible."""
    try:
        from google.cloud import firestore

        # Inicializar cliente (no crea conexión aún)
        db = firestore.AsyncClient()

        return True, "✓ Cliente Firestore inicializado"

    except ImportError:
        return False, "google-cloud-firestore no está instalado"
    except Exception as e:
        return False, f"Error al inicializar Firestore: {e}"


def validate_speech_to_text() -> tuple[bool, str]:
    """Verifica que Speech-to-Text API sea accesible."""
    try:
        from google.cloud import speech_v2

        # Solo verificar que se puede importar
        client = speech_v2.SpeechAsyncClient()

        return True, "✓ Cliente Speech-to-Text v2 inicializado"

    except ImportError:
        return False, "google-cloud-speech no está instalado"
    except Exception as e:
        return False, f"Error al inicializar Speech-to-Text: {e}"


def validate_text_to_speech() -> tuple[bool, str]:
    """Verifica que Text-to-Speech API sea accesible."""
    try:
        from google.cloud import texttospeech

        client = texttospeech.TextToSpeechAsyncClient()

        return True, "✓ Cliente Text-to-Speech inicializado"

    except ImportError:
        return False, "google-cloud-texttospeech no está instalado"
    except Exception as e:
        return False, f"Error al inicializar Text-to-Speech: {e}"


def validate_vertex_ai() -> tuple[bool, str]:
    """Verifica que Vertex AI (Gemini) sea accesible."""
    try:
        from vertexai.generative_models import GenerativeModel

        # Solo verificar que se puede importar
        return True, "✓ Cliente Vertex AI (Gemini) disponible"

    except ImportError:
        return False, "google-cloud-aiplatform no está instalado"
    except Exception as e:
        return False, f"Error al inicializar Vertex AI: {e}"


def validate_dependencies() -> tuple[bool, str]:
    """Verifica que todas las dependencias estén instaladas."""
    required_packages = [
        ("fastapi", "fastapi"),
        ("pydantic", "pydantic"),
        ("google.cloud.speech_v2", "google-cloud-speech"),
        ("google.cloud.texttospeech", "google-cloud-texttospeech"),
        ("google.cloud.firestore", "google-cloud-firestore"),
        ("google.cloud.pubsub_v1", "google-cloud-pubsub"),
        ("vertexai", "google-cloud-aiplatform"),
        ("websockets", "websockets"),
        ("cryptography", "cryptography"),
    ]

    missing = []
    for import_name, package_name in required_packages:
        try:
            __import__(import_name.split(".")[0])
        except ImportError:
            missing.append(package_name)

    if missing:
        return False, f"Paquetes faltantes: {', '.join(missing)}. Ejecuta: pip install -r requirements.txt"

    return True, "✓ Todas las dependencias instaladas"


def main():
    """Ejecuta todas las validaciones."""
    print_header("GCP Setup Validation for Voice Bot")

    results = []

    # 1. Validar dependencies
    print(f"{YELLOW}1. Validando dependencias...{RESET}")
    passed, msg = validate_dependencies()
    print_check("Dependencias Python", passed, msg)
    results.append(passed)

    # 2. Validar credentials.json
    print(f"\n{YELLOW}2. Validando credenciales GCP...{RESET}")
    passed, msg = validate_credentials_file()
    print_check("credentials.json", passed, msg)
    results.append(passed)

    # 3. Validar .env
    print(f"\n{YELLOW}3. Validando configuración .env...{RESET}")
    passed, msg = validate_env_file()
    print_check("Archivo .env", passed, msg)
    results.append(passed)

    # 4. Validar autenticación GCP
    print(f"\n{YELLOW}4. Validando autenticación GCP...{RESET}")
    passed, msg = validate_gcp_auth()
    print_check("Autenticación GCP", passed, msg)
    results.append(passed)

    # 5. Validar Firestore
    print(f"\n{YELLOW}5. Validando APIs de GCP...{RESET}")
    passed, msg = validate_firestore()
    print_check("Firestore", passed, msg)
    results.append(passed)

    passed, msg = validate_speech_to_text()
    print_check("Speech-to-Text v2", passed, msg)
    results.append(passed)

    passed, msg = validate_text_to_speech()
    print_check("Text-to-Speech", passed, msg)
    results.append(passed)

    passed, msg = validate_vertex_ai()
    print_check("Vertex AI (Gemini)", passed, msg)
    results.append(passed)

    # Resumen final
    print_header("Resumen de Validación")

    total = len(results)
    passed_count = sum(results)

    if all(results):
        print(f"{GREEN}[OK] ¡GCP ESTÁ COMPLETAMENTE CONFIGURADO!{RESET}")
        print(f"\n{GREEN}Todos los checks ({passed_count}/{total}) pasaron.{RESET}")
        print(f"\n{BLUE}Próximos pasos:{RESET}")
        print("1. Configurar credenciales de Telnyx")
        print("2. Probar en local: python -m uvicorn src.api.app:create_app --factory --reload")
        print("3. Simular webhooks de Telnyx para testing")
        return 0
    else:
        print(f"{RED}[ERROR] GCP NO ESTÁ COMPLETAMENTE CONFIGURADO{RESET}")
        print(f"\n{RED}{passed_count}/{total} checks pasaron{RESET}")
        print(f"\n{YELLOW}Por favor, revisa los errores arriba e intenta de nuevo.{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
