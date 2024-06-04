from datetime import datetime
import enum
from typing import Optional

import typed_settings


@typed_settings.settings
class Settings:
    baserow_url: str
    """URL of the Baserow instance serving as the data backend."""
    base_url: str
    """
    Public URL of the rafo instance. Used to enable correct linking to the site.
    """
    port: int
    """The port on which rafo is running."""
    time_zone: str
    """
    Timezone information in which the input from the upload from should be
    handled in.
    """

    person_table: int
    """Unique ID of the person table in Baserow."""
    show_table: int
    """Unique ID of the show table in Baserow."""
    upload_table: int
    """Unique ID of the upload table in Baserow."""

    max_file_size: int
    """The maximum allowed file size for media uploads. In GB."""
    on_upload_mail: str
    """The sender's email address for confirmation emails."""
    on_upload_sender_name: str
    """Sender's name for the confirmation emails."""
    contact_mail: str
    """
    The contact email address is shared with producers in the email and on the
    website, serving as a point of contact for any inquiries.
    """

    noise_tolerance: str
    """
    Noise levels below this threshold are considered silence. Can be specified
    in dB (in case "dB" is appended to the specified value) or amplitude ratio.
    """
    silence_duration: int
    """Minimal duration of a silence in seconds to be reported."""
    bit_rate: str
    """
    Bit rate for optimized audio. Use the suffix "k" for kilobits per second
    (kBit/s) and "m" for megabits per second (mBit/s), adhering to the syntax
    for specifying bit rate in ffmpeg. For example, "128k" indicates a bit rate
    of 128 kBit/s.
    """
    sample_rate: int
    """Sample rate for optimized audio."""
    audio_crop_allowance: float
    """
    When automatically cutting away silence the given duration of silence in
    seconds will remain. This is to prevent to0 harsh/fast cut ins.
    """

    shows_for_all_upload_exports: list[int]
    """
    A list of Omnia Show id's which each upload export to Omnia should be linked to.
    """
    dev_mode: bool
    """
    When development mode is enabled, the form displays a button that allows for
    quick filling with test data. Additionally, the test mode is noted in the
    email, marking them clearly as test entries for all recipients.
    """
    log_level: str
    """Set the log level as specified by Python's built-in logging package."""
    maintenance_mode: bool
    """
    Specifies whether maintenance mode should be activated. If enabled,
    uploading new files is not possible, and a notification is displayed (the
    content of which can be configured). This mode is advisable during backend
    (Baserow) updates.
    """
    maintenance_message: str
    """Message to shown to the user if maintenance mode is enabled."""
    legacy_url_grace_date: Optional[datetime]
    """Date (in ISO format) until which the legacy URLs will be accepted."""

    baserow_api_key: str
    """CRUD API token for Baserow."""
    smtp_sender_address: str
    smtp_host: str
    smtp_user: str
    smtp_port: int
    smtp_password: str
    omnia_domain_id: str
    omnia_api_secret: str
    omnia_session_id: str
    webhook_secret: str
    """Arbitrary secret for webhook calls from Baserow."""


class NotificationLevel(str, enum.Enum):
    INFO = "info"
    SUCCESS = "success"
    WARN = "warn"
    ERROR = "error"


@typed_settings.settings
class Notification:
    show: bool = False
    level: NotificationLevel | None = None
    title: str | None = None
    message: str | None = None


app_name = "rafo"
config_files = ["settings.toml", ".secrets.toml"]


settings = typed_settings.load(
    Settings,
    appname=app_name,
    config_files=config_files,
)

notification = typed_settings.load(
    Notification,
    appname=app_name,
    config_files=config_files,
    config_file_section="notification",
)
