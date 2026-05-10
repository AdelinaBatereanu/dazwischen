"""Static catalog version metadata provider."""

from app.models.catalog import CatalogMetadata


class CatalogVersionProvider:
    """Provides version metadata for the public catalog snapshot."""

    def get_metadata(self) -> CatalogMetadata:
        """Return the static metadata for the current catalog."""
        return CatalogMetadata(
            proxy_version="1.0.0",
            catalog_version="2026-05-02.1",
            public_endpoint_version="v1",
            internal_contract_version="1.0",
        )
