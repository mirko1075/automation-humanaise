"""
File Access Abstraction Layer (FAAL)

Unified interface for accessing different file storage backends:
- Local filesystem / NAS
- OneDrive
- Google Drive (future)
- S3 (future)
- Custom per-tenant providers
"""

from app.file_access.base import FileStorageProvider, FileOperationResult
from app.file_access.registry import get_file_provider

__all__ = [
    "FileStorageProvider",
    "FileOperationResult",
    "get_file_provider",
]
