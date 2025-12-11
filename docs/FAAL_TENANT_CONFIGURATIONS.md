# Example Tenant Configurations for FAAL

## Example 1: LocalFS with NAS (Synology)

```sql
-- Tenant using Synology NAS mounted via NFS
UPDATE tenants 
SET file_provider = 'localfs',
    file_config = '{
      "base_path": "/mnt/synology_nas/edilcos/preventivi",
      "excel_filename": "preventivi_2025.xlsx",
      "lock_timeout": 30,
      "create_dirs": true
    }'::json
WHERE name = 'Edilcos Milano';
```

**Mount command:**
```bash
sudo mount -t nfs 192.168.1.100:/volume1/edilcos /mnt/synology_nas
```

---

## Example 2: LocalFS with QNAP NAS

```sql
-- Tenant using QNAP NAS mounted via CIFS
UPDATE tenants 
SET file_provider = 'localfs',
    file_config = '{
      "base_path": "/mnt/qnap_nas/edilcos_data",
      "excel_filename": "quotes.xlsx",
      "lock_timeout": 45,
      "create_dirs": true
    }'::json
WHERE name = 'Edilcos Roma';
```

**Mount command:**
```bash
sudo mount -t cifs //192.168.1.200/edilcos /mnt/qnap_nas \
  -o username=edilcos,password=yourpass,vers=3.0
```

---

## Example 3: LocalFS with Local SSD

```sql
-- Tenant using local fast SSD storage
UPDATE tenants 
SET file_provider = 'localfs',
    file_config = '{
      "base_path": "/var/lib/edilcos/storage",
      "excel_filename": "preventivi.xlsx",
      "lock_timeout": 10,
      "create_dirs": true
    }'::json
WHERE name = 'Edilcos Test';
```

**Setup:**
```bash
sudo mkdir -p /var/lib/edilcos/storage
sudo chown edilcos:edilcos /var/lib/edilcos/storage
sudo chmod 755 /var/lib/edilcos/storage
```

---

## Example 4: OneDrive (Business)

```sql
-- Tenant using Microsoft OneDrive for Business
UPDATE tenants 
SET file_provider = 'onedrive',
    file_config = '{
      "tenant_id": "12345678-1234-1234-1234-123456789abc",
      "client_id": "87654321-4321-4321-4321-cba987654321",
      "client_secret": "your~secret~key~here",
      "drive_id": "b!abcdefgh1234567890",
      "excel_file_id": "01ABCDEF1234567890ABCDEF"
    }'::json
WHERE name = 'Edilcos Cloud';
```

**Azure AD Setup:**
1. Go to https://portal.azure.com
2. Azure Active Directory → App registrations → New registration
3. API permissions → Microsoft Graph → Application permissions → Files.ReadWrite.All
4. Certificates & secrets → New client secret
5. Copy tenant_id, client_id, client_secret

**Get drive_id and excel_file_id:**
```bash
# Get drive ID
curl -H "Authorization: Bearer $TOKEN" \
  https://graph.microsoft.com/v1.0/drives

# Get file ID
curl -H "Authorization: Bearer $TOKEN" \
  https://graph.microsoft.com/v1.0/drives/{drive-id}/root:/path/to/preventivi.xlsx
```

---

## Example 5: Multi-Tenant Setup

```sql
-- Main production tenant with NAS
UPDATE tenants 
SET file_provider = 'localfs',
    file_config = '{
      "base_path": "/mnt/prod_nas/edilcos",
      "excel_filename": "preventivi_prod.xlsx",
      "lock_timeout": 30,
      "create_dirs": true
    }'::json
WHERE name = 'Edilcos Production';

-- Staging tenant with local storage
UPDATE tenants 
SET file_provider = 'localfs',
    file_config = '{
      "base_path": "/var/lib/edilcos/staging",
      "excel_filename": "preventivi_staging.xlsx",
      "lock_timeout": 10,
      "create_dirs": true
    }'::json
WHERE name = 'Edilcos Staging';

-- Cloud tenant with OneDrive
UPDATE tenants 
SET file_provider = 'onedrive',
    file_config = '{
      "tenant_id": "cloud-tenant-id",
      "client_id": "cloud-client-id",
      "client_secret": "cloud-secret",
      "drive_id": "cloud-drive-id",
      "excel_file_id": "cloud-file-id"
    }'::json
WHERE name = 'Edilcos Cloud Backup';
```

---

## Example 6: Development/Testing

```sql
-- Dev tenant using temporary local storage
UPDATE tenants 
SET file_provider = 'localfs',
    file_config = '{
      "base_path": "/tmp/edilcos_dev",
      "excel_filename": "preventivi_dev.xlsx",
      "lock_timeout": 5,
      "create_dirs": true
    }'::json
WHERE name = 'Edilcos Dev';
```

---

## Example 7: Disabled File Provider

```sql
-- Tenant without file storage (for testing)
UPDATE tenants 
SET file_provider = NULL,
    file_config = NULL
WHERE name = 'Edilcos No Storage';
```

**Note:** When `file_provider` is NULL, Excel updates are skipped with a warning log.

---

## Configuration Best Practices

### Security
- Never commit credentials to git
- Use environment variables for secrets
- Rotate OneDrive client secrets regularly
- Restrict NAS access by IP/user

### Performance
- Use SSD for LocalFS when possible
- Mount NAS with appropriate options: `async,noatime`
- Set reasonable lock_timeout (30s typical)
- Monitor disk space

### Reliability
- Enable `create_dirs: true` for auto-setup
- Use absolute paths for `base_path`
- Test health checks regularly
- Set up monitoring/alerts

### Backup
- Backup NAS data regularly
- Use OneDrive for cloud redundancy
- Keep versioned Excel files
- Test restore procedures

---

## Testing Configuration

### Test LocalFS Provider

```python
from app.file_access.localfs_provider import LocalFSProvider

provider = LocalFSProvider({
    "base_path": "/tmp/faal_test",
    "excel_filename": "test.xlsx"
})

# Health check
health = await provider.health_check()
print(health)
```

### Test OneDrive Provider

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

### Test via API

```bash
# Update tenant config
curl -X POST http://localhost:8000/admin/tenants/123/config \
  -H "Content-Type: application/json" \
  -d '{
    "file_provider": "localfs",
    "file_config": {
      "base_path": "/mnt/nas",
      "excel_filename": "test.xlsx"
    }
  }'

# Check health
curl http://localhost:8000/admin/health/deep | jq '.file_providers'
```

---

## Common Scenarios

### Scenario 1: Migrate from Cloud to NAS

```sql
-- Step 1: Keep both active during migration
UPDATE tenants SET file_provider = 'localfs' WHERE name = 'Tenant';

-- Step 2: Copy Excel files from OneDrive to NAS

-- Step 3: Verify LocalFS health check passes

-- Step 4: Remove OneDrive config if no longer needed
```

### Scenario 2: Add Backup Provider

```sql
-- Primary: Local NAS
UPDATE tenants 
SET file_provider = 'localfs',
    file_config = '{"base_path": "/mnt/primary_nas"}'::json
WHERE name = 'Production';

-- Backup: OneDrive (via separate scheduled job)
-- Keep both configs in separate tenants or use custom sync job
```

### Scenario 3: Per-Customer Storage

```sql
-- Different storage per customer segment
UPDATE tenants 
SET file_provider = 'localfs',
    file_config = '{"base_path": "/mnt/nas/customer_a"}'::json
WHERE name = 'Customer A';

UPDATE tenants 
SET file_provider = 'localfs',
    file_config = '{"base_path": "/mnt/nas/customer_b"}'::json
WHERE name = 'Customer B';
```

---

## Monitoring

### Health Check Query

```sql
-- Get all tenant provider configs
SELECT 
    name,
    file_provider,
    file_config->>'base_path' as base_path,
    status
FROM tenants
WHERE file_provider IS NOT NULL
ORDER BY name;
```

### Check Recent Excel Updates

```sql
-- Check audit logs for file provider activity
SELECT 
    created_at,
    tenant_id,
    event_type,
    context->>'provider' as provider,
    context->>'success' as success
FROM audit_logs
WHERE event_type LIKE '%file_provider%'
ORDER BY created_at DESC
LIMIT 20;
```

---

## Troubleshooting Common Issues

### Issue: "base_path doesn't exist"
```bash
sudo mkdir -p /mnt/edilcos_nas
sudo chown edilcos:edilcos /mnt/edilcos_nas
```

### Issue: "Permission denied"
```bash
sudo chmod 755 /mnt/edilcos_nas
sudo chown edilcos:edilcos /mnt/edilcos_nas/*
```

### Issue: "Lock timeout"
```bash
# Remove stale lock
rm /path/to/preventivi.xlsx.lock

# Or increase timeout in config
"lock_timeout": 60
```

### Issue: "OneDrive token error"
- Regenerate client secret in Azure AD
- Update file_config with new secret
- Verify Graph API permissions

---

## Complete Setup Checklist

- [ ] Database migration applied
- [ ] Tenant file_provider configured
- [ ] Tenant file_config populated
- [ ] NAS mounted (if using LocalFS)
- [ ] Directory permissions verified
- [ ] Health check passes
- [ ] Test Excel update works
- [ ] Monitoring/alerts configured
- [ ] Backup strategy in place
- [ ] Documentation updated

---

**Last Updated:** 11 December 2025  
**Version:** 1.0
