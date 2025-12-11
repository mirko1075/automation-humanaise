# app/file_access/base.py
"""
Base interface for file storage providers.

All file storage providers (LocalFS, OneDrive, GDrive, S3, etc.) must implement this interface.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, List
from pathlib import Path


@dataclass
class FileOperationResult:
    """Result of a file operation."""
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    modified_at: Optional[datetime] = None


@dataclass
class FileMetadata:
    """Metadata for a file."""
    path: str
    size: int
    created_at: datetime
    modified_at: datetime
    exists: bool
    is_directory: bool
    mime_type: Optional[str] = None
    provider_metadata: Optional[Dict[str, Any]] = None


class FileStorageProvider(ABC):
    """
    Abstract base class for file storage providers.
    
    All methods are async to support various I/O operations.
    All methods must be multi-tenant safe.
    All methods must include proper error handling and logging.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize provider with configuration.
        
        Args:
            config: Provider-specific configuration from tenant.file_config
        """
        self.config = config
        self.provider_name = self.__class__.__name__
    
    @abstractmethod
    async def update_quote_excel(
        self,
        tenant_id: str,
        quote: Any,  # Quote model instance
        customer: Dict[str, Any]
    ) -> FileOperationResult:
        """
        Update Excel spreadsheet with quote data.
        
        This is the primary operation for the Preventivi flow.
        Must handle:
        - Finding/creating the Excel file
        - Updating existing rows or appending new ones
        - Locking (for local FS) or conflict resolution (for cloud)
        - Formatting and validation
        
        Args:
            tenant_id: Tenant identifier
            quote: Quote model instance
            customer: Customer data dict
            
        Returns:
            FileOperationResult with success status and details
        """
        pass
    
    @abstractmethod
    async def read_file(self, path: str) -> bytes:
        """
        Read file contents as bytes.
        
        Args:
            path: File path (relative to provider's base)
            
        Returns:
            File contents as bytes
            
        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If access denied
        """
        pass
    
    @abstractmethod
    async def write_file(self, path: str, data: bytes) -> FileOperationResult:
        """
        Write bytes to file.
        
        Args:
            path: File path (relative to provider's base)
            data: Bytes to write
            
        Returns:
            FileOperationResult with success status
        """
        pass
    
    @abstractmethod
    async def file_exists(self, path: str) -> bool:
        """
        Check if file exists.
        
        Args:
            path: File path (relative to provider's base)
            
        Returns:
            True if file exists, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_metadata(self, path: str) -> FileMetadata:
        """
        Get file metadata.
        
        Args:
            path: File path (relative to provider's base)
            
        Returns:
            FileMetadata instance
            
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        pass
    
    @abstractmethod
    async def list_files(self, directory: str) -> List[FileMetadata]:
        """
        List files in directory.
        
        Args:
            directory: Directory path (relative to provider's base)
            
        Returns:
            List of FileMetadata for files in directory
        """
        pass
    
    @abstractmethod
    async def delete_file(self, path: str) -> FileOperationResult:
        """
        Delete file.
        
        Args:
            path: File path (relative to provider's base)
            
        Returns:
            FileOperationResult with success status
        """
        pass
    
    @abstractmethod
    async def create_directory(self, path: str) -> FileOperationResult:
        """
        Create directory (and parents if needed).
        
        Args:
            path: Directory path (relative to provider's base)
            
        Returns:
            FileOperationResult with success status
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check provider health and connectivity.
        
        Must verify:
        - Storage backend is accessible
        - Credentials/tokens are valid
        - Required permissions are present
        - Base paths exist
        
        Returns:
            Dict with health check results:
            {
                "healthy": bool,
                "provider": str,
                "message": str,
                "details": {...}
            }
        """
        pass
    
    def __repr__(self) -> str:
        return f"<{self.provider_name} config={self.config}>"
