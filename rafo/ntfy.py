import enum
from pathlib import Path

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

    # Load config as class variables
    ntfy_url = settings.ntfy_url
    internal_topic = settings.ntfy_internal_topic
    news_topic = settings.ntfy_news_topic

    def __init__(
        self,
        title: str,
        message: str,
        tags: list[str] = [],
        priority: MessagePriority = MessagePriority.DEFAULT,
        topic: str | None = None,
        image_data: bytes | None = None,
        image_url: str | None = None,
    ):
        self.title = title
        self.message = message
        self.priority = priority
        self.tags = tags
        self.topic = topic or self.internal_topic
        self.image_data = image_data
        self.image_url = image_url

    def send(self):
        """Send this message via ntfy."""
        import requests

        headers = {
            "Title": self.title,
            "Priority": str(self.priority.value),
            "Tags": ",".join(self.tags),
        }

        # Add image headers if provided
        if self.image_url:
            headers["Attach"] = self.image_url

        # If binary image data is provided, send it as the body
        if self.image_data:
            headers["Message"] = self.message
            data = self.image_data
        else:
            data = self.message.encode("utf-8")

        requests.post(f"{self.ntfy_url}/{self.topic}", data=data, headers=headers)
        print(f"Sent notification to {self.topic} with title {self.title} and message {self.message}")


class Ntfy:
    """Handles the sending of notifications via ntfy."""

    async def send_on_upload_internal(self, upload: BaserowUpload):
        uploader = await upload.cached_uploader
        show = await upload.cached_show
        # We currently only send internal notifications for news uploads.
        if show.medium.value is not ShowMedium.NEWS:
            logger.info(
                f"Skipping internal notification via ntfy for non-news upload {upload.row_id}."
            )
            return
        title = f"u-{upload.row_id:05d}: Neuer Nachrichtensendung {show.name}"
        message = f"Ein neuer Nachrichtensendung für {show.name} von {uploader.name} wurde eingereicht."
        Message(title, message, priority=MessagePriority.LOW, tags=["newspaper"]).send()
    