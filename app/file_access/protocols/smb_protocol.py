# app/file_access/protocols/smb_protocol.py
"""
SMB/CIFS protocol adapter for network file access.

Uses pysmb library to implement FileStorageProvider interface for SMB shares.
"""
import asyncio
import fnmatch
import io
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, AsyncIterator

import structlog
from smb.SMBConnection import SMBConnection
from smb.smb_structs import OperationFailure
from nmb.NetBIOS import NetBIOS

from app.file_access.base_fs import (
    FileInfo,
    FileOperationResult,
    HealthCheckResult,
    FileStorageProvider
)

logger = structlog.get_logger()


class SMBProtocolAdapter(FileStorageProvider):
    """
    SMB/CIFS protocol adapter.
    
    Configuration (file_config):
    {
        "host": "192.168.1.100",           # SMB server hostname/IP
        "share": "shared_folder",          # Share name
        "username": "user",                # SMB username
        "password": "pass",                # SMB password
        "domain": "WORKGROUP",             # Domain/workgroup (optional, default: WORKGROUP)
        "base_path": "/subfolder",         # Base path within share (optional, default: /)
        "port": 445,                       # SMB port (optional, default: 445)
        "client_name": "edilcos_client",   # Client machine name (optional, default: edilcos_client)
        "use_ntlm_v2": true                # Use NTLMv2 (optional, default: true)
    }
    
    Example tenant configuration:
    {
        "file_provider": "nas",
        "file_config": {
            "protocol": "smb",
            "host": "nas.company.local",
            "share": "documents",
            "username": "edilcos_app",
            "password": "secret",
            "base_path": "/tenant_acme"
        }
    }
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize SMB adapter.
        
        Args:
            config: SMB configuration dictionary
        """
        self.config = config
        self.host = config["host"]
        self.share = config["share"]
        self.username = config["username"]
        self.password = config["password"]
        self.domain = config.get("domain", "WORKGROUP")
        self.base_path = config.get("base_path", "/").rstrip("/")
        self.port = config.get("port", 445)
        self.client_name = config.get("client_name", "edilcos_client")
        self.use_ntlm_v2 = config.get("use_ntlm_v2", True)
        
        self._conn: Optional[SMBConnection] = None
        self._connected = False
        
        logger.info(
            "smb_adapter_initialized",
            host=self.host,
            share=self.share,
            base_path=self.base_path
        )
    
    def _normalize_path(self, path: str) -> str:
        """
        Normalize path for SMB operations.
        
        Combines base_path with provided path and ensures proper format.
        SMB paths use forward slashes, no leading slash for pysmb.
        
        Args:
            path: Relative path from base_path
            
        Returns:
            Normalized path for SMB operations
        """
        # Combine base_path and path
        if self.base_path == "/":
            full_path = path
        else:
            full_path = f"{self.base_path}/{path}".replace("//", "/")
        
        # Remove leading slash (pysmb expects paths without leading slash)
        full_path = full_path.lstrip("/")
        
        # Ensure forward slashes
        full_path = full_path.replace("\\", "/")
        
        return full_path
    
    def _path_to_parent(self, path: str) -> tuple[str, str]:
        """
        Split path into parent directory and filename.
        
        Args:
            path: Full path
            
        Returns:
            Tuple of (parent_dir, filename)
        """
        normalized = self._normalize_path(path)
        if "/" not in normalized:
            return "", normalized
        
        parts = normalized.rsplit("/", 1)
        return parts[0], parts[1]
    
    async def connect(self) -> None:
        """
        Establish connection to SMB server.
        
        Raises:
            ConnectionError: If connection fails
        """
        try:
            logger.info("smb_connecting", host=self.host, share=self.share)
            
            # Create connection (pysmb is synchronous, run in executor)
            loop = asyncio.get_event_loop()
            
            def _connect():
                # Resolve NetBIOS name if needed
                server_name = self.host
                if not self.host.replace(".", "").isdigit():
                    # Hostname provided, try to resolve NetBIOS name
                    try:
                        nb = NetBIOS()
                        names = nb.queryIPForName(self.host)
                        if names:
                            server_name = names[0]
                        nb.close()
                    except Exception as e:
                        logger.warning("netbios_resolution_failed", error=str(e))
                        # Continue with provided hostname
                
                # Create SMB connection
                conn = SMBConnection(
                    username=self.username,
                    password=self.password,
                    my_name=self.client_name,
                    remote_name=server_name,
                    domain=self.domain,
                    use_ntlm_v2=self.use_ntlm_v2,
                    is_direct_tcp=True
                )
                
                # Connect
                success = conn.connect(self.host, self.port)
                if not success:
                    raise ConnectionError(f"Failed to connect to {self.host}:{self.port}")
                
                return conn
            
            self._conn = await loop.run_in_executor(None, _connect)
            self._connected = True
            
            logger.info("smb_connected", host=self.host)
            
        except Exception as e:
            logger.error("smb_connection_failed", host=self.host, error=str(e))
            raise ConnectionError(f"SMB connection failed: {e}") from e
    
    async def disconnect(self) -> None:
        """Disconnect from SMB server."""
        if self._conn:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._conn.close)
                logger.info("smb_disconnected", host=self.host)
            except Exception as e:
                logger.warning("smb_disconnect_error", error=str(e))
            finally:
                self._conn = None
                self._connected = False
    
    def _ensure_connected(self) -> None:
        """Ensure connection is active."""
        if not self._connected or not self._conn:
            raise ConnectionError("Not connected to SMB server. Call connect() first.")
    
    async def list_files(
        self,
        path: str = "/",
        pattern: Optional[str] = None,
        recursive: bool = False
    ) -> List[FileInfo]:
        """
        List files in directory.
        
        Args:
            path: Directory path
            pattern: Glob pattern to filter files (e.g., "*.xlsx")
            recursive: Whether to list recursively
            
        Returns:
            List of FileInfo objects
            
        Raises:
            FileNotFoundError: If path does not exist
            NotADirectoryError: If path is not a directory
        """
        self._ensure_connected()
        
        try:
            normalized_path = self._normalize_path(path)
            
            loop = asyncio.get_event_loop()
            
            def _list_dir(dir_path: str) -> List[FileInfo]:
                results = []
                
                try:
                    # List directory contents
                    entries = self._conn.listPath(self.share, dir_path or "/")
                    
                    for entry in entries:
                        # Skip . and ..
                        if entry.filename in (".", ".."):
                            continue
                        
                        # Build full path
                        if dir_path:
                            full_path = f"{dir_path}/{entry.filename}"
                        else:
                            full_path = entry.filename
                        
                        # Create FileInfo
                        file_info = FileInfo(
                            path=full_path,
                            name=entry.filename,
                            size=entry.file_size,
                            is_directory=entry.isDirectory,
                            modified_at=datetime.fromtimestamp(entry.last_write_time),
                            created_at=datetime.fromtimestamp(entry.create_time),
                            mime_type=None,  # SMB doesn't provide MIME type
                            metadata={
                                "is_readonly": entry.isReadOnly,
                                "is_hidden": entry.isHidden,
                                "is_archive": entry.isArchive,
                                "short_name": entry.short_name,
                            }
                        )
                        
                        # Apply pattern filter
                        if pattern and not entry.isDirectory:
                            if not fnmatch.fnmatch(entry.filename, pattern):
                                continue
                        
                        results.append(file_info)
                        
                        # Recurse into subdirectories
                        if recursive and entry.isDirectory:
                            sub_results = _list_dir(full_path)
                            results.extend(sub_results)
                    
                    return results
                    
                except OperationFailure as e:
                    if "STATUS_OBJECT_NAME_NOT_FOUND" in str(e):
                        raise FileNotFoundError(f"Path not found: {path}")
                    elif "STATUS_NOT_A_DIRECTORY" in str(e):
                        raise NotADirectoryError(f"Not a directory: {path}")
                    raise
            
            files = await loop.run_in_executor(None, _list_dir, normalized_path)
            
            logger.debug(
                "smb_list_files",
                path=path,
                count=len(files),
                pattern=pattern,
                recursive=recursive
            )
            
            return files
            
        except Exception as e:
            logger.error("smb_list_files_failed", path=path, error=str(e))
            raise
    
    async def read_file(self, path: str) -> bytes:
        """
        Read file contents.
        
        Args:
            path: File path
            
        Returns:
            File contents as bytes
            
        Raises:
            FileNotFoundError: If file does not exist
        """
        self._ensure_connected()
        
        try:
            normalized_path = self._normalize_path(path)
            
            loop = asyncio.get_event_loop()
            
            def _read():
                buffer = io.BytesIO()
                self._conn.retrieveFile(self.share, normalized_path, buffer)
                return buffer.getvalue()
            
            data = await loop.run_in_executor(None, _read)
            
            logger.debug("smb_read_file", path=path, size=len(data))
            return data
            
        except OperationFailure as e:
            if "STATUS_OBJECT_NAME_NOT_FOUND" in str(e):
                raise FileNotFoundError(f"File not found: {path}")
            logger.error("smb_read_file_failed", path=path, error=str(e))
            raise
        except Exception as e:
            logger.error("smb_read_file_failed", path=path, error=str(e))
            raise
    
    async def write_file(
        self,
        path: str,
        data: bytes,
        overwrite: bool = False
    ) -> FileOperationResult:
        """
        Write file contents.
        
        Args:
            path: File path
            data: File contents
            overwrite: Whether to overwrite existing file
            
        Returns:
            FileOperationResult with operation status
            
        Raises:
            FileExistsError: If file exists and overwrite=False
        """
        self._ensure_connected()
        
        try:
            normalized_path = self._normalize_path(path)
            
            # Check if file exists
            if not overwrite:
                exists = await self.file_exists(path)
                if exists:
                    raise FileExistsError(f"File already exists: {path}")
            
            # Ensure parent directory exists
            parent_dir, filename = self._path_to_parent(path)
            if parent_dir:
                await self.mkdir(parent_dir, parents=True)
            
            loop = asyncio.get_event_loop()
            
            def _write():
                buffer = io.BytesIO(data)
                self._conn.storeFile(self.share, normalized_path, buffer)
            
            await loop.run_in_executor(None, _write)
            
            logger.info("smb_write_file", path=path, size=len(data))
            
            return FileOperationResult(
                success=True,
                path=path,
                message="File written successfully"
            )
            
        except FileExistsError:
            raise
        except Exception as e:
            logger.error("smb_write_file_failed", path=path, error=str(e))
            return FileOperationResult(
                success=False,
                path=path,
                error=str(e)
            )
    
    async def delete_file(self, path: str) -> FileOperationResult:
        """
        Delete file.
        
        Args:
            path: File path
            
        Returns:
            FileOperationResult with operation status
        """
        self._ensure_connected()
        
        try:
            normalized_path = self._normalize_path(path)
            
            loop = asyncio.get_event_loop()
            
            def _delete():
                self._conn.deleteFiles(self.share, normalized_path)
            
            await loop.run_in_executor(None, _delete)
            
            logger.info("smb_delete_file", path=path)
            
            return FileOperationResult(
                success=True,
                path=path,
                message="File deleted successfully"
            )
            
        except OperationFailure as e:
            if "STATUS_OBJECT_NAME_NOT_FOUND" in str(e):
                logger.warning("smb_delete_file_not_found", path=path)
                return FileOperationResult(
                    success=False,
                    path=path,
                    error="File not found"
                )
            logger.error("smb_delete_file_failed", path=path, error=str(e))
            return FileOperationResult(
                success=False,
                path=path,
                error=str(e)
            )
        except Exception as e:
            logger.error("smb_delete_file_failed", path=path, error=str(e))
            return FileOperationResult(
                success=False,
                path=path,
                error=str(e)
            )
    
    async def move_file(
        self,
        source: str,
        destination: str,
        overwrite: bool = False
    ) -> FileOperationResult:
        """
        Move/rename file.
        
        Args:
            source: Source file path
            destination: Destination file path
            overwrite: Whether to overwrite existing file
            
        Returns:
            FileOperationResult with operation status
        """
        self._ensure_connected()
        
        try:
            normalized_source = self._normalize_path(source)
            normalized_dest = self._normalize_path(destination)
            
            # Check if destination exists
            if not overwrite:
                dest_exists = await self.file_exists(destination)
                if dest_exists:
                    raise FileExistsError(f"Destination already exists: {destination}")
            else:
                # Delete destination if it exists
                dest_exists = await self.file_exists(destination)
                if dest_exists:
                    await self.delete_file(destination)
            
            # Ensure parent directory exists
            parent_dir, _ = self._path_to_parent(destination)
            if parent_dir:
                await self.mkdir(parent_dir, parents=True)
            
            loop = asyncio.get_event_loop()
            
            def _rename():
                self._conn.rename(self.share, normalized_source, normalized_dest)
            
            await loop.run_in_executor(None, _rename)
            
            logger.info("smb_move_file", source=source, destination=destination)
            
            return FileOperationResult(
                success=True,
                path=destination,
                message="File moved successfully"
            )
            
        except FileExistsError as e:
            return FileOperationResult(
                success=False,
                path=destination,
                error=str(e)
            )
        except Exception as e:
            logger.error("smb_move_file_failed", source=source, destination=destination, error=str(e))
            return FileOperationResult(
                success=False,
                path=destination,
                error=str(e)
            )
    
    async def copy_file(
        self,
        source: str,
        destination: str,
        overwrite: bool = False
    ) -> FileOperationResult:
        """
        Copy file.
        
        SMB protocol doesn't have native copy operation,
        so we read and write.
        
        Args:
            source: Source file path
            destination: Destination file path
            overwrite: Whether to overwrite existing file
            
        Returns:
            FileOperationResult with operation status
        """
        try:
            # Read source
            data = await self.read_file(source)
            
            # Write to destination
            result = await self.write_file(destination, data, overwrite=overwrite)
            
            if result.success:
                logger.info("smb_copy_file", source=source, destination=destination)
            
            return result
            
        except Exception as e:
            logger.error("smb_copy_file_failed", source=source, destination=destination, error=str(e))
            return FileOperationResult(
                success=False,
                path=destination,
                error=str(e)
            )
    
    async def mkdir(self, path: str, parents: bool = False) -> FileOperationResult:
        """
        Create directory.
        
        Args:
            path: Directory path
            parents: Whether to create parent directories
            
        Returns:
            FileOperationResult with operation status
        """
        self._ensure_connected()
        
        try:
            normalized_path = self._normalize_path(path)
            
            loop = asyncio.get_event_loop()
            
            def _mkdir(dir_path: str):
                # Check if already exists
                try:
                    self._conn.listPath(self.share, dir_path)
                    # Directory exists
                    return
                except OperationFailure:
                    pass
                
                # Create directory
                self._conn.createDirectory(self.share, dir_path)
            
            if parents:
                # Create parent directories recursively
                parts = normalized_path.split("/")
                current = ""
                for part in parts:
                    if not part:
                        continue
                    current = f"{current}/{part}" if current else part
                    await loop.run_in_executor(None, _mkdir, current)
            else:
                await loop.run_in_executor(None, _mkdir, normalized_path)
            
            logger.info("smb_mkdir", path=path, parents=parents)
            
            return FileOperationResult(
                success=True,
                path=path,
                message="Directory created successfully"
            )
            
        except Exception as e:
            logger.error("smb_mkdir_failed", path=path, error=str(e))
            return FileOperationResult(
                success=False,
                path=path,
                error=str(e)
            )
    
    async def rmdir(self, path: str, recursive: bool = False) -> FileOperationResult:
        """
        Remove directory.
        
        Args:
            path: Directory path
            recursive: Whether to remove contents recursively
            
        Returns:
            FileOperationResult with operation status
        """
        self._ensure_connected()
        
        try:
            normalized_path = self._normalize_path(path)
            
            loop = asyncio.get_event_loop()
            
            def _rmdir(dir_path: str):
                if recursive:
                    # List and delete all contents first
                    entries = self._conn.listPath(self.share, dir_path)
                    for entry in entries:
                        if entry.filename in (".", ".."):
                            continue
                        
                        full_path = f"{dir_path}/{entry.filename}"
                        
                        if entry.isDirectory:
                            _rmdir(full_path)
                        else:
                            self._conn.deleteFiles(self.share, full_path)
                
                # Delete the directory itself
                self._conn.deleteDirectory(self.share, dir_path)
            
            await loop.run_in_executor(None, _rmdir, normalized_path)
            
            logger.info("smb_rmdir", path=path, recursive=recursive)
            
            return FileOperationResult(
                success=True,
                path=path,
                message="Directory removed successfully"
            )
            
        except Exception as e:
            logger.error("smb_rmdir_failed", path=path, error=str(e))
            return FileOperationResult(
                success=False,
                path=path,
                error=str(e)
            )
    
    async def file_exists(self, path: str) -> bool:
        """
        Check if file/directory exists.
        
        Args:
            path: File/directory path
            
        Returns:
            True if exists, False otherwise
        """
        self._ensure_connected()
        
        try:
            normalized_path = self._normalize_path(path)
            parent_dir, filename = self._path_to_parent(path)
            
            loop = asyncio.get_event_loop()
            
            def _exists():
                # List parent directory and check if filename exists
                parent_path = self._normalize_path(parent_dir) if parent_dir else ""
                entries = self._conn.listPath(self.share, parent_path or "/")
                
                for entry in entries:
                    if entry.filename == filename:
                        return True
                return False
            
            exists = await loop.run_in_executor(None, _exists)
            return exists
            
        except Exception as e:
            logger.debug("smb_file_exists_check_failed", path=path, error=str(e))
            return False
    
    async def get_file_info(self, path: str) -> FileInfo:
        """
        Get file/directory metadata.
        
        Args:
            path: File/directory path
            
        Returns:
            FileInfo object
            
        Raises:
            FileNotFoundError: If file does not exist
        """
        self._ensure_connected()
        
        try:
            normalized_path = self._normalize_path(path)
            parent_dir, filename = self._path_to_parent(path)
            
            loop = asyncio.get_event_loop()
            
            def _get_info():
                parent_path = self._normalize_path(parent_dir) if parent_dir else ""
                entries = self._conn.listPath(self.share, parent_path or "/")
                
                for entry in entries:
                    if entry.filename == filename:
                        return FileInfo(
                            path=normalized_path,
                            name=entry.filename,
                            size=entry.file_size,
                            is_directory=entry.isDirectory,
                            modified_at=datetime.fromtimestamp(entry.last_write_time),
                            created_at=datetime.fromtimestamp(entry.create_time),
                            mime_type=None,
                            metadata={
                                "is_readonly": entry.isReadOnly,
                                "is_hidden": entry.isHidden,
                                "is_archive": entry.isArchive,
                                "short_name": entry.short_name,
                            }
                        )
                
                raise FileNotFoundError(f"File not found: {path}")
            
            info = await loop.run_in_executor(None, _get_info)
            return info
            
        except FileNotFoundError:
            raise
        except Exception as e:
            logger.error("smb_get_file_info_failed", path=path, error=str(e))
            raise
    
    async def health_check(self) -> HealthCheckResult:
        """
        Check SMB connection health.
        
        Returns:
            HealthCheckResult with status and details
        """
        checks = {}
        
        try:
            # Test connection
            if not self._connected:
                await self.connect()
            
            checks["connection"] = "ok"
            
            # Test share access
            loop = asyncio.get_event_loop()
            
            def _test_share():
                # Try to list root of share
                self._conn.listPath(self.share, "/")
            
            await loop.run_in_executor(None, _test_share)
            checks["share_access"] = "ok"
            
            # Test base_path access if configured
            if self.base_path != "/":
                base_exists = await self.file_exists("/")
                checks["base_path_access"] = "ok" if base_exists else "warning"
            
            # All checks passed
            return HealthCheckResult(
                healthy=True,
                details=checks,
                message="SMB connection healthy"
            )
            
        except Exception as e:
            logger.error("smb_health_check_failed", error=str(e))
            checks["error"] = str(e)
            
            return HealthCheckResult(
                healthy=False,
                details=checks,
                message=f"SMB health check failed: {e}"
            )
