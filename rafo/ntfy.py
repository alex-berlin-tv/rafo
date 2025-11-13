import enum

from .config import settings
from .log import logger
from .model import BaserowUpload, ShowMedium

class MessagePriority(str, enum.Enum):
    MAX = 5
    HIGH = 4
    DEFAULT = 3
    LOW = 2
    MIN = 1


class Message:
    """Represents a message to be sent via ntfy."""

    def __init__(
        self,
        title: str,
        message: str,
        tags: list[str] = [],
        priority: MessagePriority = MessagePriority.DEFAULT,
    ):
        self.title = title
        self.message = message
        self.priority = priority
        self.tags = tags


class Ntfy:
    """Handles the sending of notifications via ntfy."""

    def __init__(
        self,
        url: str,
        topic: str,
    ):
        self.url = url
        self.topic = topic

    @classmethod
    def from_settings(cls):
        return cls(
            settings.ntfy_url,
            settings.ntfy_topic,
        )

    async def send_on_upload_internal(self, upload: BaserowUpload):
        uploader = await upload.cached_uploader
        show = await upload.cached_show
        # We currently only send internal notifications for news uploads.
        if show.medium.value is not ShowMedium.NEWS:
            logger.info(f"Skipping internal notification via ntfy for non-news upload {upload.row_id}.")
            return
        title = f"u-{upload.row_id:05d}: Neuer Nachrichtensendung {show.name}"
        message = f"Ein neuer Nachrichtensendung für {show.name} von {uploader.name} wurde eingereicht."
        self._send(Message(title, message, priority=MessagePriority.LOW, tags=["newspaper"]))

    def _send(self, message: Message):
        import requests
        
        requests.post(
            f"{self.url}/{self.topic}",
            data=message.message.encode('utf-8'),
            headers={
                "Title": message.title,
                "Priority": str(message.priority.value),
                "Tags": ",".join(message.tags),
            }
        )