# app/config.py
"""
Configuration management using Pydantic Settings.
"""
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    LOG_LEVEL: str = "INFO"
    GMAIL_CREDENTIALS_PATH: Optional[str] = None
    WHATSAPP_API_TOKEN: Optional[str] = None
    ONEDRIVE_CLIENT_ID: Optional[str] = None
    ONEDRIVE_CLIENT_SECRET: Optional[str] = None
    SLACK_WEBHOOK_URL: Optional[str] = None

    class Config:
        env_file = ".env"

settings = Settings()
