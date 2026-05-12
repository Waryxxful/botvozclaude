from datetime import timedelta

from google.cloud import storage


def generate_signed_url(gcs_url: str, expires_minutes: int = 60) -> str:
    if not gcs_url.startswith("gs://"):
        raise ValueError(f"Not a GCS URL: {gcs_url}")
    path = gcs_url[len("gs://"):]
    bucket_name, _, object_name = path.partition("/")
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=expires_minutes),
        method="GET",
    )
