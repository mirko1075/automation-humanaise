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
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    N8N_WEBHOOK_URL: Optional[str] = Field(None, env="N8N_WEBHOOK_URL")
    GMAIL_CREDENTIALS_PATH: Optional[str] = Field(None, env="GMAIL_CREDENTIALS_PATH")
    WHATSAPP_API_TOKEN: Optional[str] = Field(None, env="WHATSAPP_API_TOKEN")
    ONEDRIVE_CLIENT_ID: Optional[str] = Field(None, env="ONEDRIVE_CLIENT_ID")
    ONEDRIVE_CLIENT_SECRET: Optional[str] = Field(None, env="ONEDRIVE_CLIENT_SECRET")
    ONEDRIVE_TENANT_ID: Optional[str] = Field(None, env="ONEDRIVE_TENANT_ID")
    ONEDRIVE_DRIVE_ID: Optional[str] = Field(None, env="ONEDRIVE_DRIVE_ID")
    ONEDRIVE_EXCEL_FILE_ID: Optional[str] = Field(None, env="ONEDRIVE_EXCEL_FILE_ID")
    SLACK_WEBHOOK_URL: Optional[str] = Field(None, env="SLACK_WEBHOOK_URL")
    SLACK_ENABLED: bool = Field(False, env="SLACK_ENABLED")
    # Microsoft Graph / OneDrive configuration
    ONEDRIVE_BASE_PATH: str = "/EDILCOS/TEST"
    MS_GRAPH_BASE_URL: str = "https://graph.microsoft.com/v1.0"
    # Authentication mode for OneDrive integration: 'test' or 'app' (app-only OAuth2)
    ONEDRIVE_AUTH_MODE: str = "app"
    # Accept either MS_DRIVE_ID or legacy ONEDRIVE_DRIVE_ID environment variable
    MS_DRIVE_ID: str = Field("me/drive", env="MS_DRIVE_ID")
    ONEDRIVE_HOSTNAME: Optional[str] = None  # optional SharePoint host e.g. netorg...-my.sharepoint.com
    MS_ACCESS_TOKEN: Optional[str] = None  # Test token only; do NOT hardcode in code
    # OAuth (app-only) credentials
    MS_CLIENT_ID: Optional[str] = None
    MS_CLIENT_SECRET: Optional[str] = None
    MS_TENANT_ID: Optional[str] = None
    # Whether health check should perform a temporary write (create+delete folder)
    ONEDRIVE_HEALTHCHECK_WRITE: bool = Field(False, env="ONEDRIVE_HEALTHCHECK_WRITE")

    # Google OAuth settings for Gmail ingestion
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = None

settings = Settings()
