"""Sentiment analysis for crypto messages"""

import re
from typing import Tuple, List
from dataclasses import dataclass
from enum import Enum


class Sentiment(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class SentimentResult:
    """Result of sentiment analysis"""
    sentiment: Sentiment
    score: float  # -1 to 1
    confidence: float  # 0 to 1
    signals: List[str]  # Matched signals


# Sentiment signals with weights
BULLISH_SIGNALS = {
    # Emojis (high weight)
    "🚀": 0.3,
    "🔥": 0.25,
    "💎": 0.2,
    "🌙": 0.25,
    "📈": 0.2,
    "💰": 0.15,
    "🎯": 0.15,
    "⬆️": 0.15,
    "✅": 0.1,
    "💪": 0.1,
    "🐂": 0.2,
    "🦍": 0.15,
    
    # Phrases (various weights)
    "moon": 0.3,
    "mooning": 0.35,
    "lfg": 0.3,
    "let's go": 0.2,
    "send it": 0.3,
    "ape": 0.25,
    "aping": 0.3,
    "buy": 0.15,
    "buying": 0.15,
    "bought": 0.15,
    "bullish": 0.3,
    "pump": 0.2,
    "pumping": 0.25,
    "100x": 0.35,
    "10x": 0.25,
    "gem": 0.2,
    "alpha": 0.2,
    "early": 0.15,
    "potential": 0.1,
    "undervalued": 0.2,
    "accumulate": 0.2,
    "accumulating": 0.2,
    "loading": 0.2,
    "loaded": 0.15,
    "bags": 0.1,
    "holding": 0.1,
    "hodl": 0.15,
    "diamond hands": 0.2,
    "strong": 0.1,
    "breakout": 0.2,
    "breaking out": 0.25,
    "all time high": 0.2,
    "ath": 0.15,
    "parabolic": 0.3,
    "explosive": 0.2,
    "insane": 0.15,
    "massive": 0.15,
    "huge": 0.1,
    "whale": 0.15,  # whale buying is usually bullish
    "smart money": 0.2,
    "insider": 0.15,
    "don't miss": 0.2,
    "dont miss": 0.2,
    "easy money": 0.2,
    "free money": 0.2,
    "guaranteed": 0.15,
    "next": 0.1,  # "next big thing"
    "based": 0.15,
    "chad": 0.1,
    "fomo": 0.15,
}

BEARISH_SIGNALS = {
    # Emojis
    "📉": 0.25,
    "💀": 0.3,
    "🔴": 0.2,
    "⚠️": 0.2,
    "🚨": 0.2,
    "⬇️": 0.15,
    "❌": 0.15,
    "🐻": 0.2,
    "😭": 0.1,
    "💩": 0.2,
    
    # Phrases
    "rug": 0.4,
    "rugged": 0.45,
    "rugpull": 0.45,
    "rug pull": 0.45,
    "scam": 0.4,
    "scammer": 0.4,
    "honeypot": 0.45,
    "honey pot": 0.45,
    "dump": 0.3,
    "dumping": 0.35,
    "dumped": 0.3,
    "sell": 0.15,
    "selling": 0.15,
    "sold": 0.15,
    "bearish": 0.3,
    "dead": 0.3,
    "dying": 0.25,
    "rip": 0.25,
    "over": 0.15,
    "finished": 0.2,
    "done": 0.15,
    "avoid": 0.3,
    "stay away": 0.35,
    "red flag": 0.3,
    "red flags": 0.3,
    "warning": 0.25,
    "careful": 0.15,
    "caution": 0.15,
    "fake": 0.3,
    "fraud": 0.35,
    "dev sold": 0.4,
    "dev dumped": 0.4,
    "dev wallet": 0.2,  # often mentioned in negative context
    "exit scam": 0.45,
    "ponzi": 0.4,
    "crash": 0.3,
    "crashing": 0.35,
    "tanking": 0.3,
    "plummeting": 0.35,
    "bleeding": 0.25,
    "rekt": 0.3,
    "wrecked": 0.25,
    "loss": 0.2,
    "lost": 0.15,
    "no liquidity": 0.35,
    "locked": 0.15,  # often negative in context
    "mint": 0.2,  # mint enabled = bad
    "unlocked": 0.2,
    "jeet": 0.25,
    "jeets": 0.25,
    "paper hands": 0.15,
    "ngmi": 0.2,
    "not gonna make it": 0.2,
}

NEUTRAL_SIGNALS = {
    "watching": 0.1,
    "interesting": 0.1,
    "new": 0.05,
    "launched": 0.1,
    "launching": 0.1,
    "update": 0.05,
    "news": 0.05,
    "announcement": 0.05,
    "info": 0.05,
    "information": 0.05,
    "analysis": 0.05,
    "review": 0.05,
    "looking at": 0.1,
    "checking": 0.05,
    "monitor": 0.05,
    "tracking": 0.05,
}

# Classification patterns
CALL_PATTERNS = [
    re.compile(r'\bcall\b', re.IGNORECASE),
    re.compile(r'\balpha\b', re.IGNORECASE),
    re.compile(r'\bgem\b', re.IGNORECASE),
    re.compile(r'\bentry\b', re.IGNORECASE),
    re.compile(r'\bbuy\s+now\b', re.IGNORECASE),
    re.compile(r'\bload\s+up\b', re.IGNORECASE),
    re.compile(r'\bape\s+in\b', re.IGNORECASE),
]

ALERT_PATTERNS = [
    re.compile(r'\balert\b', re.IGNORECASE),
    re.compile(r'\bwhale\b', re.IGNORECASE),
    re.compile(r'\bsmart\s+money\b', re.IGNORECASE),
    re.compile(r'\bvolume\s+spike\b', re.IGNORECASE),
    re.compile(r'\bbreaking\b', re.IGNORECASE),
    re.compile(r'\burgent\b', re.IGNORECASE),
]

SPAM_PATTERNS = [
    re.compile(r'\bgiveaway\b', re.IGNORECASE),
    re.compile(r'\bairdrop\b', re.IGNORECASE),
    re.compile(r'\bfree\s+(?:tokens|coins|crypto)\b', re.IGNORECASE),
    re.compile(r'\bclick\s+(?:here|link)\b', re.IGNORECASE),
    re.compile(r'\bjoin\s+(?:now|us)\b', re.IGNORECASE),
    re.compile(r'\blimited\s+time\b', re.IGNORECASE),
    re.compile(r'\bverify\s+wallet\b', re.IGNORECASE),
    re.compile(r'\bconnect\s+wallet\b', re.IGNORECASE),
    re.compile(r'\bdm\s+(?:me|us)\b', re.IGNORECASE),
]


class SentimentAnalyzer:
    """Analyze sentiment of crypto messages"""
    
    def __init__(self):
        self.bullish_signals = BULLISH_SIGNALS
        self.bearish_signals = BEARISH_SIGNALS
        self.neutral_signals = NEUTRAL_SIGNALS
    
    def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment of text"""
        text_lower = text.lower()
        
        bullish_score = 0.0
        bearish_score = 0.0
        neutral_score = 0.0
        matched_signals = []
        
        # Check bullish signals
        for signal, weight in self.bullish_signals.items():
            if signal in text_lower or signal in text:  # Check both for emojis
                bullish_score += weight
                matched_signals.append(f"+{signal}")
        
        # Check bearish signals
        for signal, weight in self.bearish_signals.items():
            if signal in text_lower or signal in text:
                bearish_score += weight
                matched_signals.append(f"-{signal}")
        
        # Check neutral signals
        for signal, weight in self.neutral_signals.items():
            if signal in text_lower:
                neutral_score += weight
                matched_signals.append(f"~{signal}")
        
        # Calculate final sentiment
        total_score = bullish_score + bearish_score + neutral_score
        
        if total_score == 0:
            return SentimentResult(
                sentiment=Sentiment.NEUTRAL,
                score=0.0,
                confidence=0.3,
                signals=[]
            )
        
        # Normalize score to -1 to 1
        net_score = (bullish_score - bearish_score) / max(bullish_score + bearish_score, 1)
        
        # Determine sentiment
        if net_score > 0.2:
            sentiment = Sentiment.BULLISH
        elif net_score < -0.2:
            sentiment = Sentiment.BEARISH
        else:
            sentiment = Sentiment.NEUTRAL
        
        # Calculate confidence based on signal strength
        confidence = min(total_score / 2.0, 1.0)  # Cap at 1.0
        
        return SentimentResult(
            sentiment=sentiment,
            score=net_score,
            confidence=confidence,
            signals=matched_signals[:10]  # Top 10 signals
        )
    
    def classify_message(self, text: str) -> Tuple[str, float]:
        """Classify message type: call, alert, discussion, spam"""
        text_lower = text.lower()
        
        # Check spam first
        spam_matches = sum(1 for p in SPAM_PATTERNS if p.search(text_lower))
        if spam_matches >= 2:
            return "spam", 0.9
        
        # Check call patterns
        call_matches = sum(1 for p in CALL_PATTERNS if p.search(text_lower))
        if call_matches >= 1:
            return "call", min(0.5 + call_matches * 0.15, 0.95)
        
        # Check alert patterns
        alert_matches = sum(1 for p in ALERT_PATTERNS if p.search(text_lower))
        if alert_matches >= 1:
            return "alert", min(0.5 + alert_matches * 0.15, 0.95)
        
        # Default to discussion
        return "discussion", 0.5


# Singleton instance
sentiment_analyzer = SentimentAnalyzer()
