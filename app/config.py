# app/config.py
"""
Configuration management using Pydantic Settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    DATABASE_URL: str
    LOG_LEVEL: str = "INFO"
    GMAIL_CREDENTIALS_PATH: Optional[str] = None
    WHATSAPP_API_TOKEN: Optional[str] = None
    ONEDRIVE_CLIENT_ID: Optional[str] = None
    ONEDRIVE_CLIENT_SECRET: Optional[str] = None
    ONEDRIVE_TENANT_ID: Optional[str] = None
    ONEDRIVE_DRIVE_ID: Optional[str] = None
    ONEDRIVE_EXCEL_FILE_ID: Optional[str] = None
    SLACK_WEBHOOK_URL: Optional[str] = None
    # Microsoft Graph / OneDrive configuration
    ONEDRIVE_BASE_PATH: str = "/TEST"
    MS_GRAPH_BASE_URL: str = "https://graph.microsoft.com/v1.0"
    MS_DRIVE_ID: str = "me/drive"
    MS_ACCESS_TOKEN: Optional[str] = None  # Test token only; do NOT hardcode in code

settings = Settings()
