"""Extract rich context and narratives from messages about tokens"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import structlog

logger = structlog.get_logger()


class NarrativeType(Enum):
    """Types of narratives/themes in crypto discussions"""
    PRICE_TARGET = "price_target"
    WHALE_ACTIVITY = "whale_activity"
    DEV_ACTIVITY = "dev_activity"
    LISTING = "listing"
    PARTNERSHIP = "partnership"
    LAUNCH = "launch"
    AIRDROP = "airdrop"
    BURN = "burn"
    MIGRATION = "migration"
    RUG_WARNING = "rug_warning"
    COMMUNITY = "community"
    TECHNICAL = "technical"
    MEME = "meme"
    UTILITY = "utility"
    INFLUENCER_CALL = "influencer_call"
    ENTRY_POINT = "entry_point"
    EXIT_WARNING = "exit_warning"


@dataclass
class ExtractedContext:
    """Rich context extracted from a message"""
    # Key claims/narratives
    narratives: List[Dict[str, Any]] = field(default_factory=list)
    
    # Price-related
    price_targets: List[Dict[str, Any]] = field(default_factory=list)
    entry_points: List[Dict[str, Any]] = field(default_factory=list)
    market_cap_targets: List[Dict[str, Any]] = field(default_factory=list)
    
    # Actor-related
    whale_mentions: List[str] = field(default_factory=list)
    influencer_mentions: List[str] = field(default_factory=list)
    dev_mentions: List[str] = field(default_factory=list)
    
    # Key info
    key_claims: List[str] = field(default_factory=list)
    risk_mentions: List[str] = field(default_factory=list)
    catalyst_mentions: List[str] = field(default_factory=list)
    
    # Extracted quotes/highlights
    highlights: List[str] = field(default_factory=list)
    
    # Overall assessment
    conviction_level: str = "medium"  # low, medium, high
    urgency_level: str = "normal"  # low, normal, high, urgent


# Patterns for extracting rich context
NARRATIVE_PATTERNS = {
    NarrativeType.PRICE_TARGET: [
        re.compile(r'(?:target|pt|price\s*target)[\s:]*\$?([\d,]+\.?\d*)\s*([KMB])?', re.IGNORECASE),
        re.compile(r'going\s+to\s+\$?([\d,]+\.?\d*)\s*([KMB])?', re.IGNORECASE),
        re.compile(r'will\s+hit\s+\$?([\d,]+\.?\d*)\s*([KMB])?', re.IGNORECASE),
        re.compile(r'(\d+)\s*[xX]\s+(?:from\s+here|easy|minimum|potential)', re.IGNORECASE),
    ],
    NarrativeType.WHALE_ACTIVITY: [
        re.compile(r'whale[s]?\s+(?:are\s+)?(?:buying|accumulating|loading|aping)', re.IGNORECASE),
        re.compile(r'big\s+(?:wallet|bag|buy)[s]?\s+(?:detected|spotted|coming\s+in)', re.IGNORECASE),
        re.compile(r'smart\s+money\s+(?:is\s+)?(?:in|buying|accumulating)', re.IGNORECASE),
    ],
    NarrativeType.DEV_ACTIVITY: [
        re.compile(r'dev[s]?\s+(?:are\s+)?(?:based|legit|doxxed|active|shipping)', re.IGNORECASE),
        re.compile(r'dev[s]?\s+(?:sold|dumped|rugged|abandoned)', re.IGNORECASE),
        re.compile(r'(?:locked|burned)\s+(?:lp|liquidity)', re.IGNORECASE),
    ],
    NarrativeType.LISTING: [
        re.compile(r'(?:cex|binance|coinbase|kucoin|bybit)\s+listing', re.IGNORECASE),
        re.compile(r'getting\s+listed\s+on', re.IGNORECASE),
    ],
    NarrativeType.LAUNCH: [
        re.compile(r'(?:just\s+)?launch(?:ed|ing)', re.IGNORECASE),
        re.compile(r'(?:stealth\s+)?launch', re.IGNORECASE),
        re.compile(r'(?:fair\s+)?launch', re.IGNORECASE),
    ],
    NarrativeType.RUG_WARNING: [
        re.compile(r'(?:looks?\s+like\s+a\s+)?(?:rug|scam|honeypot)', re.IGNORECASE),
        re.compile(r'(?:dev[s]?\s+)?(?:rugged|dumping|selling)', re.IGNORECASE),
        re.compile(r'stay\s+away|avoid|don\'t\s+(?:buy|ape)', re.IGNORECASE),
    ],
    NarrativeType.INFLUENCER_CALL: [
        re.compile(r'(?:kol|influencer|ct)\s+(?:is\s+)?(?:calling|shilling|posting)', re.IGNORECASE),
        re.compile(r'(?:big|major)\s+(?:call|shill)\s+(?:incoming|coming)', re.IGNORECASE),
    ],
    NarrativeType.ENTRY_POINT: [
        re.compile(r'(?:good|great|perfect)\s+entry', re.IGNORECASE),
        re.compile(r'buy\s+(?:the\s+)?dip', re.IGNORECASE),
        re.compile(r'(?:loading|accumulating)\s+(?:here|now)', re.IGNORECASE),
        re.compile(r'(?:this\s+is\s+)?(?:the\s+)?bottom', re.IGNORECASE),
    ],
    NarrativeType.EXIT_WARNING: [
        re.compile(r'(?:take|taking)\s+profits?', re.IGNORECASE),
        re.compile(r'(?:sell|selling)\s+(?:now|soon|some)', re.IGNORECASE),
        re.compile(r'(?:top\s+is\s+)?(?:in|near)', re.IGNORECASE),
    ],
}

# Key claim patterns
KEY_CLAIM_PATTERNS = [
    # Strong bullish claims
    (re.compile(r'(?:this\s+)?(?:will|gonna)\s+(?:100|1000|moon|pump|explode)', re.IGNORECASE), "strong_bullish"),
    (re.compile(r'(?:next|new)\s+(?:100x|1000x|gem)', re.IGNORECASE), "strong_bullish"),
    (re.compile(r'(?:easy|free)\s+(?:money|gains|100x)', re.IGNORECASE), "strong_bullish"),
    
    # Conviction claims
    (re.compile(r'(?:i\'m|im)\s+(?:all\s+in|loaded|max\s+bid)', re.IGNORECASE), "high_conviction"),
    (re.compile(r'(?:biggest|best)\s+(?:play|bet|opportunity)', re.IGNORECASE), "high_conviction"),
    
    # Risk claims
    (re.compile(r'(?:nfa|not\s+financial\s+advice|dyor)', re.IGNORECASE), "disclaimer"),
    (re.compile(r'(?:risky|high\s+risk|gamble)', re.IGNORECASE), "risk_warning"),
]

# Urgency patterns
URGENCY_PATTERNS = [
    (re.compile(r'(?:buy|ape)\s+(?:now|asap|quick|fast)', re.IGNORECASE), "urgent"),
    (re.compile(r'(?:don\'t|dont)\s+(?:miss|sleep|fade)', re.IGNORECASE), "urgent"),
    (re.compile(r'(?:last|final)\s+(?:chance|call|warning)', re.IGNORECASE), "urgent"),
    (re.compile(r'(?:about\s+to|gonna)\s+(?:pump|moon|explode)', re.IGNORECASE), "high"),
]

# Catalyst patterns
CATALYST_PATTERNS = [
    re.compile(r'(?:announcement|news|update)\s+(?:coming|soon|today)', re.IGNORECASE),
    re.compile(r'(?:partnership|collab)\s+with\s+(\w+)', re.IGNORECASE),
    re.compile(r'(?:audit|kyc|doxx)\s+(?:done|complete|coming)', re.IGNORECASE),
    re.compile(r'(?:marketing|campaign)\s+(?:starting|live|incoming)', re.IGNORECASE),
]


class ContextExtractor:
    """Extract rich context from messages"""
    
    def extract_context(self, text: str, source_name: str = "") -> ExtractedContext:
        """
        Extract rich context from a message.
        
        Args:
            text: Message text
            source_name: Name of the source (channel/group)
        
        Returns:
            ExtractedContext with extracted information
        """
        context = ExtractedContext()
        text_lower = text.lower()
        
        # Extract narratives
        for narrative_type, patterns in NARRATIVE_PATTERNS.items():
            for pattern in patterns:
                matches = pattern.findall(text)
                if matches:
                    context.narratives.append({
                        "type": narrative_type.value,
                        "matched": True,
                        "raw_matches": matches[:3],  # Limit matches
                    })
                    break
        
        # Extract price targets
        for pattern in NARRATIVE_PATTERNS[NarrativeType.PRICE_TARGET]:
            for match in pattern.finditer(text):
                try:
                    if isinstance(match.group(1), str):
                        value = float(match.group(1).replace(",", ""))
                        suffix = match.group(2) if len(match.groups()) > 1 else None
                        if suffix:
                            suffix = suffix.upper()
                            if suffix == "K":
                                value *= 1000
                            elif suffix == "M":
                                value *= 1000000
                            elif suffix == "B":
                                value *= 1000000000
                        
                        context.price_targets.append({
                            "value": value,
                            "raw": match.group(0),
                            "type": "price" if value < 1000 else "mcap"
                        })
                except (ValueError, IndexError):
                    pass
        
        # Extract key claims
        for pattern, claim_type in KEY_CLAIM_PATTERNS:
            if pattern.search(text):
                context.key_claims.append(claim_type)
        
        # Determine conviction level
        if "strong_bullish" in context.key_claims or "high_conviction" in context.key_claims:
            context.conviction_level = "high"
        elif "risk_warning" in context.key_claims:
            context.conviction_level = "low"
        
        # Determine urgency level
        for pattern, urgency in URGENCY_PATTERNS:
            if pattern.search(text):
                context.urgency_level = urgency
                break
        
        # Extract catalysts
        for pattern in CATALYST_PATTERNS:
            match = pattern.search(text)
            if match:
                context.catalyst_mentions.append(match.group(0))
        
        # Extract risk mentions
        risk_words = ["rug", "scam", "honeypot", "dump", "sell", "risky", "careful", "warning"]
        for word in risk_words:
            if word in text_lower:
                # Get surrounding context
                idx = text_lower.find(word)
                start = max(0, idx - 30)
                end = min(len(text), idx + len(word) + 30)
                context.risk_mentions.append(text[start:end].strip())
        
        # Extract whale mentions
        whale_patterns = [
            re.compile(r'whale[s]?\s+\w+', re.IGNORECASE),
            re.compile(r'big\s+(?:wallet|buyer|holder)', re.IGNORECASE),
            re.compile(r'smart\s+money', re.IGNORECASE),
        ]
        for pattern in whale_patterns:
            match = pattern.search(text)
            if match:
                context.whale_mentions.append(match.group(0))
        
        # Extract highlights (key sentences)
        sentences = re.split(r'[.!?\n]', text)
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20 and len(sentence) < 200:
                # Check if sentence has interesting content
                interesting_words = ["moon", "pump", "gem", "alpha", "entry", "buy", "whale", "dev", "launch"]
                if any(word in sentence.lower() for word in interesting_words):
                    context.highlights.append(sentence)
        
        # Limit highlights
        context.highlights = context.highlights[:3]
        
        return context
    
    def extract_token_context(
        self,
        messages: List[Dict[str, Any]],
        token_address: str,
    ) -> Dict[str, Any]:
        """
        Extract aggregated context about a token from multiple messages.
        
        Args:
            messages: List of message dicts
            token_address: Token address to focus on
        
        Returns:
            Aggregated context about the token
        """
        all_narratives = []
        all_price_targets = []
        all_key_claims = []
        all_risk_mentions = []
        all_catalyst_mentions = []
        all_highlights = []
        conviction_scores = []
        urgency_scores = []
        
        urgency_map = {"low": 1, "normal": 2, "high": 3, "urgent": 4}
        conviction_map = {"low": 1, "medium": 2, "high": 3}
        
        for msg in messages:
            text = msg.get("original_text", msg.get("text", ""))
            source = msg.get("source_name", "")
            
            ctx = self.extract_context(text, source)
            
            all_narratives.extend(ctx.narratives)
            all_price_targets.extend(ctx.price_targets)
            all_key_claims.extend(ctx.key_claims)
            all_risk_mentions.extend(ctx.risk_mentions)
            all_catalyst_mentions.extend(ctx.catalyst_mentions)
            all_highlights.extend(ctx.highlights)
            
            conviction_scores.append(conviction_map.get(ctx.conviction_level, 2))
            urgency_scores.append(urgency_map.get(ctx.urgency_level, 2))
        
        # Aggregate narratives by type
        narrative_counts = {}
        for n in all_narratives:
            ntype = n["type"]
            narrative_counts[ntype] = narrative_counts.get(ntype, 0) + 1
        
        top_narratives = sorted(narrative_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Aggregate price targets
        if all_price_targets:
            price_values = [p["value"] for p in all_price_targets]
            avg_target = sum(price_values) / len(price_values)
            max_target = max(price_values)
            min_target = min(price_values)
        else:
            avg_target = max_target = min_target = None
        
        # Count key claims
        claim_counts = {}
        for claim in all_key_claims:
            claim_counts[claim] = claim_counts.get(claim, 0) + 1
        
        # Calculate average conviction and urgency
        avg_conviction = sum(conviction_scores) / len(conviction_scores) if conviction_scores else 2
        avg_urgency = sum(urgency_scores) / len(urgency_scores) if urgency_scores else 2
        
        # Determine overall conviction level
        if avg_conviction >= 2.5:
            overall_conviction = "high"
        elif avg_conviction >= 1.5:
            overall_conviction = "medium"
        else:
            overall_conviction = "low"
        
        # Determine overall urgency
        if avg_urgency >= 3:
            overall_urgency = "urgent"
        elif avg_urgency >= 2.5:
            overall_urgency = "high"
        else:
            overall_urgency = "normal"
        
        return {
            "top_narratives": [{"type": t, "count": c} for t, c in top_narratives],
            "price_targets": {
                "average": avg_target,
                "max": max_target,
                "min": min_target,
                "count": len(all_price_targets),
                "targets": all_price_targets[:5],
            },
            "key_claims": claim_counts,
            "risk_mentions": list(set(all_risk_mentions))[:5],
            "catalyst_mentions": list(set(all_catalyst_mentions))[:5],
            "highlights": list(set(all_highlights))[:10],
            "conviction_level": overall_conviction,
            "urgency_level": overall_urgency,
            "messages_analyzed": len(messages),
        }


# Singleton instance
context_extractor = ContextExtractor()
