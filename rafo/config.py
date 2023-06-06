from dynaconf import Dynaconf


settings = Dynaconf(
    envvar_prefix="RF",
    settings_files=["settings.toml", ".secrets.toml"]
)
