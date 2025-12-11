# File Access Abstraction Layer (FAAL) Documentation

**Version:** 1.0  
**Date:** 11 December 2025  
**Status:** Production Ready ✅

---

## Overview

The File Access Abstraction Layer (FAAL) provides a unified interface for accessing different file storage backends in the Edilcos Automation Backend. This allows each tenant to choose their preferred storage provider without modifying application code.

### Supported Providers

- **LocalFS**: Local filesystem / NAS (any mounted storage)
- **OneDrive**: Microsoft OneDrive via Graph API
- **Future**: Google Drive, AWS S3, Azure Blob Storage, etc.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Application Layer                            │
│              (PreventiviV1, Scheduler Jobs, etc.)                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │  get_file_provider() │
                  │      (Registry)      │
                  └──────────┬───────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
      ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
      │ LocalFS      │ │ OneDrive     │ │ GoogleDrive  │
      │ Provider     │ │ Provider     │ │ Provider     │
      └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
             │                │                │
             ▼                ▼                ▼
      ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
      │ Local/NAS    │ │ MS Graph API │ │ GDrive API   │
      │ Filesystem   │ │              │ │              │
      └──────────────┘ └──────────────┘ └──────────────┘
```

---

## Components

### 1. Base Interface (`app/file_access/base.py`)

Abstract base class defining the provider interface:

```python
class FileStorageProvider(ABC):
    async def update_quote_excel(tenant_id, quote, customer) -> FileOperationResult
    async def read_file(path: str) -> bytes
    async def write_file(path: str, data: bytes) -> FileOperationResult
    async def file_exists(path: str) -> bool
    async def get_metadata(path: str) -> FileMetadata
    async def list_files(directory: str) -> List[FileMetadata]
    async def delete_file(path: str) -> FileOperationResult
    async def create_directory(path: str) -> FileOperationResult
    async def health_check() -> Dict[str, Any]
```

### 2. LocalFS Provider (`app/file_access/localfs_provider.py`)

**Purpose:** Generic local filesystem provider for any NAS or local storage.

**Features:**
- Works with any mounted filesystem (NFS, SMB/CIFS, local directories)
- Thread-safe Excel updates using FileLock
- Creates Excel file with headers if it doesn't exist
- Updates existing rows or appends new ones
- Path security (prevents access outside base_path)

**Configuration:**
```json
{
  "base_path": "/mnt/edilcos_nas/preventivi",
  "excel_filename": "preventivi.xlsx",
  "lock_timeout": 30,
  "create_dirs": true
}
```

**Usage Example:**
```python
provider = LocalFSProvider({
    "base_path": "/mnt/nas/edilcos",
    "excel_filename": "preventivi.xlsx"
})

result = await provider.update_quote_excel(tenant_id, quote, customer)
if result.success:
    print(f"Excel updated: {result.file_path}")
```

### 3. OneDrive Provider (`app/file_access/onedrive_provider.py`)

**Purpose:** Wrapper around existing OneDriveConnector.

**Features:**
- Enqueues Excel updates via existing OneDrive integration
- Async processing via scheduler jobs
- Health check validates token and drive access

**Configuration:**
```json
{
  "tenant_id": "azure-tenant-id",
  "client_id": "app-client-id",
  "client_secret": "app-secret",
  "drive_id": "onedrive-drive-id",
  "excel_file_id": "excel-file-id"
}
```

**Note:** Most file operations (read/write/delete) are not implemented as the existing integration only handles Excel updates. To extend, implement using Microsoft Graph API.

### 4. Provider Registry (`app/file_access/registry.py`)

**Purpose:** Factory for instantiating providers.

**Functions:**

```python
# Get provider for tenant
provider = get_file_provider(tenant)

# Get provider by name
provider = get_provider_by_name("localfs", config)

# Register custom provider
register_provider("custom_nas", CustomNASProvider)

# List available providers
providers = list_providers()  # ["localfs", "onedrive", ...]
```

---

## Database Schema

### Tenant Model Updates

```sql
ALTER TABLE tenants ADD COLUMN file_provider VARCHAR;
ALTER TABLE tenants ADD COLUMN file_config JSON;
```

**Fields:**
- `file_provider`: Provider identifier ("localfs", "onedrive", "gdrive", etc.)
- `file_config`: Provider-specific JSON configuration

**Example:**
```sql
UPDATE tenants 
SET file_provider = 'localfs',
    file_config = '{"base_path": "/mnt/nas/edilcos", "excel_filename": "preventivi.xlsx"}'::json
WHERE id = 'tenant-123';
```

---

## Integration Points

### 1. PreventiviV1 Service

**Before:**
```python
from app.integrations.onedrive_api import OneDriveConnector

onedrive = OneDriveConnector()
await onedrive.enqueue_excel_update(quote)
```

**After:**
```python
from app.file_access.registry import get_file_provider

tenant = await tenant_repo.get_by_id(tenant_id)
if tenant and tenant.file_provider:
    provider = get_file_provider(tenant)
    customer_dict = {"name": customer.name, "email": customer.email, "phone": customer.phone}
    result = await provider.update_quote_excel(tenant_id, quote, customer_dict)
    if result.success:
        log("INFO", f"Excel updated: {result.message}")
```

### 2. Scheduler Jobs

**Before:**
```python
from app.integrations.onedrive_api import update_quote_excel

await update_quote_excel(quote.tenant_id, quote, customer)
```

**After:**
```python
from app.file_access.registry import get_file_provider

tenant = await tenant_repo.get_by_id(quote.tenant_id)
if tenant and tenant.file_provider:
    provider = get_file_provider(tenant)
    customer_dict = {"name": customer.name, "email": customer.email, "phone": customer.phone}
    result = await provider.update_quote_excel(quote.tenant_id, quote, customer_dict)
```

### 3. Health Checks

**Endpoint:** `GET /admin/health/deep`

**Response:**
```json
{
  "status": "ready",
  "database": {"healthy": true, "message": "Database ready"},
  "file_providers": {
    "total": 2,
    "healthy": 2,
    "unhealthy": 0,
    "checks": [
      {
        "tenant_id": "edilcos-main",
        "tenant_name": "Edilcos Main",
        "provider": "localfs",
        "healthy": true,
        "message": "LocalFS provider healthy",
        "details": {
          "base_path": "/mnt/nas/edilcos",
          "checks": {
            "base_path_exists": true,
            "base_path_readable": true,
            "base_path_writable": true,
            "disk_space_available": "125.34 GB"
          }
        }
      },
      {
        "tenant_id": "edilcos-cloud",
        "tenant_name": "Edilcos Cloud",
        "provider": "onedrive",
        "healthy": true,
        "message": "OneDrive provider healthy",
        "details": {
          "checks": {
            "token_acquired": true,
            "drive_accessible": true,
            "excel_file_exists": true
          }
        }
      }
    ]
  }
}
```

---

## Configuration Guide

### LocalFS Provider (NAS/Local Storage)

**Use when:**
- You have a NAS (Synology, QNAP, etc.) mounted to the server
- You want to use local filesystem storage
- You need immediate, synchronous file operations

**Setup:**

1. **Mount NAS to server:**
   ```bash
   # NFS mount
   sudo mount -t nfs nas.local:/volume1/edilcos /mnt/edilcos_nas
   
   # CIFS/SMB mount
   sudo mount -t cifs //nas.local/edilcos /mnt/edilcos_nas -o username=user,password=pass
   ```

2. **Configure tenant:**
   ```sql
   UPDATE tenants 
   SET file_provider = 'localfs',
       file_config = '{
         "base_path": "/mnt/edilcos_nas/preventivi",
         "excel_filename": "preventivi.xlsx",
         "lock_timeout": 30,
         "create_dirs": true
       }'::json
   WHERE name = 'Edilcos Main';
   ```

3. **Verify health:**
   ```bash
   curl http://localhost:8000/admin/health/deep
   ```

**Configuration Options:**

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `base_path` | Yes | - | Absolute path to storage directory |
| `excel_filename` | No | `"preventivi.xlsx"` | Name of Excel file |
| `lock_timeout` | No | `30` | Seconds to wait for file lock |
| `create_dirs` | No | `true` | Auto-create directories if missing |

### OneDrive Provider

**Use when:**
- You want cloud storage via Microsoft OneDrive
- You already have OneDrive configured
- You need multi-device access

**Setup:**

1. **Register Azure AD application** (if not done):
   - Go to https://portal.azure.com
   - Create App Registration
   - Grant Microsoft Graph API permissions
   - Create client secret

2. **Configure tenant:**
   ```sql
   UPDATE tenants 
   SET file_provider = 'onedrive',
       file_config = '{
         "tenant_id": "your-azure-tenant-id",
         "client_id": "your-client-id",
         "client_secret": "your-client-secret",
         "drive_id": "your-drive-id",
         "excel_file_id": "your-excel-file-id"
       }'::json
   WHERE name = 'Edilcos Cloud';
   ```

3. **Verify health:**
   ```bash
   curl http://localhost:8000/admin/health/deep
   ```

**Configuration Options:**

| Field | Required | Description |
|-------|----------|-------------|
| `tenant_id` | Yes | Azure AD tenant ID |
| `client_id` | Yes | Application (client) ID |
| `client_secret` | Yes | Application client secret |
| `drive_id` | Yes | OneDrive drive ID |
| `excel_file_id` | Yes | Excel file ID in OneDrive |

---

## Adding New Providers

### Step 1: Implement Provider Class

Create `app/file_access/custom_provider.py`:

```python
from app.file_access.base import FileStorageProvider, FileOperationResult
from typing import Dict, Any

class CustomProvider(FileStorageProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Initialize with config
        self.api_key = config["api_key"]
    
    async def update_quote_excel(self, tenant_id, quote, customer):
        # Implement Excel update logic
        try:
            # Your logic here
            return FileOperationResult(
                success=True,
                message="Excel updated successfully"
            )
        except Exception as exc:
            return FileOperationResult(
                success=False,
                message=f"Update failed: {exc}"
            )
    
    async def read_file(self, path: str) -> bytes:
        # Implement file read
        pass
    
    async def write_file(self, path: str, data: bytes):
        # Implement file write
        pass
    
    async def file_exists(self, path: str) -> bool:
        # Check if file exists
        pass
    
    async def get_metadata(self, path: str):
        # Get file metadata
        pass
    
    async def list_files(self, directory: str):
        # List files in directory
        pass
    
    async def delete_file(self, path: str):
        # Delete file
        pass
    
    async def create_directory(self, path: str):
        # Create directory
        pass
    
    async def health_check(self):
        # Check provider health
        return {
            "healthy": True,
            "provider": "custom",
            "message": "Custom provider healthy"
        }
```

### Step 2: Register Provider

In `app/file_access/registry.py`:

```python
from app.file_access.custom_provider import CustomProvider

PROVIDER_REGISTRY: Dict[str, type] = {
    "localfs": LocalFSProvider,
    "onedrive": OneDriveProvider,
    "custom": CustomProvider,  # Add here
}
```

Or dynamically:

```python
from app.file_access.registry import register_provider
from app.file_access.custom_provider import CustomProvider

register_provider("custom", CustomProvider)
```

### Step 3: Configure Tenant

```sql
UPDATE tenants 
SET file_provider = 'custom',
    file_config = '{"api_key": "your-key", ...}'::json
WHERE name = 'Custom Tenant';
```

---

## Testing

### Run Tests

```bash
# Run all FAAL tests
pytest tests/test_file_access.py -v

# Run specific test
pytest tests/test_file_access.py::TestLocalFSProvider::test_update_quote_excel -v

# Run with coverage
pytest tests/test_file_access.py --cov=app/file_access --cov-report=html
```

### Test Coverage

- LocalFSProvider: ✅ Full coverage (write, read, Excel, health)
- OneDriveProvider: ✅ Wrapper tests (initialization, unsupported ops)
- Registry: ✅ Factory tests (get, register, list)
- E2E: ✅ Complete quote workflow

### Manual Testing

**LocalFS Provider:**

```python
from app.file_access.localfs_provider import LocalFSProvider

provider = LocalFSProvider({
    "base_path": "/tmp/test_faal",
    "excel_filename": "test.xlsx"
})

# Health check
health = await provider.health_check()
print(health)

# Write file
result = await provider.write_file("test.txt", b"Hello FAAL")
print(result)

# Read file
data = await provider.read_file("test.txt")
print(data)
```

**OneDrive Provider:**

```python
from app.file_access.onedrive_provider import OneDriveProvider

provider = OneDriveProvider({
    "tenant_id": "your-tenant-id",
    "client_id": "your-client-id",
    "client_secret": "your-secret",
    "drive_id": "your-drive-id",
    "excel_file_id": "your-file-id"
})

# Health check
health = await provider.health_check()
print(health)
```

---

## Monitoring & Observability

### Logs

All provider operations are logged with structured logging:

```json
{
  "timestamp": "2025-12-11T10:30:45Z",
  "level": "INFO",
  "message": "Excel updated for quote quote-123",
  "module": "localfs_provider",
  "tenant_id": "edilcos-main",
  "request_id": "req-456"
}
```

### Audit Events

File operations generate audit events:

```python
await audit_event("file_provider_excel_update", tenant_id, flow_id, {
    "quote_id": str(quote.id),
    "provider": "localfs",
    "success": True,
    "file_path": "/mnt/nas/edilcos/preventivi.xlsx"
})
```

### Health Monitoring

Monitor provider health via `/admin/health/deep`:

```bash
# Check all providers
curl http://localhost:8000/admin/health/deep | jq '.file_providers'

# Expected output:
{
  "total": 2,
  "healthy": 2,
  "unhealthy": 0,
  "checks": [...]
}
```

Set up alerts for unhealthy providers:

```python
health = await provider.health_check()
if not health["healthy"]:
    await send_slack_alert(
        f"File provider unhealthy: {health['message']}",
        context=health["details"],
        severity="CRITICAL"
    )
```

---

## Troubleshooting

### LocalFS Provider Issues

**Problem:** `PermissionError: Access denied`

**Solution:**
```bash
# Check directory permissions
ls -la /mnt/edilcos_nas

# Fix permissions
sudo chown edilcos:edilcos /mnt/edilcos_nas
sudo chmod 755 /mnt/edilcos_nas
```

**Problem:** `Timeout: Failed to acquire file lock`

**Solution:**
- Another process is using the file
- Increase `lock_timeout` in config
- Check for stale lock files (`.lock`)

```python
# Remove stale lock
import os
os.remove("/path/to/preventivi.xlsx.lock")
```

**Problem:** `FileNotFoundError: base_path doesn't exist`

**Solution:**
```bash
# Create directory
sudo mkdir -p /mnt/edilcos_nas/preventivi

# Or enable auto-create in config
"create_dirs": true
```

### OneDrive Provider Issues

**Problem:** `Health check failed: cannot acquire token`

**Solution:**
- Verify Azure AD credentials
- Check client_id and client_secret
- Verify tenant_id is correct
- Check network connectivity to Azure

**Problem:** `Drive not accessible`

**Solution:**
- Verify drive_id is correct
- Check Graph API permissions
- Re-authenticate application

### General Issues

**Problem:** `Unknown file storage provider`

**Solution:**
```python
# Check available providers
from app.file_access.registry import list_providers
print(list_providers())

# Verify tenant.file_provider matches a registered provider
```

**Problem:** `Provider initialization failed`

**Solution:**
- Check tenant.file_config is valid JSON
- Verify all required config fields are present
- Check logs for detailed error message

---

## Performance Considerations

### LocalFS Provider

**Pros:**
- Fast: Direct filesystem access
- No network latency
- Synchronous operations
- Thread-safe with FileLock

**Cons:**
- Limited to single server (unless NAS)
- Requires mounted filesystem
- Lock contention under high load

**Optimization:**
- Use SSD for Excel files
- Mount NAS with appropriate options (async, noatime)
- Monitor disk I/O

### OneDrive Provider

**Pros:**
- Cloud storage
- Multi-device access
- Microsoft ecosystem integration

**Cons:**
- Network latency
- API rate limits
- Async only (enqueued updates)

**Optimization:**
- Batch updates when possible
- Use webhook notifications for real-time sync
- Cache frequently accessed files

---

## Security Considerations

### LocalFS Provider

1. **Path Security:**
   - All paths validated against base_path
   - Prevents directory traversal attacks
   - Example: `../../etc/passwd` → rejected

2. **File Permissions:**
   - Application runs as non-root user
   - NAS directories have restrictive permissions
   - Use ACLs for fine-grained control

3. **Lock Files:**
   - Prevent concurrent write conflicts
   - Timeout prevents indefinite locks

### OneDrive Provider

1. **Credential Storage:**
   - Client secrets stored in environment variables
   - Never commit secrets to git
   - Use Azure Key Vault in production

2. **Token Management:**
   - Tokens refreshed automatically
   - Short-lived access tokens
   - Minimal Graph API permissions

3. **Data Access:**
   - Application-only authentication (no user context)
   - Limited to configured drive/file
   - Audit all API calls

---

## Migration Guide

### Migrating from Direct OneDrive to FAAL

**Step 1:** Run database migration
```bash
psql -U edilcos -d edilcos_db -f migrations/002_add_file_provider.sql
```

**Step 2:** Configure tenants
```sql
-- For tenants using OneDrive
UPDATE tenants 
SET file_provider = 'onedrive',
    file_config = '{
      "tenant_id": "...",
      "client_id": "...",
      "client_secret": "...",
      "drive_id": "...",
      "excel_file_id": "..."
    }'::json
WHERE status = 'active';
```

**Step 3:** Deploy updated code
```bash
git pull
pip install -r requirements.txt
systemctl restart edilcos-backend
```

**Step 4:** Verify health
```bash
curl http://localhost:8000/admin/health/deep
```

### Migrating to LocalFS from OneDrive

**Step 1:** Mount NAS
```bash
sudo mount -t nfs nas.local:/volume1/edilcos /mnt/edilcos_nas
```

**Step 2:** Copy existing Excel files
```bash
# Download from OneDrive
# Copy to /mnt/edilcos_nas/preventivi/
```

**Step 3:** Update tenant config
```sql
UPDATE tenants 
SET file_provider = 'localfs',
    file_config = '{
      "base_path": "/mnt/edilcos_nas/preventivi",
      "excel_filename": "preventivi.xlsx"
    }'::json
WHERE id = 'tenant-id';
```

**Step 4:** Test
```bash
# Trigger quote processing
# Verify Excel updated in NAS
```

---

## Future Enhancements

### Planned Features

1. **Google Drive Provider**
   - Similar to OneDrive wrapper
   - Use Google Drive API
   - Support Sheets API for Excel

2. **AWS S3 Provider**
   - Cloud object storage
   - Supports any S3-compatible storage
   - High availability

3. **Azure Blob Storage Provider**
   - Alternative to OneDrive
   - Better for large files
   - Lower cost

4. **File Versioning**
   - Keep history of Excel changes
   - Rollback capability
   - Audit trail

5. **Caching Layer**
   - Cache frequently accessed files
   - Redis-based
   - Reduce provider load

6. **Async Background Sync**
   - Sync between providers
   - Backup from LocalFS to Cloud
   - Disaster recovery

### Contributing New Providers

To contribute a new provider:

1. Fork repository
2. Create `app/file_access/your_provider.py`
3. Implement `FileStorageProvider` interface
4. Add tests in `tests/test_file_access.py`
5. Update documentation
6. Submit pull request

---

## API Reference

See docstrings in:
- `app/file_access/base.py` - Base interface
- `app/file_access/localfs_provider.py` - LocalFS implementation
- `app/file_access/onedrive_provider.py` - OneDrive wrapper
- `app/file_access/registry.py` - Provider registry

---

## Support

For issues or questions:
- Check logs: `tail -f logs/app.log`
- Run health check: `curl /admin/health/deep`
- Review documentation
- Contact development team

---

**Document Version:** 1.0  
**Last Updated:** 11 December 2025  
**Status:** Production Ready ✅
