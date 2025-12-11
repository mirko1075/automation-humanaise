# app/file_access/protocols/nfs_protocol.py
"""
NFS protocol adapter for network file access.

NOT YET IMPLEMENTED - Placeholder for future implementation.

To implement NFS support:

1. Install dependencies:
   - libnfs-python: Python bindings for libnfs
   OR
   - Mount NFS share and use localfs_provider

2. Recommended approach:
   - Use libnfs-python for direct NFS operations
   - Alternatively, mount NFS share at OS level and use LocalFSProvider

3. Configuration schema:
   {
       "protocol": "nfs",
       "host": "nfs.company.local",      # NFS server hostname/IP
       "export": "/exports/data",        # NFS export path
       "base_path": "/tenant_data",      # Base path within export
       "version": 3,                     # NFS version (3 or 4)
       "mount_options": "rw,sync"        # Mount options (optional)
   }

4. Implementation checklist:
   - [ ] Install libnfs-python or configure NFS mounts
   - [ ] Implement NFSProtocolAdapter(FileStorageProvider)
   - [ ] Handle NFS-specific errors (NFSERR_NOENT, NFSERR_ACCES, etc.)
   - [ ] Implement connect/disconnect with NFS mount/unmount
   - [ ] Implement all FileStorageProvider abstract methods
   - [ ] Add NFS-specific health checks
   - [ ] Handle NFS locking for concurrent access
   - [ ] Test with real NFS server
   - [ ] Update NAS_PROVIDER_GUIDE.md with NFS examples

5. Example usage:
   ```python
   from app.file_access.nas_provider import NASProvider
   
   config = {
       "protocol": "nfs",
       "host": "nfs.example.com",
       "export": "/data",
       "base_path": "/tenant_acme"
   }
   
   provider = NASProvider(config)
   async with provider:
       files = await provider.list_files("/")
   ```

6. References:
   - libnfs-python: https://github.com/sahlberg/libnfs-python
   - NFS RFC: https://tools.ietf.org/html/rfc1813
   - Linux NFS: https://nfs.sourceforge.net/
"""
from typing import Any, Dict, List, Optional, AsyncIterator

from app.file_access.base_fs import (
    FileInfo,
    FileOperationResult,
    HealthCheckResult,
    FileStorageProvider
)


class NFSProtocolAdapter(FileStorageProvider):
    """
    NFS protocol adapter.
    
    NOT YET IMPLEMENTED.
    """
    
    def __init__(self, config: Dict[str, Any]):
        raise NotImplementedError(
            "NFS protocol adapter is not yet implemented. "
            "See implementation guide in protocols/nfs_protocol.py"
        )
    
    async def connect(self) -> None:
        raise NotImplementedError("NFS adapter not implemented")
    
    async def disconnect(self) -> None:
        raise NotImplementedError("NFS adapter not implemented")
    
    async def list_files(
        self,
        path: str = "/",
        pattern: Optional[str] = None,
        recursive: bool = False
    ) -> List[FileInfo]:
        raise NotImplementedError("NFS adapter not implemented")
    
    async def read_file(self, path: str) -> bytes:
        raise NotImplementedError("NFS adapter not implemented")
    
    async def write_file(
        self,
        path: str,
        data: bytes,
        overwrite: bool = False
    ) -> FileOperationResult:
        raise NotImplementedError("NFS adapter not implemented")
    
    async def delete_file(self, path: str) -> FileOperationResult:
        raise NotImplementedError("NFS adapter not implemented")
    
    async def move_file(
        self,
        source: str,
        destination: str,
        overwrite: bool = False
    ) -> FileOperationResult:
        raise NotImplementedError("NFS adapter not implemented")
    
    async def copy_file(
        self,
        source: str,
        destination: str,
        overwrite: bool = False
    ) -> FileOperationResult:
        raise NotImplementedError("NFS adapter not implemented")
    
    async def mkdir(self, path: str, parents: bool = False) -> FileOperationResult:
        raise NotImplementedError("NFS adapter not implemented")
    
    async def rmdir(self, path: str, recursive: bool = False) -> FileOperationResult:
        raise NotImplementedError("NFS adapter not implemented")
    
    async def file_exists(self, path: str) -> bool:
        raise NotImplementedError("NFS adapter not implemented")
    
    async def get_file_info(self, path: str) -> FileInfo:
        raise NotImplementedError("NFS adapter not implemented")
    
    async def health_check(self) -> HealthCheckResult:
        raise NotImplementedError("NFS adapter not implemented")
