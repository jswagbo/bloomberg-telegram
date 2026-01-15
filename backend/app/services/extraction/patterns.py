"""Pattern matching for entity extraction"""

import re
from typing import List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TokenMatch:
    """Extracted token match"""
    symbol: Optional[str]
    address: Optional[str]
    chain: str
    confidence: float
    match_type: str  # symbol, address, pump_link


@dataclass
class WalletMatch:
    """Extracted wallet match"""
    address: str
    chain: str
    label: Optional[str] = None


@dataclass
class PriceMatch:
    """Extracted price match"""
    value: float
    unit: str  # USD, SOL, ETH, BNB, x


# Token patterns
TOKEN_PATTERNS = {
    # $SYMBOL pattern - most common
    "symbol": re.compile(r'\$([A-Z]{2,10})\b', re.IGNORECASE),
    
    # CA: address pattern
    "ca_prefix": re.compile(r'(?:CA|Contract|Address)[\s:]+([A-Za-z0-9]{32,44})\b', re.IGNORECASE),
    
    # Solana pump.fun patterns
    "pump_address": re.compile(r'([1-9A-HJ-NP-Za-km-z]{32,44})pump\b'),
    "pump_link": re.compile(r'pump\.fun/(?:coin/)?([A-Za-z0-9]+)', re.IGNORECASE),
    
    # Base/ETH dexscreener links
    "dexscreener": re.compile(r'dexscreener\.com/(\w+)/([A-Za-z0-9]+)', re.IGNORECASE),
    
    # Birdeye links
    "birdeye": re.compile(r'birdeye\.so/token/([A-Za-z0-9]+)', re.IGNORECASE),
    
    # Jupiter links
    "jupiter": re.compile(r'jup\.ag/swap/\w+-([A-Za-z0-9]+)', re.IGNORECASE),
    
    # Photon links
    "photon": re.compile(r'photon-sol\.tinyastro\.io/\w+/([A-Za-z0-9]+)', re.IGNORECASE),
}

# Wallet patterns by chain
WALLET_PATTERNS = {
    "solana": re.compile(r'\b([1-9A-HJ-NP-Za-km-z]{32,44})\b'),
    "ethereum": re.compile(r'\b(0x[a-fA-F0-9]{40})\b'),
    "base": re.compile(r'\b(0x[a-fA-F0-9]{40})\b'),
    "bsc": re.compile(r'\b(0x[a-fA-F0-9]{40})\b'),
}

# Price patterns
PRICE_PATTERNS = {
    "usd": re.compile(r'\$?([\d,]+\.?\d*)\s*(?:USD|USDT|USDC)?\b', re.IGNORECASE),
    "sol": re.compile(r'([\d,]+\.?\d*)\s*SOL\b', re.IGNORECASE),
    "eth": re.compile(r'([\d,]+\.?\d*)\s*ETH\b', re.IGNORECASE),
    "bnb": re.compile(r'([\d,]+\.?\d*)\s*BNB\b', re.IGNORECASE),
    "multiplier": re.compile(r'(\d+(?:\.\d+)?)\s*[xX]\b'),
    "mcap": re.compile(r'(?:MC|mcap|market\s*cap)[\s:]*\$?([\d,]+\.?\d*)\s*([KMB])?', re.IGNORECASE),
}

# Whale/notable wallet labels
WHALE_PATTERNS = [
    (re.compile(r'\bwhale\b', re.IGNORECASE), "whale"),
    (re.compile(r'\bdev\s*wallet\b', re.IGNORECASE), "dev"),
    (re.compile(r'\bsniper\b', re.IGNORECASE), "sniper"),
    (re.compile(r'\bfresh\s*wallet\b', re.IGNORECASE), "fresh"),
    (re.compile(r'\binsider\b', re.IGNORECASE), "insider"),
    (re.compile(r'\bkol\b', re.IGNORECASE), "kol"),
]


def detect_chain_from_address(address: str) -> str:
    """Detect chain from address format"""
    if address.startswith("0x") and len(address) == 42:
        return "evm"  # Could be ETH, Base, or BSC - need context
    elif len(address) >= 32 and len(address) <= 44:
        # Check if valid Base58 (Solana)
        try:
            import re
            if re.match(r'^[1-9A-HJ-NP-Za-km-z]+$', address):
                return "solana"
        except:
            pass
    return "unknown"


def detect_chain_from_context(text: str) -> Optional[str]:
    """Detect chain from text context"""
    text_lower = text.lower()
    
    chain_keywords = {
        "solana": ["solana", "sol", "pump.fun", "raydium", "jupiter", "photon"],
        "base": ["base", "aerodrome", "basechain"],
        "bsc": ["bsc", "bnb", "binance", "pancakeswap"],
        "ethereum": ["eth", "ethereum", "uniswap", "mainnet"],
    }
    
    for chain, keywords in chain_keywords.items():
        for keyword in keywords:
            if keyword in text_lower:
                return chain
    
    return None


def extract_tokens(text: str, default_chain: str = "solana") -> List[TokenMatch]:
    """Extract token mentions from text"""
    tokens = []
    seen_addresses = set()
    seen_symbols = set()
    symbol_positions = {}  # Track symbol positions for association
    
    # Detect chain from context
    detected_chain = detect_chain_from_context(text) or default_chain
    
    # First pass: collect all symbols and their positions
    for match in TOKEN_PATTERNS["symbol"].finditer(text):
        symbol = match.group(1).upper()
        if symbol not in seen_symbols:
            seen_symbols.add(symbol)
            symbol_positions[symbol] = match.start()
    
    # Helper to find nearby symbol for an address
    def find_nearby_symbol(address_pos: int, max_distance: int = 100) -> Optional[str]:
        """Find a symbol that appears near this address position"""
        closest_symbol = None
        closest_distance = max_distance + 1
        for symbol, pos in symbol_positions.items():
            distance = abs(pos - address_pos)
            if distance < closest_distance:
                closest_distance = distance
                closest_symbol = symbol
        return closest_symbol if closest_distance <= max_distance else None
    
    # Extract CA: prefix patterns with symbol association
    for match in TOKEN_PATTERNS["ca_prefix"].finditer(text):
        address = match.group(1)
        if address not in seen_addresses:
            seen_addresses.add(address)
            chain = detect_chain_from_address(address)
            if chain == "evm":
                chain = detected_chain if detected_chain in ["base", "bsc", "ethereum"] else "base"
            elif chain == "solana":
                chain = "solana"
            else:
                chain = detected_chain
            
            # Try to find associated symbol
            nearby_symbol = find_nearby_symbol(match.start())
            
            tokens.append(TokenMatch(
                symbol=nearby_symbol,
                address=address,
                chain=chain,
                confidence=0.95,
                match_type="address"
            ))
            
            # Remove used symbol from available pool
            if nearby_symbol and nearby_symbol in symbol_positions:
                del symbol_positions[nearby_symbol]
    
    # Extract pump.fun addresses
    for match in TOKEN_PATTERNS["pump_address"].finditer(text):
        address = match.group(1)
        if address not in seen_addresses:
            seen_addresses.add(address)
            tokens.append(TokenMatch(
                symbol=None,
                address=address,
                chain="solana",
                confidence=0.9,
                match_type="pump_address"
            ))
    
    # Extract pump.fun links
    for match in TOKEN_PATTERNS["pump_link"].finditer(text):
        address = match.group(1)
        if address not in seen_addresses and len(address) > 10:
            seen_addresses.add(address)
            tokens.append(TokenMatch(
                symbol=None,
                address=address,
                chain="solana",
                confidence=0.95,
                match_type="pump_link"
            ))
    
    # Extract dexscreener links
    for match in TOKEN_PATTERNS["dexscreener"].finditer(text):
        chain = match.group(1).lower()
        address = match.group(2)
        if address not in seen_addresses:
            seen_addresses.add(address)
            # Map dexscreener chain names
            chain_map = {"solana": "solana", "base": "base", "bsc": "bsc", "ethereum": "ethereum"}
            mapped_chain = chain_map.get(chain, detected_chain)
            tokens.append(TokenMatch(
                symbol=None,
                address=address,
                chain=mapped_chain,
                confidence=0.95,
                match_type="dexscreener"
            ))
    
    # Extract birdeye links
    for match in TOKEN_PATTERNS["birdeye"].finditer(text):
        address = match.group(1)
        if address not in seen_addresses:
            seen_addresses.add(address)
            tokens.append(TokenMatch(
                symbol=None,
                address=address,
                chain="solana",
                confidence=0.95,
                match_type="birdeye"
            ))
    
    return tokens


def extract_wallets(text: str, default_chain: str = "solana") -> List[WalletMatch]:
    """Extract wallet addresses from text"""
    wallets = []
    seen_addresses = set()
    
    # Check for whale/label context
    text_lower = text.lower()
    detected_label = None
    for pattern, label in WHALE_PATTERNS:
        if pattern.search(text_lower):
            detected_label = label
            break
    
    # Detect chain from context
    detected_chain = detect_chain_from_context(text) or default_chain
    
    # Extract Solana addresses
    if detected_chain == "solana":
        for match in WALLET_PATTERNS["solana"].finditer(text):
            address = match.group(1)
            # Filter out likely token addresses (pump addresses)
            if address not in seen_addresses and "pump" not in text[max(0, match.start()-10):match.end()+10].lower():
                seen_addresses.add(address)
                wallets.append(WalletMatch(
                    address=address,
                    chain="solana",
                    label=detected_label
                ))
    
    # Extract EVM addresses
    for chain in ["ethereum", "base", "bsc"]:
        for match in WALLET_PATTERNS[chain].finditer(text):
            address = match.group(1)
            if address not in seen_addresses:
                seen_addresses.add(address)
                # Determine which EVM chain
                evm_chain = detected_chain if detected_chain in ["base", "bsc", "ethereum"] else "base"
                wallets.append(WalletMatch(
                    address=address,
                    chain=evm_chain,
                    label=detected_label
                ))
    
    return wallets


def extract_prices(text: str) -> List[PriceMatch]:
    """Extract price mentions from text"""
    prices = []
    
    # Extract USD values
    for match in PRICE_PATTERNS["usd"].finditer(text):
        try:
            value = float(match.group(1).replace(",", ""))
            prices.append(PriceMatch(value=value, unit="USD"))
        except ValueError:
            pass
    
    # Extract SOL values
    for match in PRICE_PATTERNS["sol"].finditer(text):
        try:
            value = float(match.group(1).replace(",", ""))
            prices.append(PriceMatch(value=value, unit="SOL"))
        except ValueError:
            pass
    
    # Extract ETH values
    for match in PRICE_PATTERNS["eth"].finditer(text):
        try:
            value = float(match.group(1).replace(",", ""))
            prices.append(PriceMatch(value=value, unit="ETH"))
        except ValueError:
            pass
    
    # Extract BNB values
    for match in PRICE_PATTERNS["bnb"].finditer(text):
        try:
            value = float(match.group(1).replace(",", ""))
            prices.append(PriceMatch(value=value, unit="BNB"))
        except ValueError:
            pass
    
    # Extract multipliers (10x, 100x)
    for match in PRICE_PATTERNS["multiplier"].finditer(text):
        try:
            value = float(match.group(1))
            prices.append(PriceMatch(value=value, unit="x"))
        except ValueError:
            pass
    
    # Extract market cap
    for match in PRICE_PATTERNS["mcap"].finditer(text):
        try:
            value = float(match.group(1).replace(",", ""))
            suffix = match.group(2)
            if suffix:
                suffix = suffix.upper()
                if suffix == "K":
                    value *= 1000
                elif suffix == "M":
                    value *= 1000000
                elif suffix == "B":
                    value *= 1000000000
            prices.append(PriceMatch(value=value, unit="MCAP"))
        except ValueError:
            pass
    
    return prices


class TokenPattern:
    """Token pattern matching utilities"""
    
    @staticmethod
    def is_valid_solana_address(address: str) -> bool:
        """Check if address is valid Solana format"""
        if len(address) < 32 or len(address) > 44:
            return False
        return bool(re.match(r'^[1-9A-HJ-NP-Za-km-z]+$', address))
    
    @staticmethod
    def is_valid_evm_address(address: str) -> bool:
        """Check if address is valid EVM format"""
        return bool(re.match(r'^0x[a-fA-F0-9]{40}$', address))


class WalletPattern:
    """Wallet pattern matching utilities"""
    
    @staticmethod
    def extract_with_context(text: str, address: str) -> str:
        """Extract context around a wallet address"""
        idx = text.find(address)
        if idx == -1:
            return ""
        start = max(0, idx - 100)
        end = min(len(text), idx + len(address) + 100)
        return text[start:end]
