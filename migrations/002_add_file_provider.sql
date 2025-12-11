"""
Database migration: Add file_provider fields to Tenant table

Revision ID: 002_add_file_provider
Revises: 001_initial
Create Date: 2025-12-11

"""

# Migration for adding file_provider and file_config to tenants table

-- SQLAlchemy Migration (for reference)
ALTER TABLE tenants ADD COLUMN file_provider VARCHAR;
ALTER TABLE tenants ADD COLUMN file_config JSON;

-- Example tenant configurations:

-- LocalFS provider (for NAS or local storage)
UPDATE tenants 
SET file_provider = 'localfs',
    file_config = '{
      "base_path": "/mnt/edilcos_nas/preventivi",
      "excel_filename": "preventivi.xlsx",
      "lock_timeout": 30,
      "create_dirs": true
    }'::json
WHERE name = 'Edilcos Main';

-- OneDrive provider
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

-- Notes:
-- 1. file_provider values: "localfs", "onedrive", "gdrive", "s3", etc.
-- 2. file_config is provider-specific JSON configuration
-- 3. Both fields are nullable (optional) for backward compatibility
