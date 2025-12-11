# tests/test_file_access.py
"""
Tests for File Access Abstraction Layer (FAAL).
"""
import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from app.file_access.localfs_provider import LocalFSProvider
from app.file_access.onedrive_provider import OneDriveProvider
from app.file_access.registry import (
    get_file_provider,
    get_provider_by_name,
    register_provider,
    list_providers
)
from app.db.models import Tenant, Quote


class TestLocalFSProvider:
    """Tests for LocalFSProvider."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def provider(self, temp_dir):
        """Create LocalFSProvider instance."""
        config = {
            "base_path": str(temp_dir),
            "excel_filename": "test_preventivi.xlsx",
            "lock_timeout": 5,
            "create_dirs": True
        }
        return LocalFSProvider(config)
    
    @pytest.mark.asyncio
    async def test_health_check(self, provider):
        """Test health check succeeds."""
        result = await provider.health_check()
        assert result["healthy"] is True
        assert result["provider"] == "localfs"
        assert result["details"]["checks"]["base_path_exists"] is True
        assert result["details"]["checks"]["base_path_readable"] is True
        assert result["details"]["checks"]["base_path_writable"] is True
    
    @pytest.mark.asyncio
    async def test_write_and_read_file(self, provider):
        """Test writing and reading a file."""
        test_data = b"Hello, FAAL!"
        path = "test_file.txt"
        
        # Write
        result = await provider.write_file(path, test_data)
        assert result.success is True
        assert result.file_size == len(test_data)
        
        # Read
        data = await provider.read_file(path)
        assert data == test_data
    
    @pytest.mark.asyncio
    async def test_file_exists(self, provider):
        """Test file_exists check."""
        path = "test.txt"
        
        # Initially doesn't exist
        exists = await provider.file_exists(path)
        assert exists is False
        
        # After writing, exists
        await provider.write_file(path, b"test")
        exists = await provider.file_exists(path)
        assert exists is True
    
    @pytest.mark.asyncio
    async def test_get_metadata(self, provider):
        """Test getting file metadata."""
        path = "metadata_test.txt"
        data = b"test metadata"
        
        await provider.write_file(path, data)
        
        metadata = await provider.get_metadata(path)
        assert metadata.path == path
        assert metadata.size == len(data)
        assert metadata.exists is True
        assert metadata.is_directory is False
    
    @pytest.mark.asyncio
    async def test_create_directory(self, provider):
        """Test creating directories."""
        dir_path = "subdir/nested"
        
        result = await provider.create_directory(dir_path)
        assert result.success is True
        
        # Verify it exists
        exists = await provider.file_exists(dir_path)
        assert exists is True
    
    @pytest.mark.asyncio
    async def test_list_files(self, provider, temp_dir):
        """Test listing files in directory."""
        # Create some files
        await provider.write_file("file1.txt", b"data1")
        await provider.write_file("file2.txt", b"data2")
        await provider.create_directory("subdir")
        
        # List files
        files = await provider.list_files("")
        assert len(files) >= 2
        
        file_names = [f.path for f in files]
        assert "file1.txt" in file_names
        assert "file2.txt" in file_names
    
    @pytest.mark.asyncio
    async def test_delete_file(self, provider):
        """Test deleting a file."""
        path = "delete_me.txt"
        
        # Create file
        await provider.write_file(path, b"delete this")
        assert await provider.file_exists(path) is True
        
        # Delete file
        result = await provider.delete_file(path)
        assert result.success is True
        
        # Verify deleted
        assert await provider.file_exists(path) is False
    
    @pytest.mark.asyncio
    async def test_update_quote_excel(self, provider, temp_dir):
        """Test Excel update with quote data."""
        # Create mock quote and customer
        class MockQuote:
            id = "test-quote-123"
            created_at = datetime.utcnow()
            total = 1500.50
            status = "pending"
            notes = "Test quote"
            tenant_id = "test-tenant"
            flow_id = "preventivi_v1"
        
        quote = MockQuote()
        customer = {
            "name": "Mario Rossi",
            "email": "mario@example.com",
            "phone": "+39123456789"
        }
        
        # Update Excel (should create new file)
        result = await provider.update_quote_excel("test-tenant", quote, customer)
        assert result.success is True
        assert "created" in result.message or "updated" in result.message
        
        # Verify Excel file was created
        excel_path = temp_dir / "test_preventivi.xlsx"
        assert excel_path.exists()
        
        # Update again (should update existing row)
        quote.status = "accepted"
        result2 = await provider.update_quote_excel("test-tenant", quote, customer)
        assert result2.success is True
    
    @pytest.mark.asyncio
    async def test_path_security(self, provider):
        """Test that paths outside base_path are rejected."""
        with pytest.raises(PermissionError):
            await provider.read_file("../../etc/passwd")


class TestOneDriveProvider:
    """Tests for OneDriveProvider."""
    
    @pytest.fixture
    def provider(self):
        """Create OneDriveProvider instance with mock config."""
        config = {
            "tenant_id": "test-tenant-id",
            "client_id": "test-client-id",
            "client_secret": "test-secret",
            "drive_id": "test-drive-id",
            "excel_file_id": "test-excel-id"
        }
        return OneDriveProvider(config)
    
    def test_unsupported_operations(self, provider):
        """Test that unsupported operations raise NotImplementedError."""
        with pytest.raises(NotImplementedError):
            pytest.mark.asyncio(provider.read_file("test.txt"))
        
        with pytest.raises(NotImplementedError):
            pytest.mark.asyncio(provider.write_file("test.txt", b"data"))
        
        with pytest.raises(NotImplementedError):
            pytest.mark.asyncio(provider.file_exists("test.txt"))


class TestProviderRegistry:
    """Tests for provider registry."""
    
    def test_list_providers(self):
        """Test listing available providers."""
        providers = list_providers()
        assert "localfs" in providers
        assert "onedrive" in providers
    
    def test_get_provider_by_name_localfs(self):
        """Test getting LocalFS provider by name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"base_path": tmpdir}
            provider = get_provider_by_name("localfs", config)
            assert isinstance(provider, LocalFSProvider)
    
    def test_get_provider_by_name_onedrive(self):
        """Test getting OneDrive provider by name."""
        config = {
            "tenant_id": "test",
            "client_id": "test",
            "client_secret": "test",
            "drive_id": "test",
            "excel_file_id": "test"
        }
        provider = get_provider_by_name("onedrive", config)
        assert isinstance(provider, OneDriveProvider)
    
    def test_get_provider_unknown(self):
        """Test getting unknown provider raises error."""
        with pytest.raises(ValueError, match="Unknown file storage provider"):
            get_provider_by_name("unknown_provider", {})
    
    @pytest.mark.asyncio
    async def test_get_file_provider_from_tenant(self):
        """Test getting provider from tenant object."""
        # Create mock tenant
        tenant = Tenant()
        tenant.id = "test-tenant-id"
        tenant.name = "Test Tenant"
        tenant.file_provider = "localfs"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tenant.file_config = {"base_path": tmpdir}
            
            provider = get_file_provider(tenant)
            assert isinstance(provider, LocalFSProvider)
    
    def test_get_file_provider_no_config(self):
        """Test error when tenant has no file_provider."""
        tenant = Tenant()
        tenant.id = "test-tenant-id"
        tenant.file_provider = None
        
        with pytest.raises(ValueError, match="has no file_provider configured"):
            get_file_provider(tenant)
    
    def test_register_custom_provider(self):
        """Test registering a custom provider."""
        from app.file_access.base import FileStorageProvider
        
        class CustomProvider(FileStorageProvider):
            async def update_quote_excel(self, *args, **kwargs):
                pass
            async def read_file(self, path: str) -> bytes:
                return b""
            async def write_file(self, path: str, data: bytes):
                pass
            async def file_exists(self, path: str) -> bool:
                return False
            async def get_metadata(self, path: str):
                pass
            async def list_files(self, directory: str):
                return []
            async def delete_file(self, path: str):
                pass
            async def create_directory(self, path: str):
                pass
            async def health_check(self):
                return {"healthy": True, "provider": "custom"}
        
        register_provider("custom", CustomProvider)
        assert "custom" in list_providers()
        
        provider = get_provider_by_name("custom", {})
        assert isinstance(provider, CustomProvider)


class TestE2EFileAccess:
    """End-to-end tests for file access layer."""
    
    @pytest.mark.asyncio
    async def test_full_quote_workflow_localfs(self):
        """Test complete quote workflow with LocalFS provider."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup provider
            provider = LocalFSProvider({
                "base_path": tmpdir,
                "excel_filename": "preventivi.xlsx"
            })
            
            # Create mock quote
            class MockQuote:
                id = "quote-001"
                created_at = datetime.utcnow()
                total = 2500.00
                status = "pending"
                notes = "New construction project"
                tenant_id = "edilcos-test"
                flow_id = "preventivi_v1"
            
            customer = {
                "name": "Giuseppe Verdi",
                "email": "giuseppe@example.com",
                "phone": "+39987654321"
            }
            
            # First update (create)
            result1 = await provider.update_quote_excel("edilcos-test", MockQuote(), customer)
            assert result1.success is True
            
            # Verify file exists
            excel_path = Path(tmpdir) / "preventivi.xlsx"
            assert excel_path.exists()
            
            # Second update (modify)
            MockQuote.status = "accepted"
            MockQuote.total = 2750.00
            result2 = await provider.update_quote_excel("edilcos-test", MockQuote(), customer)
            assert result2.success is True
            
            # Health check
            health = await provider.health_check()
            assert health["healthy"] is True
