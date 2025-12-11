# app/file_access/protocols/sftp_protocol.py
"""
SFTP protocol adapter for network file access.

NOT YET IMPLEMENTED - Placeholder for future implementation.

To implement SFTP support:

1. Install dependencies:
   pip install paramiko

2. Configuration schema:
   {
       "protocol": "sftp",
       "host": "sftp.company.local",           # SFTP server hostname/IP
       "port": 22,                             # SFTP port (default: 22)
       "username": "user",                     # Username
       "password": "pass",                     # Password (optional if using key)
       "private_key_path": "/path/to/key",     # Path to private key file (optional)
       "private_key_passphrase": "phrase",     # Key passphrase (optional)
       "base_path": "/tenant_data",            # Base path on SFTP server
       "host_key_policy": "auto_add"           # Host key policy: auto_add, reject, warn (default: auto_add)
   }

3. Implementation checklist:
   - [ ] Install paramiko library
   - [ ] Implement SFTPProtocolAdapter(FileStorageProvider)
   - [ ] Handle SFTP-specific errors (IOError, OSError, etc.)
   - [ ] Implement connect/disconnect with paramiko SSHClient
   - [ ] Support both password and key-based authentication
   - [ ] Implement all FileStorageProvider abstract methods
   - [ ] Add SFTP-specific health checks
   - [ ] Handle host key verification policies
   - [ ] Handle connection timeouts and retries
   - [ ] Test with real SFTP server
   - [ ] Update NAS_PROVIDER_GUIDE.md with SFTP examples

4. Example usage (password auth):
   ```python
   from app.file_access.nas_provider import NASProvider
   
   config = {
       "protocol": "sftp",
       "host": "sftp.example.com",
       "port": 22,
       "username": "edilcos_app",
       "password": "secret",
       "base_path": "/data/tenant_acme"
   }
   
   provider = NASProvider(config)
   async with provider:
       files = await provider.list_files("/")
   ```

5. Example usage (key auth):
   ```python
   config = {
       "protocol": "sftp",
       "host": "sftp.example.com",
       "username": "edilcos_app",
       "private_key_path": "/home/app/.ssh/id_rsa",
       "base_path": "/data/tenant_acme"
   }
   
   provider = NASProvider(config)
   async with provider:
       data = await provider.read_file("/document.pdf")
   ```

6. Host key policies:
   - auto_add: Automatically add unknown host keys (use with caution in production)
   - reject: Reject unknown host keys (most secure, requires pre-populated known_hosts)
   - warn: Log warning but accept (useful for testing)

7. References:
   - paramiko: https://www.paramiko.org/
   - SFTP RFC: https://tools.ietf.org/html/draft-ietf-secsh-filexfer
   - SSH/SFTP best practices: https://www.ssh.com/academy/ssh/sftp
"""
from typing import Any, Dict, List, Optional, AsyncIterator

from app.file_access.base_fs import (
    FileInfo,
    FileOperationResult,
    HealthCheckResult,
    FileStorageProvider
)


class SFTPProtocolAdapter(FileStorageProvider):
    """
    SFTP protocol adapter.
    
    NOT YET IMPLEMENTED.
    """
    
    def __init__(self, config: Dict[str, Any]):
        raise NotImplementedError(
            "SFTP protocol adapter is not yet implemented. "
            "See implementation guide in protocols/sftp_protocol.py"
        )
    
    async def connect(self) -> None:
        raise NotImplementedError("SFTP adapter not implemented")
    
    async def disconnect(self) -> None:
        raise NotImplementedError("SFTP adapter not implemented")
    
    async def list_files(
        self,
        path: str = "/",
        pattern: Optional[str] = None,
        recursive: bool = False
    ) -> List[FileInfo]:
        raise NotImplementedError("SFTP adapter not implemented")
    
    async def read_file(self, path: str) -> bytes:
        raise NotImplementedError("SFTP adapter not implemented")
    
    async def write_file(
        self,
        path: str,
        data: bytes,
        overwrite: bool = False
    ) -> FileOperationResult:
        raise NotImplementedError("SFTP adapter not implemented")
    
    async def delete_file(self, path: str) -> FileOperationResult:
        raise NotImplementedError("SFTP adapter not implemented")
    
    async def move_file(
        self,
        source: str,
        destination: str,
        overwrite: bool = False
    ) -> FileOperationResult:
        raise NotImplementedError("SFTP adapter not implemented")
    
    async def copy_file(
        self,
        source: str,
        destination: str,
        overwrite: bool = False
    ) -> FileOperationResult:
        raise NotImplementedError("SFTP adapter not implemented")
    
    async def mkdir(self, path: str, parents: bool = False) -> FileOperationResult:
        raise NotImplementedError("SFTP adapter not implemented")
    
    async def rmdir(self, path: str, recursive: bool = False) -> FileOperationResult:
        raise NotImplementedError("SFTP adapter not implemented")
    
    async def file_exists(self, path: str) -> bool:
        raise NotImplementedError("SFTP adapter not implemented")
    
    async def get_file_info(self, path: str) -> FileInfo:
        raise NotImplementedError("SFTP adapter not implemented")
    
    async def health_check(self) -> HealthCheckResult:
        raise NotImplementedError("SFTP adapter not implemented")
