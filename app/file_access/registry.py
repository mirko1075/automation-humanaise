# app/file_access/registry.py
"""
Provider registry for FAAL.

Factory function to instantiate the correct file storage provider
based on tenant configuration.
"""
from typing import Dict, Any, Optional
from app.file_access.base import FileStorageProvider
from app.file_access.localfs_provider import LocalFSProvider
from app.file_access.onedrive_provider import OneDriveProvider
from app.file_access.nas_provider import NASProvider
from app.monitoring.logger import log


# Registry of available providers
PROVIDER_REGISTRY: Dict[str, type] = {
    "localfs": LocalFSProvider,
    "onedrive": OneDriveProvider,
    "nas": NASProvider,
    # Future providers:
    # "gdrive": GoogleDriveProvider,
    # "s3": S3Provider,
    # "azure_blob": AzureBlobProvider,
}


def register_provider(name: str, provider_class: type) -> None:
    """
    Register a new file storage provider.
    
    This allows custom providers to be added at runtime.
    
    Args:
        name: Provider identifier (e.g., "custom_nas")
        provider_class: Class implementing FileStorageProvider
        
    Raises:
        ValueError: If provider_class doesn't implement FileStorageProvider
    """
    if not issubclass(provider_class, FileStorageProvider):
        raise ValueError(
            f"Provider class must inherit from FileStorageProvider, "
            f"got {provider_class}"
        )
    
    PROVIDER_REGISTRY[name] = provider_class
    log("INFO", f"Registered file storage provider: {name}", module="registry")


def get_file_provider(tenant: Any) -> FileStorageProvider:
    """
    Get file storage provider for tenant.
    
    Factory function that instantiates the correct provider based on
    tenant.file_provider and tenant.file_config.
    
    Args:
        tenant: Tenant model instance with file_provider and file_config fields
        
    Returns:
        Initialized FileStorageProvider instance
        
    Raises:
        ValueError: If provider is unknown or configuration is invalid
        
    Example:
        tenant = await get_tenant(tenant_id)
        provider = get_file_provider(tenant)
        result = await provider.update_quote_excel(tenant_id, quote, customer)
    """
    provider_name = getattr(tenant, "file_provider", None)
    file_config = getattr(tenant, "file_config", None)
    
    # Validation
    if not provider_name:
        raise ValueError(
            f"Tenant {tenant.id} has no file_provider configured. "
            f"Set tenant.file_provider to one of: {list(PROVIDER_REGISTRY.keys())}"
        )
    
    if not file_config:
        raise ValueError(
            f"Tenant {tenant.id} has no file_config. "
            f"Set tenant.file_config with provider-specific configuration."
        )
    
    # Normalize provider name
    provider_name = provider_name.lower().strip()
    
    # Get provider class from registry
    provider_class = PROVIDER_REGISTRY.get(provider_name)
    
    if not provider_class:
        raise ValueError(
            f"Unknown file storage provider: '{provider_name}'. "
            f"Available providers: {list(PROVIDER_REGISTRY.keys())}"
        )
    
    # Instantiate provider with config
    try:
        provider = provider_class(file_config)
        log("INFO", f"Initialized {provider_name} provider for tenant {tenant.id}", 
            module="registry", tenant_id=str(tenant.id))
        return provider
    
    except Exception as exc:
        raise ValueError(
            f"Failed to initialize {provider_name} provider for tenant {tenant.id}: {exc}"
        ) from exc


def get_provider_by_name(
    provider_name: str, 
    config: Dict[str, Any]
) -> FileStorageProvider:
    """
    Get file storage provider by name and config.
    
    Lower-level factory function when tenant object is not available.
    
    Args:
        provider_name: Provider identifier (e.g., "localfs", "onedrive")
        config: Provider-specific configuration dict
        
    Returns:
        Initialized FileStorageProvider instance
        
    Raises:
        ValueError: If provider is unknown or configuration is invalid
    """
    provider_name = provider_name.lower().strip()
    
    provider_class = PROVIDER_REGISTRY.get(provider_name)
    
    if not provider_class:
        raise ValueError(
            f"Unknown file storage provider: '{provider_name}'. "
            f"Available providers: {list(PROVIDER_REGISTRY.keys())}"
        )
    
    try:
        return provider_class(config)
    except Exception as exc:
        raise ValueError(
            f"Failed to initialize {provider_name} provider: {exc}"
        ) from exc


def list_providers() -> list[str]:
    """
    List all registered provider names.
    
    Returns:
        List of provider identifiers
    """
    return list(PROVIDER_REGISTRY.keys())


def get_provider_info(provider_name: str) -> Dict[str, Any]:
    """
    Get information about a provider.
    
    Args:
        provider_name: Provider identifier
        
    Returns:
        Dict with provider information
        
    Raises:
        ValueError: If provider is unknown
    """
    provider_name = provider_name.lower().strip()
    
    provider_class = PROVIDER_REGISTRY.get(provider_name)
    
    if not provider_class:
        raise ValueError(
            f"Unknown file storage provider: '{provider_name}'. "
            f"Available providers: {list(PROVIDER_REGISTRY.keys())}"
        )
    
    return {
        "name": provider_name,
        "class": provider_class.__name__,
        "module": provider_class.__module__,
        "docstring": provider_class.__doc__,
    }
