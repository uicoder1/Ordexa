from typing import Dict, Type
from app.services.marketplace_adapters.base_adapter import BaseMarketplaceAdapter
from app.services.marketplace_adapters.flipkart_adapter import FlipkartAdapter

class MarketplaceAdapterFactory:

    _adapters: Dict[str, BaseMarketplaceAdapter] = {
        "flipkart": FlipkartAdapter(),
        "amazon": FlipkartAdapter(),    # Generic fallback
        "meesho": FlipkartAdapter(),    # Generic fallback
        "shopify": FlipkartAdapter(),   # Generic fallback
        "custom": FlipkartAdapter()     # Generic fallback
    }

    @classmethod
    def get_adapter(cls, marketplace_name: str) -> BaseMarketplaceAdapter:
        key = (marketplace_name or "flipkart").strip().lower()
        return cls._adapters.get(key, cls._adapters["flipkart"])
