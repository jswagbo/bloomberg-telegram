"""External API integrations"""

from app.services.external_apis.price_service import PriceService, price_service
from app.services.external_apis.dexscreener import DexScreenerClient
from app.services.external_apis.jupiter import JupiterClient
from app.services.external_apis.coingecko import CoinGeckoClient

__all__ = [
    "PriceService",
    "price_service",
    "DexScreenerClient",
    "JupiterClient",
    "CoinGeckoClient",
]

# Alias for backwards compatibility
ExternalAPIService = PriceService
