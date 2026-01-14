"""Wallet tracking and profiling service"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict

import structlog

logger = structlog.get_logger()


@dataclass
class WalletData:
    """In-memory wallet data"""
    address: str
    chain: str
    
    # Labels
    label: Optional[str] = None  # whale, sniper, dev, known_caller
    tags: List[str] = field(default_factory=list)
    name: Optional[str] = None
    
    # Activity
    tokens_touched: int = 0
    token_addresses: List[str] = field(default_factory=list)
    
    # Mentions
    mention_count: int = 0
    mentioned_with_tokens: Dict[str, int] = field(default_factory=dict)  # token -> count
    
    # Performance (if we can track)
    total_trades: int = 0
    winning_trades: int = 0
    total_pnl: float = 0.0
    notable_wins: List[Dict[str, Any]] = field(default_factory=list)
    
    # Timeline
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    
    # Linked wallets
    linked_wallets: List[str] = field(default_factory=list)


class WalletTracker:
    """Service for tracking wallet activity"""
    
    def __init__(self):
        self._wallets: Dict[str, WalletData] = {}  # key: address:chain
    
    def get_wallet_key(self, address: str, chain: str) -> str:
        """Generate unique key for wallet"""
        return f"{address.lower()}:{chain.lower()}"
    
    def get_or_create_wallet(
        self,
        address: str,
        chain: str,
        label: Optional[str] = None,
    ) -> WalletData:
        """Get or create wallet data"""
        key = self.get_wallet_key(address, chain)
        
        if key not in self._wallets:
            self._wallets[key] = WalletData(
                address=address,
                chain=chain,
                label=label,
            )
        elif label and not self._wallets[key].label:
            self._wallets[key].label = label
        
        return self._wallets[key]
    
    def record_mention(
        self,
        address: str,
        chain: str,
        timestamp: datetime,
        label: Optional[str] = None,
        associated_token: Optional[str] = None,
    ) -> WalletData:
        """Record a wallet mention"""
        wallet = self.get_or_create_wallet(address, chain, label)
        
        wallet.mention_count += 1
        
        if wallet.first_seen is None:
            wallet.first_seen = timestamp
        wallet.last_seen = timestamp
        
        if associated_token:
            wallet.mentioned_with_tokens[associated_token] = \
                wallet.mentioned_with_tokens.get(associated_token, 0) + 1
            
            if associated_token not in wallet.token_addresses:
                wallet.token_addresses.append(associated_token)
                wallet.tokens_touched += 1
        
        logger.debug(
            "wallet_mention_recorded",
            address=address[:16] + "...",
            chain=chain,
            mentions=wallet.mention_count,
        )
        
        return wallet
    
    def record_activity(
        self,
        address: str,
        chain: str,
        activity_type: str,  # buy, sell, transfer
        token_address: str,
        amount_usd: float,
        timestamp: datetime,
        label: Optional[str] = None,
    ) -> WalletData:
        """Record wallet activity (buy/sell)"""
        wallet = self.get_or_create_wallet(address, chain, label)
        
        wallet.total_trades += 1
        
        if wallet.first_seen is None:
            wallet.first_seen = timestamp
        wallet.last_seen = timestamp
        
        if token_address not in wallet.token_addresses:
            wallet.token_addresses.append(token_address)
            wallet.tokens_touched += 1
        
        logger.debug(
            "wallet_activity_recorded",
            address=address[:16] + "...",
            chain=chain,
            activity=activity_type,
            amount_usd=amount_usd,
        )
        
        return wallet
    
    def add_label(self, address: str, chain: str, label: str):
        """Add or update wallet label"""
        wallet = self.get_or_create_wallet(address, chain)
        wallet.label = label
    
    def add_tag(self, address: str, chain: str, tag: str):
        """Add tag to wallet"""
        wallet = self.get_or_create_wallet(address, chain)
        if tag not in wallet.tags:
            wallet.tags.append(tag)
    
    def link_wallets(self, address1: str, address2: str, chain: str):
        """Link two wallets together"""
        wallet1 = self.get_or_create_wallet(address1, chain)
        wallet2 = self.get_or_create_wallet(address2, chain)
        
        if address2 not in wallet1.linked_wallets:
            wallet1.linked_wallets.append(address2)
        if address1 not in wallet2.linked_wallets:
            wallet2.linked_wallets.append(address1)
    
    def record_win(
        self,
        address: str,
        chain: str,
        token_address: str,
        return_percent: float,
        timestamp: datetime,
    ):
        """Record a winning trade"""
        wallet = self.get_or_create_wallet(address, chain)
        
        wallet.winning_trades += 1
        
        wallet.notable_wins.append({
            "token": token_address,
            "return": return_percent,
            "timestamp": timestamp.isoformat(),
        })
        
        # Keep only last 20 notable wins
        wallet.notable_wins = wallet.notable_wins[-20:]
    
    def get_wallet(self, address: str, chain: str) -> Optional[Dict[str, Any]]:
        """Get wallet data as dictionary"""
        key = self.get_wallet_key(address, chain)
        wallet = self._wallets.get(key)
        
        if not wallet:
            return None
        
        # Calculate win rate
        win_rate = None
        if wallet.total_trades > 0:
            win_rate = wallet.winning_trades / wallet.total_trades
        
        return {
            "address": wallet.address,
            "chain": wallet.chain,
            "label": wallet.label,
            "tags": wallet.tags,
            "name": wallet.name,
            "activity": {
                "tokens_touched": wallet.tokens_touched,
                "total_trades": wallet.total_trades,
                "winning_trades": wallet.winning_trades,
                "win_rate": win_rate,
            },
            "mentions": {
                "count": wallet.mention_count,
                "top_tokens": sorted(
                    wallet.mentioned_with_tokens.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5],
            },
            "timeline": {
                "first_seen": wallet.first_seen.isoformat() if wallet.first_seen else None,
                "last_seen": wallet.last_seen.isoformat() if wallet.last_seen else None,
            },
            "notable_wins": wallet.notable_wins[-5:],
            "linked_wallets": wallet.linked_wallets,
        }
    
    def get_whales(
        self,
        chain: Optional[str] = None,
        min_mentions: int = 3,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get whale wallets"""
        whales = []
        
        for wallet in self._wallets.values():
            if chain and wallet.chain != chain:
                continue
            
            if wallet.label not in ["whale", "sniper", "kol"]:
                continue
            
            if wallet.mention_count < min_mentions:
                continue
            
            whales.append(self.get_wallet(wallet.address, wallet.chain))
        
        # Sort by mention count
        whales.sort(key=lambda w: w.get("mentions", {}).get("count", 0), reverse=True)
        
        return whales[:limit]
    
    def get_wallets_for_token(
        self,
        token_address: str,
        min_mentions: int = 1,
    ) -> List[Dict[str, Any]]:
        """Get wallets mentioned with a specific token"""
        results = []
        
        for wallet in self._wallets.values():
            if token_address in wallet.mentioned_with_tokens:
                if wallet.mentioned_with_tokens[token_address] >= min_mentions:
                    results.append(self.get_wallet(wallet.address, wallet.chain))
        
        # Sort by mentions of this token
        results.sort(
            key=lambda w: next(
                (c for t, c in w.get("mentions", {}).get("top_tokens", []) if t == token_address),
                0
            ),
            reverse=True
        )
        
        return results
    
    def find_connected_wallets(
        self,
        address: str,
        chain: str,
        depth: int = 2,
    ) -> List[Dict[str, Any]]:
        """Find wallets connected to this address"""
        key = self.get_wallet_key(address, chain)
        wallet = self._wallets.get(key)
        
        if not wallet:
            return []
        
        # BFS to find connected wallets
        visited = {address}
        to_visit = [(addr, 1) for addr in wallet.linked_wallets]
        connected = []
        
        while to_visit:
            current_addr, current_depth = to_visit.pop(0)
            
            if current_addr in visited:
                continue
            
            visited.add(current_addr)
            current_key = self.get_wallet_key(current_addr, chain)
            current_wallet = self._wallets.get(current_key)
            
            if current_wallet:
                connected.append({
                    "wallet": self.get_wallet(current_addr, chain),
                    "depth": current_depth,
                })
                
                if current_depth < depth:
                    for linked in current_wallet.linked_wallets:
                        if linked not in visited:
                            to_visit.append((linked, current_depth + 1))
        
        return connected


# Singleton instance
wallet_tracker = WalletTracker()
