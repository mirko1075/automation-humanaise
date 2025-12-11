# app/file_access/base_fs.py
"""
Base filesystem interface for all file storage protocols.

This interface defines the contract that all protocol adapters must implement.
It is protocol-agnostic and can be used with SMB, NFS, WebDAV, SFTP, FTP/S, etc.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, AsyncIterator
from pathlib import Path


@dataclass
class FileInfo:
    """Information about a file or directory."""
    path: str
    name: str
    size: int
    is_directory: bool
    modified_time: datetime
    created_time: Optional[datetime] = None
    mime_type: Optional[str] = None
    permissions: Optional[str] = None
    owner: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class FileOperationResult:
    """Result of a file operation."""
    success: bool
    message: str
    path: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    healthy: bool
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    protocol: Optional[str] = None
    latency_ms: Optional[float] = None


class FileStorageProvider(ABC):
    """
    Abstract base class for file storage providers.
    
    All protocol adapters (SMB, NFS, WebDAV, SFTP, etc.) must implement this interface.
    All methods are async to support various I/O operations and network protocols.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize provider with configuration.
        
        Args:
            config: Provider-specific configuration
        """
        self.config = config
        self.protocol = config.get("protocol", "unknown")
    
    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection to the storage backend.
        
        Should be called before any file operations.
        May involve authentication, session establishment, etc.
        
        Raises:
            ConnectionError: If connection fails
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """
        Close connection to the storage backend.
        
        Should be called when done with operations to free resources.
        """
        pass
    
    @abstractmethod
    async def list_files(
        self, 
        path: str = "",
        pattern: Optional[str] = None,
        recursive: bool = False
    ) -> List[FileInfo]:
        """
        List files in a directory.
        
        Args:
            path: Directory path (relative to base_path)
            pattern: Optional glob pattern to filter files (e.g., "*.xlsx")
            recursive: If True, list files recursively
            
        Returns:
            List of FileInfo objects
            
        Raises:
            FileNotFoundError: If directory doesn't exist
            PermissionError: If access denied
        """
        pass
    
    @abstractmethod
    async def read_file(self, path: str) -> bytes:
        """
        Read file contents as bytes.
        
        Args:
            path: File path (relative to base_path)
            
        Returns:
            File contents as bytes
            
        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If access denied
        """
        pass
    
    @abstractmethod
    async def write_file(
        self, 
        path: str, 
        data: bytes,
        overwrite: bool = True
    ) -> FileOperationResult:
        """
        Write bytes to file.
        
        Args:
            path: File path (relative to base_path)
            data: Bytes to write
            overwrite: If False and file exists, raise error
            
        Returns:
            FileOperationResult with success status
            
        Raises:
            FileExistsError: If file exists and overwrite=False
            PermissionError: If access denied
        """
        pass
    
    @abstractmethod
    async def delete_file(self, path: str) -> FileOperationResult:
        """
        Delete a file.
        
        Args:
            path: File path (relative to base_path)
            
        Returns:
            FileOperationResult with success status
            
        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If access denied
        """
        pass
    
    @abstractmethod
    async def move_file(
        self, 
        source: str, 
        destination: str,
        overwrite: bool = False
    ) -> FileOperationResult:
        """
        Move or rename a file.
        
        Args:
            source: Source file path
            destination: Destination file path
            overwrite: If True, overwrite destination if exists
            
        Returns:
            FileOperationResult with success status
            
        Raises:
            FileNotFoundError: If source doesn't exist
            FileExistsError: If destination exists and overwrite=False
            PermissionError: If access denied
        """
        pass
    
    @abstractmethod
    async def copy_file(
        self,
        source: str,
        destination: str,
        overwrite: bool = False
    ) -> FileOperationResult:
        """
        Copy a file.
        
        Args:
            source: Source file path
            destination: Destination file path
            overwrite: If True, overwrite destination if exists
            
        Returns:
            FileOperationResult with success status
        """
        pass
    
    @abstractmethod
    async def mkdir(
        self, 
        path: str,
        parents: bool = True
    ) -> FileOperationResult:
        """
        Create a directory.
        
        Args:
            path: Directory path (relative to base_path)
            parents: If True, create parent directories as needed
            
        Returns:
            FileOperationResult with success status
            
        Raises:
            FileExistsError: If directory already exists
            PermissionError: If access denied
        """
        pass
    
    @abstractmethod
    async def rmdir(
        self,
        path: str,
        recursive: bool = False
    ) -> FileOperationResult:
        """
        Remove a directory.
        
        Args:
            path: Directory path
            recursive: If True, remove directory and all contents
            
        Returns:
            FileOperationResult with success status
        """
        pass
    
    @abstractmethod
    async def file_exists(self, path: str) -> bool:
        """
        Check if file or directory exists.
        
        Args:
            path: File or directory path
            
        Returns:
            True if exists, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_file_info(self, path: str) -> FileInfo:
        """
        Get detailed information about a file or directory.
        
        Args:
            path: File or directory path
            
        Returns:
            FileInfo object
            
        Raises:
            FileNotFoundError: If path doesn't exist
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> HealthCheckResult:
        """
        Check provider health and connectivity.
        
        Should verify:
        - Connection is established
        - Authentication is valid
        - Base path is accessible
        - Read/write permissions are present
        
        Returns:
            HealthCheckResult with health status and diagnostics
        """
        pass
    
    async def stream_read(
        self,
        path: str,
        chunk_size: int = 8192
    ) -> AsyncIterator[bytes]:
        """
        Stream read a file in chunks.
        
        Useful for large files to avoid loading entire file into memory.
        Default implementation reads entire file and yields it.
        Protocol adapters may override for true streaming.
        
        Args:
            path: File path
            chunk_size: Size of chunks to read
            
        Yields:
            Bytes chunks
        """
        data = await self.read_file(path)
        for i in range(0, len(data), chunk_size):
            yield data[i:i + chunk_size]
    
    async def stream_write(
        self,
        path: str,
        data_iterator: AsyncIterator[bytes],
        overwrite: bool = True
    ) -> FileOperationResult:
        """
        Stream write a file from chunks.
        
        Default implementation collects all chunks and writes at once.
        Protocol adapters may override for true streaming.
        
        Args:
            path: File path
            data_iterator: Async iterator yielding bytes chunks
            overwrite: If False and file exists, raise error
            
        Returns:
            FileOperationResult
        """
        chunks = []
        async for chunk in data_iterator:
            chunks.append(chunk)
        data = b"".join(chunks)
        return await self.write_file(path, data, overwrite=overwrite)
    
    async def __aenter__(self):
        """Context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.disconnect()
        return False
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} protocol={self.protocol}>"
