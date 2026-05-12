import ftplib
from pathlib import Path
from django.conf import settings


AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".mp4"}


class FTPClient:
    """Thin wrapper over ftplib.FTP / paramiko SFTP."""

    def __init__(self):
        self._conn = None
        self._ssh = None
        self._connect()

    def _connect(self):
        if settings.FTP_USE_SFTP:
            self._connect_sftp()
        else:
            self._connect_ftp()

    def _connect_ftp(self):
        conn = ftplib.FTP()
        conn.connect(settings.FTP_HOST, settings.FTP_PORT)
        conn.login(settings.FTP_USER, settings.FTP_PASSWORD)
        self._conn = conn

    def _connect_sftp(self):
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            settings.FTP_HOST,
            port=settings.FTP_PORT,
            username=settings.FTP_USER,
            password=settings.FTP_PASSWORD,
        )
        self._ssh = ssh
        self._conn = ssh.open_sftp()

    def list_audio_files(self, directory: str) -> list[tuple[str, str]]:
        """Return [(full_ftp_path, filename)] for audio files in directory."""
        results = []
        directory = directory.rstrip("/")

        if settings.FTP_USE_SFTP:
            for entry in self._conn.listdir_attr(directory):
                name = entry.filename
                if Path(name).suffix.lower() in AUDIO_EXTENSIONS:
                    results.append((f"{directory}/{name}", name))
        else:
            entries: list[str] = []
            try:
                self._conn.retrlines(f"NLST {directory}", entries.append)
            except ftplib.error_perm:
                return []
            for entry in entries:
                name = Path(entry).name
                if Path(name).suffix.lower() in AUDIO_EXTENSIONS:
                    results.append((f"{directory}/{name}", name))

        return results

    def download_file(self, ftp_path: str, campaign_id: int, filename: str) -> str:
        """Download file to media/audio/<campaign_id>/<filename>.
        Returns the path relative to MEDIA_ROOT."""
        dest_dir = Path(settings.MEDIA_ROOT) / "audio" / str(campaign_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        local_abs = dest_dir / filename

        if settings.FTP_USE_SFTP:
            self._conn.get(ftp_path, str(local_abs))
        else:
            with open(local_abs, "wb") as f:
                self._conn.retrbinary(f"RETR {ftp_path}", f.write)

        return str(Path("audio") / str(campaign_id) / filename)

    def close(self):
        try:
            if settings.FTP_USE_SFTP:
                self._conn.close()
                if self._ssh:
                    self._ssh.close()
            else:
                self._conn.quit()
        except Exception:
            pass
