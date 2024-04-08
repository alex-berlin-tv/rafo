from datetime import datetime
from typing import Optional

import typed_settings


@typed_settings.settings
class Settings:
    baserow_url: str
    base_url: str
    port: int
    project_name: str
    person_table: int
    show_table: int
    upload_table: int
    max_file_size: int

    on_upload_mail: str
    on_upload_sender_name: str
    contact_mail: str
    dev_mode: bool
    log_level: str
    noise_tolerance: str
    """Noise levels below this threshold are considered silence."""
    silence_duration: int
    """Minimal duration of a silence in seconds to be reported."""
    bit_rate: str
    """Bit rate for optimized audio."""
    sample_rate: int
    """Sample rate for optimized audio."""
    audio_crop_allowance: float
    """
    When automatically cutting away silence the given duration of silence will
    remain. This is to prevent to harsh/fast cut ins.
    """
    shows_for_all_upload_exports: list[int]
    """
    A list of Omnia Show id's which each upload export to Omnia should be linked to.
    """
    maintenance_mode: bool
    """
    States whether the maintenance mode should be enabled. If the maintenance
    mode is enabled it's not possible to upload new files. This mode should be
    used during backend (Baserow) updates
    """
    maintenance_message: str
    """Message to shown to the user if maintenance mode is enabled."""
    legacy_url_grace_date: Optional[datetime]
    """Defines a date until when users can use the legacy URL."""
    time_zone: str
    """
    Timezone information in which the input from the upload from should be
    handled in.
    """

    baserow_api_key: str
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


@typed_settings.settings
class PersonTable:
    id: int
    name: str


settings = typed_settings.load(
    Settings,
    appname="rafo",
    config_files=["settings.toml", ".secrets.toml"]
)
