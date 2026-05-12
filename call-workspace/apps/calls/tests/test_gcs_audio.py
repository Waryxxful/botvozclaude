from unittest.mock import MagicMock, patch

from apps.calls.services.gcs_audio import generate_signed_url


@patch("apps.calls.services.gcs_audio.storage.Client")
def test_generate_signed_url_builds_correct_path(mock_client_cls):
    bucket = MagicMock()
    blob = MagicMock()
    blob.generate_signed_url.return_value = "https://signed/url"
    bucket.blob.return_value = blob
    client = MagicMock()
    client.bucket.return_value = bucket
    mock_client_cls.return_value = client

    result = generate_signed_url("gs://my-bucket/calls/abc.wav", expires_minutes=60)

    assert result == "https://signed/url"
    client.bucket.assert_called_once_with("my-bucket")
    bucket.blob.assert_called_once_with("calls/abc.wav")
