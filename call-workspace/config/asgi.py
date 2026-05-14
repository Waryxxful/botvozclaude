import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

# Agregar la raíz de BOT_VOZ al path para importar src/
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent  # BOT_VOZ/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path

from apps.calls.consumers import BotTestConsumer

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter([
            path("ws/bot-test/", BotTestConsumer.as_asgi()),
        ])
    ),
})
