import json
import structlog
from datetime import datetime
from google.cloud import pubsub_v1

from config.settings import get_settings

logger = structlog.get_logger(__name__)


class PubSubPublisher:
    def __init__(self) -> None:
        settings = get_settings()
        self._publisher = pubsub_v1.PublisherClient()
        self._topic_path = self._publisher.topic_path(
            settings.gcp_project_id,
            settings.pubsub_topic_call_events,
        )

    async def publish_call_event(self, event_type: str, call_id: str, **extra) -> None:
        """Publica un evento de llamada a Pub/Sub (fire-and-forget)."""
        message = {
            "event_type": event_type,
            "call_id": call_id,
            "timestamp": datetime.utcnow().isoformat(),
            **extra,
        }
        data = json.dumps(message).encode("utf-8")
        try:
            future = self._publisher.publish(self._topic_path, data=data)
            future.result(timeout=5)
            logger.debug("pubsub_event_published", event_type=event_type, call_id=call_id)
        except Exception as exc:
            logger.error("pubsub_publish_failed", event_type=event_type, call_id=call_id, error=str(exc))


_publisher: PubSubPublisher | None = None


def get_pubsub_publisher() -> PubSubPublisher:
    global _publisher
    if _publisher is None:
        _publisher = PubSubPublisher()
    return _publisher
