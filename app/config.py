# app/config.py
"""
Configuration management using Pydantic Settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
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
    ONEDRIVE_BASE_PATH: str = "/EDILCOS/TEST"
    MS_GRAPH_BASE_URL: str = "https://graph.microsoft.com/v1.0"
    # Authentication mode for OneDrive integration: 'test' or 'app' (app-only OAuth2)
    ONEDRIVE_AUTH_MODE: str = Field("app", env="ONEDRIVE_AUTH_MODE")
    # Accept either MS_DRIVE_ID or legacy ONEDRIVE_DRIVE_ID environment variable
    MS_DRIVE_ID: str = Field("me/drive", env=("MS_DRIVE_ID", "ONEDRIVE_DRIVE_ID"))
    ONEDRIVE_HOSTNAME: Optional[str] = None  # optional SharePoint host e.g. netorg...-my.sharepoint.com
    MS_ACCESS_TOKEN: Optional[str] = None  # Test token only; do NOT hardcode in code
    # OAuth (app-only) credentials
    MS_CLIENT_ID: Optional[str] = None
    MS_CLIENT_SECRET: Optional[str] = None
    MS_TENANT_ID: Optional[str] = None

settings = Settings()
