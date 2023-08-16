import typed_settings


@typed_settings.settings
class Settings:
    nocodb_url: str
    base_url: str
    port: int
    project_name: str
    producer_table: str
    show_table: str
    episode_table: str
    max_file_size: int
    raw_column: str
    waveform_column: str
    producer_column: str
    show_column: str
    on_upload_mail: str
    on_upload_sender_name: str
    contact_mail: str
    dev_mode: bool
    log_level: str
    noise_tolerance: str
    """Noise levels below this threshold are considered silence."""
    silence_duration: int
    """Minimal duration of a silence in seconds to be reported."""
    nocodb_api_key: str
    smtp_sender_address: str
    smtp_host: str
    smtp_user: str
    smtp_port: int
    smtp_password: str


settings = typed_settings.load(
    Settings,
    appname="rafo",
    config_files=["settings.toml", ".secrets.toml"]
)
