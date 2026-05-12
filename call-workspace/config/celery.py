import os
from celery import Celery
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("callworkspace")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
