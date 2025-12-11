# NAS Provider Guide

Complete guide for using and extending the Multi-Protocol NAS Provider in Edilcos backend.

## Table of Contents

1. [Overview](#overview)
2. [Supported Protocols](#supported-protocols)
3. [Configuration](#configuration)
4. [Usage Examples](#usage-examples)
5. [Protocol Adapter Development](#protocol-adapter-development)
6. [Document Operations](#document-operations)
7. [Migration Guide](#migration-guide)
8. [Troubleshooting](#troubleshooting)
9. [Performance Considerations](#performance-considerations)
10. [Security Best Practices](#security-best-practices)

---

## Overview

The NAS Provider is a multi-protocol file storage abstraction that allows tenants to connect to various network-attached storage systems through a unified interface. It supports multiple protocols (SMB, NFS, WebDAV, SFTP, FTP/S) with dynamic adapter loading.

### Key Features

- **Protocol-agnostic interface**: Business logic doesn't change when switching protocols
- **Dynamic adapter loading**: Protocols are loaded on-demand based on configuration
- **Document operations**: Protocol-independent Excel, PDF, and Word manipulation
- **Async/await support**: Fully asynchronous for high performance
- **Comprehensive error handling**: Graceful degradation and detailed logging
- **Type-safe**: Full type hints throughout
- **Extensible**: Easy to add new protocols

### Architecture

```
┌─────────────────────────────────────────────────┐
│           NASProvider (Orchestrator)            │
│  - Protocol detection                           │
│  - Adapter loading                              │
│  - Operation delegation                         │
└──────────────────┬──────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │  Protocol Registry  │
        │  (Dynamic Loading)  │
        └──────────┬──────────┘
                   │
     ┌─────────────┼─────────────┬──────────────┐
     │             │             │              │
┌────▼────┐  ┌────▼────┐  ┌────▼────┐   ┌─────▼─────┐
│   SMB   │  │   NFS   │  │ WebDAV  │   │   SFTP    │
│ Adapter │  │ Adapter │  │ Adapter │   │  Adapter  │
└─────────┘  └─────────┘  └─────────┘   └───────────┘
```

---

## Supported Protocols

### Currently Implemented

#### 1. SMB/CIFS (✅ Available)
- **Library**: `pysmb`
- **Use case**: Windows shares, Samba servers, NAS devices
- **Authentication**: Username/password, domain support
- **Features**: Full read/write, directory operations, file metadata

### Coming Soon

#### 2. NFS (📋 Placeholder)
- **Library**: `libnfs-python` (recommended)
- **Use case**: Unix/Linux NFS shares
- **Authentication**: Host-based
- **Features**: High performance for Linux environments

#### 3. WebDAV (📋 Placeholder)
- **Library**: `webdavclient3`
- **Use case**: Nextcloud, ownCloud, HTTP-based storage
- **Authentication**: Username/password, token
- **Features**: HTTP/S transport, SSL support

#### 4. SFTP (📋 Placeholder)
- **Library**: `paramiko`
- **Use case**: SSH file transfer
- **Authentication**: Password, public key
- **Features**: Secure encrypted transfer

#### 5. FTP/FTPS (📋 Placeholder)
- **Library**: Built-in `ftplib`
- **Use case**: Legacy FTP servers
- **Authentication**: Username/password
- **Features**: Optional TLS encryption

---

## Configuration

### Database Schema

Add to `Tenant` model:

```python
class Tenant(Base):
    __tablename__ = "tenants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    
    # File provider configuration
    file_provider = Column(String, nullable=True)  # "nas", "localfs", "onedrive"
    file_config = Column(JSON, nullable=True)      # Provider-specific config
```

### Protocol-Specific Configurations

#### SMB Configuration

```json
{
  "protocol": "smb",
  "host": "nas.company.local",
  "share": "documents",
  "username": "edilcos_app",
  "password": "secure_password",
  "domain": "WORKGROUP",
  "base_path": "/tenant_acme",
  "port": 445,
  "use_ntlm_v2": true
}
```

**Required fields:**
- `protocol`: Must be `"smb"`
- `host`: SMB server hostname or IP
- `share`: Share name on the server
- `username`: SMB username
- `password`: SMB password

**Optional fields:**
- `domain`: Domain/workgroup (default: `"WORKGROUP"`)
- `base_path`: Base directory within share (default: `"/"`)
- `port`: SMB port (default: `445`)
- `client_name`: Client machine name (default: `"edilcos_client"`)
- `use_ntlm_v2`: Use NTLMv2 authentication (default: `true`)

#### NFS Configuration (Future)

```json
{
  "protocol": "nfs",
  "host": "nfs.company.local",
  "export": "/exports/data",
  "base_path": "/tenant_acme",
  "version": 3,
  "mount_options": "rw,sync"
}
```

#### WebDAV Configuration (Future)

```json
{
  "protocol": "webdav",
  "url": "https://cloud.company.com/remote.php/dav",
  "username": "edilcos_app",
  "password": "secure_password",
  "base_path": "/files/edilcos_app/tenant_acme",
  "verify_ssl": true
}
```

#### SFTP Configuration (Future)

```json
{
  "protocol": "sftp",
  "host": "sftp.company.local",
  "port": 22,
  "username": "edilcos_app",
  "password": "secure_password",
  "base_path": "/data/tenant_acme"
}
```

Or with SSH key:

```json
{
  "protocol": "sftp",
  "host": "sftp.company.local",
  "port": 22,
  "username": "edilcos_app",
  "private_key_path": "/app/.ssh/id_rsa",
  "private_key_passphrase": "key_password",
  "base_path": "/data/tenant_acme"
}
```

---

## Usage Examples

### Basic File Operations

```python
from app.file_access.registry import get_file_provider

# Get tenant
tenant = await get_tenant(tenant_id)

# Get provider (automatically loads correct protocol)
provider = get_file_provider(tenant)

# Connect
async with provider:
    # List files
    files = await provider.list_files("/quotes", pattern="*.xlsx")
    for file in files:
        print(f"{file.name}: {file.size} bytes")
    
    # Read file
    data = await provider.read_file("/quotes/Q001.xlsx")
    print(f"Read {len(data)} bytes")
    
    # Write file
    result = await provider.write_file(
        "/quotes/Q002.xlsx",
        excel_bytes,
        overwrite=True
    )
    
    if result.success:
        print("File written successfully")
    else:
        print(f"Error: {result.error}")
    
    # Check if file exists
    exists = await provider.file_exists("/quotes/Q001.xlsx")
    
    # Get file metadata
    info = await provider.get_file_info("/quotes/Q001.xlsx")
    print(f"Modified: {info.modified_at}")
    print(f"Size: {info.size} bytes")
```

### Excel Operations (Protocol-Agnostic)

```python
from app.file_access.registry import get_file_provider
from app.file_access.document_ops import (
    read_excel,
    write_excel,
    update_excel,
    create_excel_from_data
)

# Get provider
tenant = await get_tenant(tenant_id)
provider = get_file_provider(tenant)

async with provider:
    # Read Excel
    workbook = await read_excel(provider, "/quotes/template.xlsx")
    worksheet = workbook.active
    print(f"Sheet: {worksheet.title}")
    
    # Update specific cells
    updates = {
        "A1": "Customer Name",
        "B1": "ACME Corp",
        "A2": "Amount",
        "B2": 1250.50
    }
    await update_excel(provider, "/quotes/Q001.xlsx", updates)
    
    # Create Excel from data
    data = [
        ["Product A", 10, 500.00],
        ["Product B", 5, 250.00],
    ]
    headers = ["Product", "Quantity", "Price"]
    
    await create_excel_from_data(
        provider,
        "/reports/sales.xlsx",
        data,
        headers=headers
    )
```

### PDF Operations (Protocol-Agnostic)

```python
from app.file_access.document_ops import (
    read_pdf_text,
    create_pdf,
    merge_pdfs,
    extract_pdf_metadata
)

async with provider:
    # Extract text from PDF
    text = await read_pdf_text(provider, "/documents/invoice.pdf")
    print(text)
    
    # Create simple PDF
    content = """
    Quote #Q001
    Customer: ACME Corp
    Amount: $1,000.00
    """
    
    await create_pdf(
        provider,
        "/quotes/Q001.pdf",
        content,
        title="Quote Q001"
    )
    
    # Merge PDFs
    await merge_pdfs(
        provider,
        ["/docs/part1.pdf", "/docs/part2.pdf"],
        "/docs/combined.pdf"
    )
    
    # Extract metadata
    metadata = await extract_pdf_metadata(provider, "/docs/invoice.pdf")
    print(f"Title: {metadata['title']}")
    print(f"Pages: {metadata['pages']}")
```

### Word Document Operations (Protocol-Agnostic)

```python
from app.file_access.document_ops import (
    create_word,
    update_word,
    extract_word_text
)

async with provider:
    # Create Word document
    content = {
        "title": "Quote #Q001",
        "sections": [
            {
                "heading": "Customer Information",
                "paragraphs": [
                    "Customer: ACME Corp",
                    "Contact: John Doe",
                    "Email: john@acme.com"
                ]
            },
            {
                "heading": "Quote Items",
                "table": {
                    "headers": ["Item", "Quantity", "Price"],
                    "rows": [
                        ["Product A", "2", "$500.00"],
                        ["Product B", "1", "$300.00"]
                    ]
                }
            }
        ]
    }
    
    await create_word(provider, "/quotes/Q001.docx", content)
    
    # Update placeholders in template
    replacements = {
        "{{CUSTOMER_NAME}}": "ACME Corp",
        "{{QUOTE_NUMBER}}": "Q001",
        "{{AMOUNT}}": "$1,000.00"
    }
    
    await update_word(
        provider,
        "/templates/quote_template.docx",
        replacements
    )
    
    # Extract text
    text = await extract_word_text(provider, "/quotes/Q001.docx")
    print(text)
```

### Health Checks

```python
# Check provider health
result = await provider.health_check()

if result.healthy:
    print("Provider is healthy")
    print(f"Protocol: {result.details['protocol']}")
    print(f"Connection: {result.details['connection']}")
else:
    print(f"Provider unhealthy: {result.message}")
    print(f"Details: {result.details}")
```

---

## Protocol Adapter Development

### Creating a New Protocol Adapter

To add support for a new protocol, follow these steps:

#### 1. Create Adapter File

Create `app/file_access/protocols/<protocol>_protocol.py`:

```python
from typing import Any, Dict, List, Optional, AsyncIterator
from app.file_access.base_fs import (
    FileInfo,
    FileOperationResult,
    HealthCheckResult,
    FileStorageProvider
)

class MyProtocolAdapter(FileStorageProvider):
    """
    My Protocol adapter.
    
    Configuration:
    {
        "protocol": "myprotocol",
        "host": "server.local",
        "username": "user",
        "password": "pass",
        ...
    }
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.host = config["host"]
        # ... initialize other config
        self._connected = False
    
    async def connect(self) -> None:
        """Establish connection."""
        # Implementation
        self._connected = True
    
    async def disconnect(self) -> None:
        """Close connection."""
        # Implementation
        self._connected = False
    
    async def list_files(
        self,
        path: str = "/",
        pattern: Optional[str] = None,
        recursive: bool = False
    ) -> List[FileInfo]:
        """List files in directory."""
        # Implementation
        pass
    
    # Implement all other abstract methods...
```

#### 2. Register Protocol

In `app/file_access/nas_provider.py`, add registration:

```python
def _register_protocols():
    # ... existing registrations ...
    
    try:
        from app.file_access.protocols.myprotocol_protocol import MyProtocolAdapter
        NASProvider.register_protocol("myprotocol", MyProtocolAdapter)
    except ImportError as e:
        logger.debug("myprotocol_unavailable", error=str(e))
```

#### 3. Add Dependencies

In `requirements.txt`:

```
# My Protocol support
myprotocol-lib>=1.0.0
```

#### 4. Create Tests

Create `tests/test_myprotocol.py`:

```python
import pytest
from app.file_access.protocols.myprotocol_protocol import MyProtocolAdapter

class TestMyProtocolAdapter:
    def test_initialization(self):
        config = {"protocol": "myprotocol", "host": "test.local"}
        adapter = MyProtocolAdapter(config)
        assert adapter.host == "test.local"
    
    @pytest.mark.asyncio
    async def test_connection(self):
        # Test connection logic
        pass
```

#### 5. Document Protocol

Add configuration examples and usage to this guide.

### Protocol Adapter Interface

All adapters must implement `FileStorageProvider` interface:

**Required methods:**
- `connect()` - Establish connection
- `disconnect()` - Close connection
- `list_files(path, pattern, recursive)` - List directory contents
- `read_file(path)` - Read file as bytes
- `write_file(path, data, overwrite)` - Write bytes to file
- `delete_file(path)` - Delete file
- `move_file(source, dest, overwrite)` - Move/rename file
- `copy_file(source, dest, overwrite)` - Copy file
- `mkdir(path, parents)` - Create directory
- `rmdir(path, recursive)` - Remove directory
- `file_exists(path)` - Check existence
- `get_file_info(path)` - Get metadata
- `health_check()` - Check connection health

**Optional methods** (have default implementations):
- `stream_read(path, chunk_size)` - Stream file read
- `stream_write(path, data_iterator, overwrite)` - Stream file write

### Error Handling Guidelines

**Standard exceptions to raise:**
- `FileNotFoundError`: File/directory doesn't exist
- `FileExistsError`: File exists and overwrite=False
- `NotADirectoryError`: Path is not a directory
- `IsADirectoryError`: Path is a directory, expected file
- `PermissionError`: No permission for operation
- `ConnectionError`: Connection failed or lost

**Return FileOperationResult for operations:**
```python
return FileOperationResult(
    success=True,
    path=path,
    message="Operation successful"
)

# Or on error:
return FileOperationResult(
    success=False,
    path=path,
    error="Detailed error message"
)
```

---

## Document Operations

Document operations are protocol-agnostic - they work with any `FileStorageProvider` implementation.

### Excel Operations

**Available functions:**
- `read_excel(provider, path, sheet_name, read_only)` - Read workbook
- `write_excel(provider, path, workbook, overwrite)` - Write workbook
- `update_excel(provider, path, updates, sheet_name)` - Update cells
- `create_excel_from_data(provider, path, data, sheet_name, headers, overwrite)` - Create from data
- `read_excel_as_dict(provider, path, sheet_name, header_row)` - Read as dictionaries
- `append_excel_row(provider, path, row_data, sheet_name)` - Append row

### PDF Operations

**Available functions:**
- `read_pdf_text(provider, path)` - Extract text
- `extract_pdf_metadata(provider, path)` - Get metadata
- `merge_pdfs(provider, source_paths, dest_path, overwrite)` - Merge PDFs
- `create_pdf(provider, path, content, overwrite, page_size, title)` - Create simple PDF
- `split_pdf(provider, source_path, output_dir, page_ranges)` - Split PDF

### Word Operations

**Available functions:**
- `read_word(provider, path)` - Read document
- `write_word(provider, path, document, overwrite)` - Write document
- `create_word(provider, path, content, overwrite)` - Create from structure
- `update_word(provider, path, replacements)` - Replace placeholders
- `extract_word_text(provider, path)` - Extract text
- `add_word_paragraph(provider, path, text, style)` - Append paragraph
- `add_word_table(provider, path, headers, rows)` - Append table

---

## Migration Guide

### From LocalFS to NAS Provider

#### 1. Update Tenant Configuration

**Before:**
```json
{
  "file_provider": "localfs",
  "file_config": {
    "base_path": "/mnt/storage/tenant_acme"
  }
}
```

**After:**
```json
{
  "file_provider": "nas",
  "file_config": {
    "protocol": "smb",
    "host": "nas.company.local",
    "share": "storage",
    "username": "edilcos_app",
    "password": "secure_password",
    "base_path": "/tenant_acme"
  }
}
```

#### 2. No Code Changes Required

The abstraction layer ensures code continues working:

```python
# This code works with both LocalFS and NAS providers
provider = get_file_provider(tenant)
async with provider:
    await provider.write_file("/quotes/Q001.xlsx", data)
```

#### 3. Test Migration

1. Test with new config in development
2. Verify file operations work
3. Check health endpoints
4. Monitor logs for errors
5. Update production tenant configs

### From OneDrive to NAS Provider

Similar process - update `file_provider` to `"nas"` and configure protocol.

---

## Troubleshooting

### Common Issues

#### SMB Connection Failed

**Symptoms:**
```
ConnectionError: SMB connection failed: [Errno 111] Connection refused
```

**Solutions:**
1. Check host reachability: `ping nas.company.local`
2. Verify SMB port is open: `telnet nas.company.local 445`
3. Confirm credentials are correct
4. Check domain/workgroup matches server
5. Verify share name exists on server
6. Check firewall rules

#### Permission Denied

**Symptoms:**
```
PermissionError: Access denied to /path/file.txt
```

**Solutions:**
1. Verify user has read/write permissions on share
2. Check base_path exists and is accessible
3. Ensure correct username/password
4. Verify domain authentication if applicable

#### File Not Found

**Symptoms:**
```
FileNotFoundError: File not found: /quotes/Q001.xlsx
```

**Solutions:**
1. Verify base_path is correct
2. Check path separators (forward slashes)
3. Confirm file exists on NAS
4. Check case sensitivity of filenames

#### Protocol Not Supported

**Symptoms:**
```
ValueError: Unsupported protocol: nfs. Supported protocols: smb
```

**Solutions:**
1. Check protocol is implemented (currently only SMB)
2. Verify protocol name spelling in config
3. Install required dependencies
4. Register protocol if custom implementation

### Debug Logging

Enable debug logging to troubleshoot:

```python
import structlog

logger = structlog.get_logger()
logger.setLevel("DEBUG")

# Detailed logs will show:
# - Connection attempts
# - File operations
# - Protocol-specific details
# - Error stack traces
```

### Health Check Diagnostics

Use health checks to diagnose issues:

```python
result = await provider.health_check()

print(f"Healthy: {result.healthy}")
print(f"Message: {result.message}")
print(f"Details: {result.details}")

# Check specific aspects:
if "connection" in result.details:
    print(f"Connection: {result.details['connection']}")
if "share_access" in result.details:
    print(f"Share Access: {result.details['share_access']}")
```

---

## Performance Considerations

### Connection Pooling

For high-traffic scenarios, consider connection pooling:

```python
class ProviderPool:
    def __init__(self, tenant, pool_size=5):
        self.tenant = tenant
        self.pool = [get_file_provider(tenant) for _ in range(pool_size)]
        self.available = asyncio.Queue()
        for provider in self.pool:
            self.available.put_nowait(provider)
    
    async def acquire(self):
        provider = await self.available.get()
        if not provider._connected:
            await provider.connect()
        return provider
    
    async def release(self, provider):
        await self.available.put(provider)
```

### Streaming Large Files

Use streaming methods for large files:

```python
# Stream read
async for chunk in provider.stream_read("/large_file.bin", chunk_size=8192):
    process_chunk(chunk)

# Stream write
async def data_generator():
    # Generate data in chunks
    for i in range(1000):
        yield generate_chunk(i)

await provider.stream_write("/output.bin", data_generator())
```

### Caching

Cache file metadata to reduce network calls:

```python
from functools import lru_cache

@lru_cache(maxsize=100)
async def get_cached_file_info(provider, path):
    return await provider.get_file_info(path)
```

### Batch Operations

Group operations when possible:

```python
# Instead of:
for file in files:
    await provider.delete_file(file)

# Use list comprehension with gather:
await asyncio.gather(*[
    provider.delete_file(file) for file in files
])
```

---

## Security Best Practices

### 1. Credential Management

**DO:**
- Store credentials in environment variables or secrets manager
- Use encrypted connections (SMB over TLS, SFTP, FTPS, WebDAV HTTPS)
- Rotate credentials regularly
- Use least-privilege access

**DON'T:**
- Hardcode credentials in code
- Store plaintext credentials in database
- Use same credentials for all tenants
- Share credentials across environments

### 2. Access Control

```python
# Implement tenant isolation
def validate_tenant_access(tenant_id: str, requested_path: str):
    """Ensure tenant can only access their files."""
    base_path = f"/tenants/{tenant_id}"
    normalized_path = os.path.normpath(requested_path)
    
    if not normalized_path.startswith(base_path):
        raise PermissionError("Access denied: path outside tenant scope")
```

### 3. Input Validation

```python
def validate_filename(filename: str):
    """Prevent directory traversal attacks."""
    if ".." in filename or filename.startswith("/"):
        raise ValueError("Invalid filename")
    
    # Check for null bytes
    if "\x00" in filename:
        raise ValueError("Invalid filename: null byte")
```

### 4. Audit Logging

Log all file operations:

```python
logger.info(
    "file_operation",
    operation="write",
    tenant_id=tenant_id,
    path=path,
    size=len(data),
    user_id=user_id,
    timestamp=datetime.utcnow().isoformat()
)
```

---

## Conclusion

The NAS Provider system provides a flexible, protocol-agnostic way to work with network storage. Key takeaways:

1. **Unified interface**: All protocols use same API
2. **Easy to extend**: Add new protocols without changing business logic
3. **Well-tested**: Comprehensive test suite
4. **Production-ready**: Error handling, logging, monitoring
5. **Documented**: Clear examples and guidelines

For questions or issues, check troubleshooting section or create a GitHub issue.
