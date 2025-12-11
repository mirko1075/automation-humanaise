# FAAL Quick Reference Guide

## Installation

```bash
pip install -r requirements.txt
```

## Database Migration

```bash
psql -U edilcos -d edilcos_db -f migrations/002_add_file_provider.sql
```

## Configuration Examples

### LocalFS (NAS/Local Storage)

```sql
UPDATE tenants 
SET file_provider = 'localfs',
    file_config = '{
      "base_path": "/mnt/edilcos_nas/preventivi",
      "excel_filename": "preventivi.xlsx",
      "lock_timeout": 30,
      "create_dirs": true
    }'::json
WHERE name = 'Your Tenant';
```

### OneDrive

```sql
UPDATE tenants 
SET file_provider = 'onedrive',
    file_config = '{
      "tenant_id": "azure-tenant-id",
      "client_id": "app-client-id",
      "client_secret": "app-secret",
      "drive_id": "drive-id",
      "excel_file_id": "excel-file-id"
    }'::json
WHERE name = 'Your Tenant';
```

## Usage in Code

```python
from app.file_access.registry import get_file_provider

# Get provider for tenant
tenant = await tenant_repo.get_by_id(tenant_id)
provider = get_file_provider(tenant)

# Update Excel
customer_dict = {
    "name": customer.name,
    "email": customer.email,
    "phone": customer.phone
}
result = await provider.update_quote_excel(tenant_id, quote, customer_dict)

if result.success:
    print(f"Success: {result.message}")
else:
    print(f"Failed: {result.message}")
```

## Health Check

```bash
curl http://localhost:8000/admin/health/deep | jq '.file_providers'
```

## Common Commands

### Mount NAS (NFS)
```bash
sudo mount -t nfs nas.local:/volume1/edilcos /mnt/edilcos_nas
```

### Mount NAS (CIFS/SMB)
```bash
sudo mount -t cifs //nas.local/edilcos /mnt/edilcos_nas -o username=user,password=pass
```

### Check Permissions
```bash
ls -la /mnt/edilcos_nas
sudo chown edilcos:edilcos /mnt/edilcos_nas
sudo chmod 755 /mnt/edilcos_nas
```

### Run Tests
```bash
pytest tests/test_file_access.py -v
```

## Troubleshooting

### LocalFS: Permission Denied
```bash
sudo chown edilcos:edilcos /mnt/edilcos_nas
sudo chmod 755 /mnt/edilcos_nas
```

### LocalFS: Lock Timeout
```bash
# Remove stale lock file
rm /mnt/edilcos_nas/preventivi.xlsx.lock
```

### OneDrive: Token Error
- Verify Azure AD credentials in file_config
- Check tenant_id, client_id, client_secret
- Verify Graph API permissions

## Adding New Provider

1. Create `app/file_access/new_provider.py`
2. Implement `FileStorageProvider` interface
3. Register in `app/file_access/registry.py`
4. Add tests in `tests/test_file_access.py`
5. Update documentation

## Provider Support Matrix

| Operation | LocalFS | OneDrive | Future |
|-----------|---------|----------|--------|
| update_quote_excel | ✅ Sync | ✅ Async | - |
| read_file | ✅ | ❌ | - |
| write_file | ✅ | ❌ | - |
| file_exists | ✅ | ❌ | - |
| get_metadata | ✅ | ❌ | - |
| list_files | ✅ | ❌ | - |
| delete_file | ✅ | ❌ | - |
| create_directory | ✅ | ❌ | - |
| health_check | ✅ | ✅ | - |

✅ = Implemented  
❌ = Not implemented (can be added)  
- = Planned

## Documentation

Full docs: `docs/FILE_ACCESS_ABSTRACTION_LAYER.md`
