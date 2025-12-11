# app/file_access/protocols/__init__.py
"""
Protocol adapters for NAS provider.

Each protocol adapter implements the FileStorageProvider interface
for a specific network filesystem protocol (SMB, NFS, WebDAV, SFTP, etc.).
"""

from app.file_access.protocols.smb_protocol import SMBProtocolAdapter

__all__ = [
    "SMBProtocolAdapter",
]
