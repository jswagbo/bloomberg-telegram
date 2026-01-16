"""
Opinion Extractor - Identifies messages containing valuable alpha/insights.

This flips the traditional approach:
- Instead of: Find token → Look for discussion
- We do: Find ALL opinions → Figure out which token they apply to

This captures way more alpha because people often discuss tokens without
explicitly mentioning contract addresses.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class OpinionType(Enum):
    """Types of opinions/insights"""
    PRICE_PREDICTION = "price_prediction"  # "gonna 10x", "easy 100m mc"
    ENTRY_SIGNAL = "entry_signal"  # "good entry", "buying here", "loading"
    EXIT_SIGNAL = "exit_signal"  # "taking profits", "selling here"
    WARNING = "warning"  # "careful", "looks ruggy", "dev sold"
    CATALYST = "catalyst"  # "listing coming", "partnership", "update"
    SOCIAL_PROOF = "social_proof"  # "whales buying", "influencer mentioned"
    TECHNICAL = "technical"  # "chart looks good", "breaking resistance"
    FUNDAMENTAL = "fundamental"  # "good dev", "strong community", "utility"
    GENERAL_BULLISH = "general_bullish"  # General positive sentiment
    GENERAL_BEARISH = "general_bearish"  # General negative sentiment


@dataclass
class ExtractedOpinion:
    """An opinion/insight extracted from a message"""
    text: str
    opinion_type: OpinionType
    confidence: float  # 0-1 how confident this is real alpha
    sentiment: str  # bullish, bearish, neutral
    key_claim: Optional[str] = None  # The main claim/prediction
    price_target: Optional[str] = None  # If mentioned
    source_name: str = ""
    source_id: str = ""
    message_id: int = 0
    timestamp: Optional[str] = None
    
    # Token reference (may be resolved later)
    token_symbol: Optional[str] = None
    token_address: Optional[str] = None
    token_name: Optional[str] = None


# Patterns that indicate a message contains valuable opinion/alpha
OPINION_PATTERNS = {
    # Price predictions
    OpinionType.PRICE_PREDICTION: [
        r'\b(\d+)x\b',  # "10x", "100x"
        r'\b(moon|mooning|sends?|rips?|pumps?)\b',
        r'\beasy\s+\d+[mk]\b',  # "easy 100m"
        r'\b(floor|target|pt)\s*[:\s]*\$?\d+',
        r'\b(going to|gonna|will hit)\s+\$?\d+',
        r'\bmc\s*(of\s*)?\d+[mkb]',  # market cap predictions
    ],
    
    # Entry signals
    OpinionType.ENTRY_SIGNAL: [
        r'\b(buying|bought|loading|loaded|accumulating|adding|aping|aped)\b',
        r'\bgood\s+(entry|buy|dip)\b',
        r'\b(entry|dip)\s+(here|now|zone)\b',
        r'\b(undervalued|cheap|discount)\b',
        r'\bthis\s+is\s+(it|the\s+one)\b',
    ],
    
    # Exit signals
    OpinionType.EXIT_SIGNAL: [
        r'\b(selling|sold|taking\s+profits?|tp|exiting|dumping)\b',
        r'\b(overvalued|overbought|topped?)\b',
        r'\bget\s+out\b',
    ],
    
    # Warnings
    OpinionType.WARNING: [
        r'\b(careful|caution|warning|watch\s+out|be\s+careful)\b',
        r'\b(rug|rugged|rugpull|scam|honeypot)\b',
        r'\b(dev\s+(sold|dumped|left)|team\s+sold)\b',
        r'\b(suspicious|sketchy|risky|gamble)\b',
        r'\bdon\'?t\s+(buy|ape|fomo)\b',
    ],
    
    # Catalysts
    OpinionType.CATALYST: [
        r'\b(listing|listed|cex|binance|coinbase|kraken)\b',
        r'\b(partnership|collab|announcement)\b',
        r'\b(launch|launching|release|update|upgrade|v2)\b',
        r'\b(audit|audited|kyc|doxxed)\b',
        r'\b(airdrop|snapshot)\b',
    ],
    
    # Social proof
    OpinionType.SOCIAL_PROOF: [
        r'\b(whale|whales?)\s+(buying|bought|accumulating|in)\b',
        r'\b(influencer|kol|ct|ansem|murad)\b',
        r'\beveryone\s+(is\s+)?(talking|buying|aping)\b',
        r'\b(trending|viral|blowing\s+up)\b',
    ],
    
    # Technical analysis
    OpinionType.TECHNICAL: [
        r'\b(chart|ta|technical)\b',
        r'\b(support|resistance|breakout|breakdown)\b',
        r'\b(bullish|bearish)\s+(pattern|structure|divergence)\b',
        r'\b(volume|liquidity)\s+(increasing|spiking|low|high)\b',
        r'\b(rsi|macd|ma|ema)\b',
    ],
    
    # Fundamental analysis
    OpinionType.FUNDAMENTAL: [
        r'\b(dev|team|founder)\s+(is\s+)?(based|legit|active|good|solid)\b',
        r'\b(community|tg|telegram)\s+(is\s+)?(strong|active|growing)\b',
        r'\b(utility|usecase|product)\b',
        r'\b(tokenomics|supply|distribution)\b',
        r'\b(narrative|meta|trend)\b',
    ],
}

# General sentiment patterns
BULLISH_PATTERNS = [
    r'\b(bullish|long|buy|moon|pump|gem|alpha|based|fire|lfg|wagmi)\b',
    r'\b(love|like|excited|confident|optimistic)\b',
    r'\b(strong|solid|great|amazing|incredible)\b',
    r'🚀|🔥|💎|💰|📈|🐂|✅',
]

BEARISH_PATTERNS = [
    r'\b(bearish|short|sell|dump|rug|scam|dead|ngmi)\b',
    r'\b(hate|dislike|worried|concerned|skeptical)\b',
    r'\b(weak|bad|terrible|awful|trash)\b',
    r'📉|💀|⚠️|🚨|❌|🐻',
]

# Patterns to SKIP (not real opinions)
SKIP_PATTERNS = [
    r'^https?://',  # URLs only
    r'^(ca|contract|mint|address)[:\s]',  # Just posting address
    r'pump\.fun/',
    r'dexscreener\.com/',
    r'birdeye\.so/',
    r'^[A-Za-z0-9]{32,}$',  # Just an address
]


class OpinionExtractor:
    """Extracts opinions and insights from messages"""
    
    def __init__(self):
        # Compile patterns for efficiency
        self._opinion_patterns = {
            otype: [re.compile(p, re.IGNORECASE) for p in patterns]
            for otype, patterns in OPINION_PATTERNS.items()
        }
        self._bullish_patterns = [re.compile(p, re.IGNORECASE) for p in BULLISH_PATTERNS]
        self._bearish_patterns = [re.compile(p, re.IGNORECASE) for p in BEARISH_PATTERNS]
        self._skip_patterns = [re.compile(p, re.IGNORECASE) for p in SKIP_PATTERNS]
    
    def should_skip(self, text: str) -> bool:
        """Check if message should be skipped (not a real opinion)"""
        if not text or len(text.strip()) < 15:
            return True
        
        for pattern in self._skip_patterns:
            if pattern.search(text):
                return True
        
        return False
    
    def extract_sentiment(self, text: str) -> Tuple[str, float]:
        """Extract sentiment from text. Returns (sentiment, confidence)"""
        bullish_score = sum(1 for p in self._bullish_patterns if p.search(text))
        bearish_score = sum(1 for p in self._bearish_patterns if p.search(text))
        
        total = bullish_score + bearish_score
        if total == 0:
            return "neutral", 0.5
        
        if bullish_score > bearish_score:
            confidence = bullish_score / max(total, 1)
            return "bullish", min(confidence, 1.0)
        elif bearish_score > bullish_score:
            confidence = bearish_score / max(total, 1)
            return "bearish", min(confidence, 1.0)
        else:
            return "neutral", 0.5
    
    def extract_opinion_types(self, text: str) -> List[Tuple[OpinionType, float]]:
        """Extract opinion types from text with confidence scores"""
        found_types = []
        
        for opinion_type, patterns in self._opinion_patterns.items():
            matches = sum(1 for p in patterns if p.search(text))
            if matches > 0:
                # Confidence based on number of matches
                confidence = min(matches * 0.3, 1.0)
                found_types.append((opinion_type, confidence))
        
        return found_types
    
    def extract_price_target(self, text: str) -> Optional[str]:
        """Extract price target or prediction if mentioned"""
        patterns = [
            r'(\d+)[xX]',  # "10x"
            r'(\$[\d,.]+[kmb]?)',  # "$0.01", "$100k"
            r'(\d+[kmb]\s*(mc|market\s*cap))',  # "100m mc"
            r'(target|pt)[:\s]*(\$?[\d,.]+[kmb]?)',  # "target: $1"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return None
    
    def extract_key_claim(self, text: str) -> Optional[str]:
        """Extract the main claim/thesis from the opinion"""
        # Try to find the most informative sentence
        sentences = re.split(r'[.!?\n]', text)
        
        best_sentence = None
        best_score = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:
                continue
            
            # Score based on opinion indicators
            score = 0
            for patterns in self._opinion_patterns.values():
                score += sum(1 for p in patterns if p.search(sentence))
            
            if score > best_score:
                best_score = score
                best_sentence = sentence
        
        return best_sentence[:200] if best_sentence else None
    
    def extract_token_reference(self, text: str) -> Dict[str, Optional[str]]:
        """Try to extract token reference from the opinion text"""
        result = {
            "symbol": None,
            "address": None,
            "name": None,
        }
        
        # Look for $SYMBOL pattern
        symbol_match = re.search(r'\$([A-Za-z][A-Za-z0-9]{1,10})\b', text)
        if symbol_match:
            result["symbol"] = symbol_match.group(1).upper()
        
        # Look for token address patterns
        # Solana addresses (base58, 32-44 chars)
        sol_match = re.search(r'\b([1-9A-HJ-NP-Za-km-z]{32,44})\b', text)
        if sol_match:
            addr = sol_match.group(1)
            # Verify it's likely an address (mix of cases, numbers)
            if re.search(r'[a-z]', addr) and re.search(r'[A-Z]', addr):
                result["address"] = addr
        
        # ETH/Base addresses (0x...)
        eth_match = re.search(r'\b(0x[a-fA-F0-9]{40})\b', text)
        if eth_match:
            result["address"] = eth_match.group(1)
        
        return result
    
    def extract_opinion(
        self,
        text: str,
        source_name: str = "",
        source_id: str = "",
        message_id: int = 0,
        timestamp: Optional[str] = None,
    ) -> Optional[ExtractedOpinion]:
        """
        Extract opinion/insight from a message.
        
        Returns None if the message doesn't contain valuable opinion.
        """
        if self.should_skip(text):
            return None
        
        # Get opinion types
        opinion_types = self.extract_opinion_types(text)
        
        # Also check for general sentiment even without specific patterns
        sentiment, sent_confidence = self.extract_sentiment(text)
        
        # If no specific opinion type but has clear sentiment, categorize it
        if not opinion_types and sentiment != "neutral" and sent_confidence > 0.6:
            if sentiment == "bullish":
                opinion_types = [(OpinionType.GENERAL_BULLISH, sent_confidence)]
            else:
                opinion_types = [(OpinionType.GENERAL_BEARISH, sent_confidence)]
        
        # Skip if no opinion detected
        if not opinion_types:
            return None
        
        # Get the primary opinion type (highest confidence)
        primary_type, primary_conf = max(opinion_types, key=lambda x: x[1])
        
        # Calculate overall confidence
        confidence = min(primary_conf + (len(opinion_types) - 1) * 0.1, 1.0)
        
        # Extract additional info
        token_ref = self.extract_token_reference(text)
        price_target = self.extract_price_target(text)
        key_claim = self.extract_key_claim(text)
        
        return ExtractedOpinion(
            text=text[:1000],  # Limit text length
            opinion_type=primary_type,
            confidence=confidence,
            sentiment=sentiment,
            key_claim=key_claim,
            price_target=price_target,
            source_name=source_name,
            source_id=source_id,
            message_id=message_id,
            timestamp=timestamp,
            token_symbol=token_ref["symbol"],
            token_address=token_ref["address"],
            token_name=token_ref["name"],
        )
    
    def extract_opinions_batch(
        self,
        messages: List[Dict[str, Any]],
    ) -> List[ExtractedOpinion]:
        """
        Extract opinions from a batch of messages.
        
        Args:
            messages: List of message dicts with 'text', 'source_name', etc.
        
        Returns:
            List of extracted opinions
        """
        opinions = []
        
        for msg in messages:
            text = msg.get("text") or msg.get("original_text", "")
            opinion = self.extract_opinion(
                text=text,
                source_name=msg.get("source_name", ""),
                source_id=str(msg.get("source_id", "")),
                message_id=msg.get("message_id", 0),
                timestamp=msg.get("timestamp"),
            )
            if opinion:
                opinions.append(opinion)
        
        return opinions


# Singleton instance
opinion_extractor = OpinionExtractor()
