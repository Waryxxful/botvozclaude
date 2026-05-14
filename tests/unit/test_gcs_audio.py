from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
@patch("src.integrations.gcs_audio.storage.Client")
async def test_upload_returns_gcs_url(mock_client_cls, tmp_path):
    audio_file = tmp_path / "test.wav"
    audio_file.write_bytes(b"fake-wav-bytes")

    bucket = MagicMock()
    blob = MagicMock()
    bucket.blob.return_value = blob
    client = MagicMock()
    client.bucket.return_value = bucket
    mock_client_cls.return_value = client

    from src.integrations.gcs_audio import upload_call_audio
    url = await upload_call_audio(
        bucket_name="my-bucket",
        call_id="abc-123",
        local_path=str(audio_file),
    )
    assert url == "gs://my-bucket/calls/abc-123.wav"
    bucket.blob.assert_called_once_with("calls/abc-123.wav")
    blob.upload_from_filename.assert_called_once_with(str(audio_file), content_type="audio/wav")


@pytest.mark.asyncio
@patch("src.integrations.gcs_audio.storage.Client")
async def test_upload_raises_when_bucket_name_empty(mock_client_cls, tmp_path):
    f = tmp_path / "a.wav"
    f.write_bytes(b"x")
    from src.integrations.gcs_audio import upload_call_audio
    with pytest.raises(ValueError, match="bucket"):
        await upload_call_audio(bucket_name="", call_id="x", local_path=str(f))
