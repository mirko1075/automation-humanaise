# app/file_access/protocols/ftp_protocol.py
"""
FTP/FTPS protocol adapter for network file access.

NOT YET IMPLEMENTED - Placeholder for future implementation.

To implement FTP/FTPS support:

1. Install dependencies:
   - Standard library ftplib (included with Python)
   - For FTPS with TLS/SSL, ftplib.FTP_TLS is available

2. Configuration schema:
   {
       "protocol": "ftp",                    # or "ftps" for secure FTP
       "host": "ftp.company.local",          # FTP server hostname/IP
       "port": 21,                           # FTP port (default: 21, FTPS: 990)
       "username": "user",                   # Username
       "password": "pass",                   # Password
       "base_path": "/tenant_data",          # Base path on FTP server
       "passive": true,                      # Use passive mode (default: true)
       "tls": false,                         # Use TLS (FTPS) (default: false)
       "verify_ssl": true                    # Verify SSL certificates for FTPS (default: true)
   }

3. Implementation checklist:
   - [ ] Implement FTPProtocolAdapter(FileStorageProvider) using ftplib
   - [ ] Support both active and passive FTP modes
   - [ ] Support FTPS (FTP over TLS/SSL) using ftplib.FTP_TLS
   - [ ] Handle FTP-specific errors (ftplib.error_perm, etc.)
   - [ ] Implement connect/disconnect with FTP client
   - [ ] Implement all FileStorageProvider abstract methods
   - [ ] Handle binary vs ASCII transfer modes (use binary for files)
   - [ ] Add FTP-specific health checks
   - [ ] Test with real FTP/FTPS server
   - [ ] Update NAS_PROVIDER_GUIDE.md with FTP examples

4. Example usage (FTP):
   ```python
   from app.file_access.nas_provider import NASProvider
   
   config = {
       "protocol": "ftp",
       "host": "ftp.example.com",
       "port": 21,
       "username": "edilcos_app",
       "password": "secret",
       "base_path": "/data/tenant_acme",
       "passive": true
   }
   
   provider = NASProvider(config)
   async with provider:
       files = await provider.list_files("/")
   ```

5. Example usage (FTPS):
   ```python
   config = {
       "protocol": "ftps",
       "host": "ftps.example.com",
       "port": 990,
       "username": "edilcos_app",
       "password": "secret",
       "base_path": "/data/tenant_acme",
       "tls": true,
       "verify_ssl": true
   }
   
   provider = NASProvider(config)
   async with provider:
       await provider.write_file("/document.pdf", pdf_bytes, overwrite=True)
   ```

6. FTP vs FTPS:
   - FTP: Unencrypted, not recommended for production use
   - FTPS (FTP over TLS): Encrypted, secure, recommended for production
   - Port 21: Standard FTP (can upgrade to TLS)
   - Port 990: Implicit FTPS (TLS from start)

7. Active vs Passive mode:
   - Passive: Client initiates data connection (recommended, firewall-friendly)
   - Active: Server initiates data connection (older, may have firewall issues)

8. References:
   - ftplib documentation: https://docs.python.org/3/library/ftplib.html
   - FTP RFC: https://tools.ietf.org/html/rfc959
   - FTPS RFC: https://tools.ietf.org/html/rfc4217
"""
from typing import Any, Dict, List, Optional, AsyncIterator

from app.file_access.base_fs import (
    FileInfo,
    FileOperationResult,
    HealthCheckResult,
    FileStorageProvider
)


class FTPProtocolAdapter(FileStorageProvider):
    """
    FTP/FTPS protocol adapter.
    
    NOT YET IMPLEMENTED.
    """
    
    def __init__(self, config: Dict[str, Any]):
        raise NotImplementedError(
            "FTP/FTPS protocol adapter is not yet implemented. "
            "See implementation guide in protocols/ftp_protocol.py"
        )
    
    async def connect(self) -> None:
        raise NotImplementedError("FTP adapter not implemented")
    
    async def disconnect(self) -> None:
        raise NotImplementedError("FTP adapter not implemented")
    
    async def list_files(
        self,
        path: str = "/",
        pattern: Optional[str] = None,
        recursive: bool = False
    ) -> List[FileInfo]:
        raise NotImplementedError("FTP adapter not implemented")
    
    async def read_file(self, path: str) -> bytes:
        raise NotImplementedError("FTP adapter not implemented")
    
    async def write_file(
        self,
        path: str,
        data: bytes,
        overwrite: bool = False
    ) -> FileOperationResult:
        raise NotImplementedError("FTP adapter not implemented")
    
    async def delete_file(self, path: str) -> FileOperationResult:
        raise NotImplementedError("FTP adapter not implemented")
    
    async def move_file(
        self,
        source: str,
        destination: str,
        overwrite: bool = False
    ) -> FileOperationResult:
        raise NotImplementedError("FTP adapter not implemented")
    
    async def copy_file(
        self,
        source: str,
        destination: str,
        overwrite: bool = False
    ) -> FileOperationResult:
        raise NotImplementedError("FTP adapter not implemented")
    
    async def mkdir(self, path: str, parents: bool = False) -> FileOperationResult:
        raise NotImplementedError("FTP adapter not implemented")
    
    async def rmdir(self, path: str, recursive: bool = False) -> FileOperationResult:
        raise NotImplementedError("FTP adapter not implemented")
    
    async def file_exists(self, path: str) -> bool:
        raise NotImplementedError("FTP adapter not implemented")
    
    async def get_file_info(self, path: str) -> FileInfo:
        raise NotImplementedError("FTP adapter not implemented")
    
    async def health_check(self) -> HealthCheckResult:
        raise NotImplementedError("FTP adapter not implemented")
