"""Carga el perfil de bot por defecto en Firestore."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()


async def main():
    from config.bot_config import load_bot_profile
    from src.persistence.firestore_client import get_firestore_client

    profile = load_bot_profile("default")
    firestore = get_firestore_client()

    doc_ref = firestore._client.collection(
        firestore._profiles_col
    ).document(profile.name)

    await doc_ref.set(profile.model_dump())
    print(f"✓ Perfil '{profile.name}' guardado en Firestore")
    await firestore.close()


if __name__ == "__main__":
    asyncio.run(main())
