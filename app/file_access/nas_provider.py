# app/file_access/nas_provider.py
"""
NAS provider with multi-protocol support.

Dynamically loads protocol adapters based on tenant configuration
and delegates all filesystem operations to the appropriate adapter.
"""
from typing import Any, Dict, List, Optional, AsyncIterator

import structlog

from app.file_access.base_fs import (
    FileInfo,
    FileOperationResult,
    HealthCheckResult,
    FileStorageProvider
)

logger = structlog.get_logger()


class NASProvider(FileStorageProvider):
    """
    Multi-protocol NAS provider.
    
    This class acts as an orchestrator that dynamically loads
    the appropriate protocol adapter based on configuration and
    delegates all operations to that adapter.
    
    Configuration (file_config):
    {
        "protocol": "smb",  # Protocol type: smb, nfs, webdav, sftp, ftp, ftps
        ... protocol-specific config ...
    }
    
    Example tenant configurations:
    
    SMB:
    {
        "file_provider": "nas",
        "file_config": {
            "protocol": "smb",
            "host": "nas.company.local",
            "share": "documents",
            "username": "user",
            "password": "pass",
            "base_path": "/tenant_data"
        }
    }
    
    NFS:
    {
        "file_provider": "nas",
        "file_config": {
            "protocol": "nfs",
            "host": "nfs.company.local",
            "export": "/exports/data",
            "base_path": "/tenant_data"
        }
    }
    
    WebDAV:
    {
        "file_provider": "nas",
        "file_config": {
            "protocol": "webdav",
            "url": "https://webdav.company.local/remote.php/dav",
            "username": "user",
            "password": "pass",
            "base_path": "/tenant_data"
        }
    }
    
    SFTP:
    {
        "file_provider": "nas",
        "file_config": {
            "protocol": "sftp",
            "host": "sftp.company.local",
            "port": 22,
            "username": "user",
            "password": "pass",  # or "private_key_path": "/path/to/key"
            "base_path": "/tenant_data"
        }
    }
    """
    
    # Protocol adapter registry
    _protocol_adapters: Dict[str, type] = {}
    
    @classmethod
    def register_protocol(cls, protocol: str, adapter_class: type) -> None:
        """
        Register a protocol adapter.
        
        Args:
            protocol: Protocol name (e.g., "smb", "nfs")
            adapter_class: Adapter class implementing FileStorageProvider
        """
        cls._protocol_adapters[protocol.lower()] = adapter_class
        logger.info("protocol_registered", protocol=protocol, adapter=adapter_class.__name__)
    
    @classmethod
    def get_supported_protocols(cls) -> List[str]:
        """
        Get list of supported protocols.
        
        Returns:
            List of protocol names
        """
        return list(cls._protocol_adapters.keys())
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize NAS provider.
        
        Args:
            config: Configuration dictionary with "protocol" key
        """
        self.config = config
        self.protocol = config.get("protocol", "").lower()
        
        if not self.protocol:
            raise ValueError("Protocol not specified in configuration")
        
        if self.protocol not in self._protocol_adapters:
            raise ValueError(
                f"Unsupported protocol: {self.protocol}. "
                f"Supported protocols: {', '.join(self.get_supported_protocols())}"
            )
        
        # Instantiate protocol adapter
        adapter_class = self._protocol_adapters[self.protocol]
        self._adapter: FileStorageProvider = adapter_class(config)
        
        logger.info(
            "nas_provider_initialized",
            protocol=self.protocol,
            adapter=adapter_class.__name__
        )
    
    async def connect(self) -> None:
        """Establish connection via protocol adapter."""
        logger.debug("nas_connecting", protocol=self.protocol)
        await self._adapter.connect()
    
    async def disconnect(self) -> None:
        """Disconnect via protocol adapter."""
        logger.debug("nas_disconnecting", protocol=self.protocol)
        await self._adapter.disconnect()
    
    async def list_files(
        self,
        path: str = "/",
        pattern: Optional[str] = None,
        recursive: bool = False
    ) -> List[FileInfo]:
        """List files via protocol adapter."""
        return await self._adapter.list_files(path, pattern, recursive)
    
    async def read_file(self, path: str) -> bytes:
        """Read file via protocol adapter."""
        return await self._adapter.read_file(path)
    
    async def write_file(
        self,
        path: str,
        data: bytes,
        overwrite: bool = False
    ) -> FileOperationResult:
        """Write file via protocol adapter."""
        return await self._adapter.write_file(path, data, overwrite)
    
    async def delete_file(self, path: str) -> FileOperationResult:
        """Delete file via protocol adapter."""
        return await self._adapter.delete_file(path)
    
    async def move_file(
        self,
        source: str,
        destination: str,
        overwrite: bool = False
    ) -> FileOperationResult:
        """Move file via protocol adapter."""
        return await self._adapter.move_file(source, destination, overwrite)
    
    async def copy_file(
        self,
        source: str,
        destination: str,
        overwrite: bool = False
    ) -> FileOperationResult:
        """Copy file via protocol adapter."""
        return await self._adapter.copy_file(source, destination, overwrite)
    
    async def mkdir(self, path: str, parents: bool = False) -> FileOperationResult:
        """Create directory via protocol adapter."""
        return await self._adapter.mkdir(path, parents)
    
    async def rmdir(self, path: str, recursive: bool = False) -> FileOperationResult:
        """Remove directory via protocol adapter."""
        return await self._adapter.rmdir(path, recursive)
    
    async def file_exists(self, path: str) -> bool:
        """Check if file exists via protocol adapter."""
        return await self._adapter.file_exists(path)
    
    async def get_file_info(self, path: str) -> FileInfo:
        """Get file info via protocol adapter."""
        return await self._adapter.get_file_info(path)
    
    async def health_check(self) -> HealthCheckResult:
        """
        Perform health check via protocol adapter.
        
        Adds protocol information to health check results.
        """
        result = await self._adapter.health_check()
        
        # Add protocol info
        if result.details is None:
            result.details = {}
        result.details["protocol"] = self.protocol
        result.details["adapter"] = self._adapter.__class__.__name__
        
        return result
    
    async def stream_read(
        self,
        path: str,
        chunk_size: int = 8192
    ) -> AsyncIterator[bytes]:
        """Stream read via protocol adapter."""
        async for chunk in self._adapter.stream_read(path, chunk_size):
            yield chunk
    
    async def stream_write(
        self,
        path: str,
        data_iterator: AsyncIterator[bytes],
        overwrite: bool = False
    ) -> FileOperationResult:
        """Stream write via protocol adapter."""
        return await self._adapter.stream_write(path, data_iterator, overwrite)


# Auto-register available protocol adapters
def _register_protocols():
    """Register all available protocol adapters."""
    
    # Try to import and register SMB adapter
    try:
        from app.file_access.protocols.smb_protocol import SMBProtocolAdapter
        NASProvider.register_protocol("smb", SMBProtocolAdapter)
    except ImportError as e:
        logger.warning("smb_protocol_unavailable", error=str(e))
    
    # Try to import and register NFS adapter
    try:
        from app.file_access.protocols.nfs_protocol import NFSProtocolAdapter
        NASProvider.register_protocol("nfs", NFSProtocolAdapter)
    except ImportError as e:
        logger.debug("nfs_protocol_unavailable", error=str(e))
    
    # Try to import and register WebDAV adapter
    try:
        from app.file_access.protocols.webdav_protocol import WebDAVProtocolAdapter
        NASProvider.register_protocol("webdav", WebDAVProtocolAdapter)
    except ImportError as e:
        logger.debug("webdav_protocol_unavailable", error=str(e))
    
    # Try to import and register SFTP adapter
    try:
        from app.file_access.protocols.sftp_protocol import SFTPProtocolAdapter
        NASProvider.register_protocol("sftp", SFTPProtocolAdapter)
    except ImportError as e:
        logger.debug("sftp_protocol_unavailable", error=str(e))
    
    # Try to import and register FTP/FTPS adapter
    try:
        from app.file_access.protocols.ftp_protocol import FTPProtocolAdapter
        NASProvider.register_protocol("ftp", FTPProtocolAdapter)
        NASProvider.register_protocol("ftps", FTPProtocolAdapter)
    except ImportError as e:
        logger.debug("ftp_protocol_unavailable", error=str(e))


# Register protocols on module import
_register_protocols()
