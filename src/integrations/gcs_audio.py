"""Upload recorded call audio to Google Cloud Storage."""

import asyncio

from google.cloud import storage


async def upload_call_audio(*, bucket_name: str, call_id: str, local_path: str) -> str:
    """Upload a WAV file to gs://<bucket_name>/calls/<call_id>.wav and return the gs:// URL."""
    if not bucket_name:
        raise ValueError("bucket_name is required")

    def _do_upload() -> str:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(f"calls/{call_id}.wav")
        blob.upload_from_filename(local_path, content_type="audio/wav")
        return f"gs://{bucket_name}/calls/{call_id}.wav"

    return await asyncio.to_thread(_do_upload)
