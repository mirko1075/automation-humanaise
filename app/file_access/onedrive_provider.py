# app/file_access/onedrive_provider.py
"""
OneDrive provider for FAAL.

Wraps the existing OneDriveConnector to conform to FileStorageProvider interface.
"""
import traceback
from datetime import datetime
from typing import Any, Dict, List
from app.file_access.base import FileStorageProvider, FileOperationResult, FileMetadata
from app.integrations.onedrive_api import (
    enqueue_excel_update,
    get_graph_client,
    update_excel_on_onedrive
)
from app.monitoring.logger import log
from app.config import settings


class OneDriveProvider(FileStorageProvider):
    """
    OneDrive provider wrapping existing OneDriveConnector.
    
    This provider wraps the existing OneDrive Excel integration.
    It enqueues Excel updates to be processed by scheduler jobs.
    
    Config schema:
    {
        "tenant_id": "...",  # OneDrive/Azure tenant ID
        "client_id": "...",  # Application client ID
        "client_secret": "...",  # Application secret
        "drive_id": "...",  # OneDrive drive ID
        "excel_file_id": "..."  # Excel file ID in OneDrive
    }
    
    Note: Most file operations (read/write/delete) are not supported
    as the existing integration only handles Excel updates via Graph API.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Validate required config
        required = ["tenant_id", "client_id", "client_secret", "drive_id", "excel_file_id"]
        for field in required:
            if field not in config:
                raise ValueError(f"OneDriveProvider requires '{field}' in config")
        
        self.tenant_id = config["tenant_id"]
        self.client_id = config["client_id"]
        self.client_secret = config["client_secret"]
        self.drive_id = config["drive_id"]
        self.excel_file_id = config["excel_file_id"]
        
        log("INFO", f"OneDriveProvider initialized for drive {self.drive_id}", 
            module="onedrive_provider")
    
    async def update_quote_excel(
        self,
        tenant_id: str,
        quote: Any,
        customer: Dict[str, Any]
    ) -> FileOperationResult:
        """
        Update Excel spreadsheet with quote data.
        
        Uses the existing OneDrive integration to enqueue Excel update.
        The actual update is performed asynchronously by scheduler jobs.
        """
        try:
            # Enqueue Excel update using existing function
            await enqueue_excel_update(quote)
            
            log("INFO", f"Excel update enqueued for quote {quote.id}", 
                module="onedrive_provider", tenant_id=tenant_id)
            
            return FileOperationResult(
                success=True,
                message=f"Excel update enqueued for quote {quote.id}",
                details={
                    "quote_id": str(quote.id),
                    "tenant_id": tenant_id,
                    "drive_id": self.drive_id,
                    "excel_file_id": self.excel_file_id,
                    "status": "PENDING"
                }
            )
        
        except Exception as exc:
            tb = traceback.format_exc()
            log("ERROR", f"OneDrive Excel enqueue error: {exc}", 
                module="onedrive_provider", tenant_id=tenant_id)
            return FileOperationResult(
                success=False,
                message=f"Failed to enqueue Excel update: {exc}",
                details={"error": str(exc), "traceback": tb}
            )
    
    async def read_file(self, path: str) -> bytes:
        """
        Read file from OneDrive.
        
        Not implemented: the existing integration doesn't support generic file reads.
        To implement, use Microsoft Graph API:
        GET /drives/{drive-id}/items/{item-id}/content
        """
        raise NotImplementedError(
            "OneDriveProvider does not support read_file. "
            "Use Microsoft Graph API directly for file downloads."
        )
    
    async def write_file(self, path: str, data: bytes) -> FileOperationResult:
        """
        Write file to OneDrive.
        
        Not implemented: the existing integration only handles Excel updates.
        To implement, use Microsoft Graph API:
        PUT /drives/{drive-id}/items/{parent-id}:/{filename}:/content
        """
        raise NotImplementedError(
            "OneDriveProvider does not support write_file. "
            "Use Microsoft Graph API directly for file uploads."
        )
    
    async def file_exists(self, path: str) -> bool:
        """
        Check if file exists in OneDrive.
        
        Not implemented: requires Microsoft Graph API call.
        To implement:
        GET /drives/{drive-id}/root:/{path}
        """
        raise NotImplementedError(
            "OneDriveProvider does not support file_exists. "
            "Use Microsoft Graph API directly."
        )
    
    async def get_metadata(self, path: str) -> FileMetadata:
        """
        Get file metadata from OneDrive.
        
        Not implemented: requires Microsoft Graph API call.
        """
        raise NotImplementedError(
            "OneDriveProvider does not support get_metadata. "
            "Use Microsoft Graph API directly."
        )
    
    async def list_files(self, directory: str) -> List[FileMetadata]:
        """
        List files in OneDrive directory.
        
        Not implemented: requires Microsoft Graph API call.
        To implement:
        GET /drives/{drive-id}/root:/{path}:/children
        """
        raise NotImplementedError(
            "OneDriveProvider does not support list_files. "
            "Use Microsoft Graph API directly."
        )
    
    async def delete_file(self, path: str) -> FileOperationResult:
        """
        Delete file from OneDrive.
        
        Not implemented: the existing integration doesn't support file deletion.
        To implement, use Microsoft Graph API:
        DELETE /drives/{drive-id}/items/{item-id}
        """
        raise NotImplementedError(
            "OneDriveProvider does not support delete_file. "
            "Use Microsoft Graph API directly."
        )
    
    async def create_directory(self, path: str) -> FileOperationResult:
        """
        Create directory in OneDrive.
        
        Not implemented: the existing integration doesn't support directory creation.
        To implement, use Microsoft Graph API:
        POST /drives/{drive-id}/items/{parent-id}/children
        """
        raise NotImplementedError(
            "OneDriveProvider does not support create_directory. "
            "Use Microsoft Graph API directly."
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check OneDrive provider health.
        
        Verifies:
        - Can obtain access token
        - Can access the configured drive
        - Excel file exists
        """
        checks = {
            "token_acquired": False,
            "drive_accessible": False,
            "excel_file_exists": False
        }
        
        try:
            # Try to get access token
            async with get_graph_client() as client:
                checks["token_acquired"] = True
                
                # Try to access drive
                drive_url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}"
                async with client.get(drive_url) as resp:
                    if resp.status == 200:
                        checks["drive_accessible"] = True
                        drive_data = await resp.json()
                    else:
                        log("WARNING", f"Drive access failed: {resp.status}", 
                            module="onedrive_provider")
                
                # Try to access Excel file
                file_url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/items/{self.excel_file_id}"
                async with client.get(file_url) as resp:
                    if resp.status == 200:
                        checks["excel_file_exists"] = True
                        file_data = await resp.json()
                    else:
                        log("WARNING", f"Excel file access failed: {resp.status}", 
                            module="onedrive_provider")
            
            # Determine overall health
            healthy = all(checks.values())
            
            if healthy:
                message = "OneDrive provider healthy"
            else:
                message = "OneDrive provider unhealthy: "
                issues = []
                if not checks["token_acquired"]:
                    issues.append("cannot acquire token")
                if not checks["drive_accessible"]:
                    issues.append("drive not accessible")
                if not checks["excel_file_exists"]:
                    issues.append("Excel file not found")
                message += ", ".join(issues)
            
            return {
                "healthy": healthy,
                "provider": "onedrive",
                "message": message,
                "details": {
                    "checks": checks,
                    "config": {
                        "tenant_id": self.tenant_id,
                        "drive_id": self.drive_id,
                        "excel_file_id": self.excel_file_id
                    }
                }
            }
        
        except Exception as exc:
            return {
                "healthy": False,
                "provider": "onedrive",
                "message": f"Health check failed: {exc}",
                "details": {
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "checks": checks
                }
            }
