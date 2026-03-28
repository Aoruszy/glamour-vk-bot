from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Glamour API"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_timezone: str = "Europe/Kaliningrad"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./glamour.db"
    vk_callback_secret: str = "glamour-secret"
    vk_confirmation_token: str = "glamour-confirm"
    vk_access_token: str = ""
    vk_api_version: str = "5.199"
    vk_group_id: int = 0
    salon_name: str = "Glamour"
    salon_address: str = "Калининград, Гайдара 173"
    salon_phone: str = "+7 (911) 462-62-85"
    salon_working_hours: str = "10:00-20:00"
    salon_map_url: str = ""
    salon_website_url: str = ""
    allow_cors_origins: str = "*"
    admin_username: str = "admin"
    admin_password: str = "glamour-admin"
    auth_secret: str = "glamour-auth-secret"
    auth_access_token_ttl_minutes: int = 480
    notification_poll_interval_seconds: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
