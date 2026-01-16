"""
Chat Summarizer Service

Summarizes what each Telegram chat is saying about specific tokens.
Uses LLM to generate concise summaries per chat per token.
"""

import os
import re
import httpx
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio
import structlog

logger = structlog.get_logger()

# Groq API for LLM summarization
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


@dataclass
class ChatTokenSummary:
    """Summary of what one chat says about a token"""
    chat_name: str
    chat_id: str
    summary: str  # What this chat says about the token
    sentiment: str  # bullish, bearish, neutral
    mention_count: int  # How many times token was mentioned in this chat
    last_mention: Optional[datetime]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "chat_name": self.chat_name,
            "chat_id": self.chat_id,
            "summary": self.summary,
            "sentiment": self.sentiment,
            "mention_count": self.mention_count,
            "last_mention": self.last_mention.isoformat() if self.last_mention else None,
        }


@dataclass
class TokenChatAnalysis:
    """Complete analysis of a token across all chats"""
    address: str
    symbol: str
    name: str
    chain: str
    total_scans: int  # Number of chats that mentioned this token
    total_mentions: int  # Total mention count across all chats
    chat_summaries: List[ChatTokenSummary]
    overall_sentiment: str
    consensus_summary: str  # What the collective chats say
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "symbol": self.symbol,
            "name": self.name,
            "chain": self.chain,
            "total_scans": self.total_scans,
            "total_mentions": self.total_mentions,
            "chat_summaries": [s.to_dict() for s in self.chat_summaries],
            "overall_sentiment": self.overall_sentiment,
            "consensus_summary": self.consensus_summary,
        }


class ChatSummarizer:
    """Summarizes Telegram chat discussions about tokens"""
    
    # Patterns for detecting token mentions
    SCAN_PATTERNS = [
        r'pump\.fun/',
        r'dexscreener\.com/',
        r'birdeye\.so/',
        r'raydium\.io/',
        r'jupiter\.ag/',
        r'^CA[:\s]',
        r'^Contract[:\s]',
    ]
    
    BULLISH_WORDS = [
        'bullish', 'moon', 'pump', 'gem', 'alpha', 'lfg', 'wagmi',
        'buy', 'long', 'accumulate', 'loading', 'fire', 'based',
        'strong', 'solid', 'great', 'love', '🚀', '🔥', '💎',
    ]
    
    BEARISH_WORDS = [
        'bearish', 'dump', 'rug', 'scam', 'sell', 'short', 'ngmi',
        'dead', 'careful', 'risky', 'avoid', 'exit', '📉', '💀',
    ]
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._summary_cache: Dict[str, TokenChatAnalysis] = {}
        self._cache_time: Dict[str, datetime] = {}
        self.cache_duration = timedelta(minutes=5)
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client
    
    def _message_mentions_token(
        self,
        text: str,
        address: str,
        symbol: str,
        name: str = "",
    ) -> bool:
        """Check if message mentions a token"""
        text_lower = text.lower()
        
        # Check address
        if address.lower() in text_lower:
            return True
        
        # Check truncated address
        if len(address) > 12:
            if address[:8].lower() in text_lower or address[-8:].lower() in text_lower:
                return True
        
        # Check $SYMBOL
        if re.search(rf'\${re.escape(symbol)}\b', text, re.IGNORECASE):
            return True
        
        # Check SYMBOL as word
        if len(symbol) >= 2:
            if re.search(rf'\b{re.escape(symbol)}\b', text, re.IGNORECASE):
                return True
        
        # Check name
        if name and len(name) >= 4:
            if re.search(rf'\b{re.escape(name)}\b', text, re.IGNORECASE):
                return True
        
        return False
    
    def _is_scan_message(self, text: str) -> bool:
        """Check if message is a token scan (bot post, link share)"""
        for pattern in self.SCAN_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def _get_sentiment(self, text: str) -> str:
        """Determine sentiment of text"""
        text_lower = text.lower()
        bullish = sum(1 for w in self.BULLISH_WORDS if w in text_lower)
        bearish = sum(1 for w in self.BEARISH_WORDS if w in text_lower)
        
        if bullish > bearish:
            return "bullish"
        elif bearish > bullish:
            return "bearish"
        return "neutral"
    
    def _group_messages_by_chat(
        self,
        messages: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group messages by chat source"""
        grouped = defaultdict(list)
        for msg in messages:
            source_name = msg.get("source_name", "Unknown")
            grouped[source_name].append(msg)
        return dict(grouped)
    
    async def _summarize_with_llm(
        self,
        messages: List[str],
        token_symbol: str,
        chat_name: str,
    ) -> str:
        """Use LLM to summarize what a chat says about a token"""
        if not GROQ_API_KEY:
            # Fallback without LLM
            return self._simple_summarize(messages, token_symbol)
        
        try:
            client = await self._get_client()
            
            # Combine messages
            combined = "\n".join(messages[:20])  # Limit to 20 messages
            
            prompt = f"""Summarize what this Telegram chat "{chat_name}" is saying about the token ${token_symbol}.
Be concise (1-2 sentences). Focus on:
- Overall sentiment (bullish/bearish/neutral)
- Key opinions or insights
- Any warnings or alpha

Messages:
{combined}

Summary:"""
            
            response = await client.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 100,
                    "temperature": 0.3,
                },
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            
        except Exception as e:
            logger.warning("llm_summarize_failed", error=str(e))
        
        return self._simple_summarize(messages, token_symbol)
    
    def _simple_summarize(self, messages: List[str], token_symbol: str) -> str:
        """Simple rule-based summary without LLM"""
        if not messages:
            return f"Token ${token_symbol} was scanned but no discussion found."
        
        # Count sentiment
        bullish = 0
        bearish = 0
        
        for msg in messages:
            sentiment = self._get_sentiment(msg)
            if sentiment == "bullish":
                bullish += 1
            elif sentiment == "bearish":
                bearish += 1
        
        total = len(messages)
        
        if bullish > bearish and bullish > total * 0.3:
            return f"Generally bullish on ${token_symbol}. {bullish}/{total} messages positive."
        elif bearish > bullish and bearish > total * 0.3:
            return f"Cautious about ${token_symbol}. {bearish}/{total} messages show concern."
        else:
            return f"Mixed opinions on ${token_symbol}. {total} messages discussing."
    
    async def analyze_token_across_chats(
        self,
        messages: List[Dict[str, Any]],
        token_address: str,
        token_symbol: str,
        token_name: str,
        chain: str,
    ) -> TokenChatAnalysis:
        """
        Analyze what all chats are saying about a specific token.
        
        Returns:
            TokenChatAnalysis with per-chat summaries and overall consensus
        """
        # Check cache
        cache_key = f"{chain}:{token_address}"
        if cache_key in self._summary_cache:
            if datetime.utcnow() - self._cache_time.get(cache_key, datetime.min) < self.cache_duration:
                return self._summary_cache[cache_key]
        
        # Group messages by chat
        grouped = self._group_messages_by_chat(messages)
        
        chat_summaries = []
        total_mentions = 0
        overall_bullish = 0
        overall_bearish = 0
        
        for chat_name, chat_messages in grouped.items():
            # Find messages mentioning this token
            token_messages = []
            discussion_messages = []  # Non-scan messages
            last_mention = None
            
            for msg in chat_messages:
                text = msg.get("text", "")
                if not text:
                    continue
                
                if self._message_mentions_token(text, token_address, token_symbol, token_name):
                    token_messages.append(msg)
                    total_mentions += 1
                    
                    # Track last mention time
                    ts_str = msg.get("timestamp")
                    if ts_str:
                        try:
                            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                            if ts.tzinfo:
                                ts = ts.replace(tzinfo=None)
                            if last_mention is None or ts > last_mention:
                                last_mention = ts
                        except:
                            pass
                    
                    # Separate scans from discussions
                    if not self._is_scan_message(text):
                        discussion_messages.append(text)
            
            # Skip if no mentions in this chat
            if not token_messages:
                continue
            
            # Generate summary for this chat
            if discussion_messages:
                summary = await self._summarize_with_llm(
                    discussion_messages,
                    token_symbol,
                    chat_name,
                )
            else:
                summary = f"Token ${token_symbol} was scanned but no discussion yet."
            
            # Determine sentiment
            all_text = " ".join(discussion_messages)
            sentiment = self._get_sentiment(all_text) if discussion_messages else "neutral"
            
            if sentiment == "bullish":
                overall_bullish += 1
            elif sentiment == "bearish":
                overall_bearish += 1
            
            chat_summaries.append(ChatTokenSummary(
                chat_name=chat_name,
                chat_id=chat_messages[0].get("source_id", "") if chat_messages else "",
                summary=summary,
                sentiment=sentiment,
                mention_count=len(token_messages),
                last_mention=last_mention,
            ))
        
        # Sort by mention count
        chat_summaries.sort(key=lambda x: x.mention_count, reverse=True)
        
        # Determine overall sentiment
        if overall_bullish > overall_bearish:
            overall_sentiment = "bullish"
        elif overall_bearish > overall_bullish:
            overall_sentiment = "bearish"
        else:
            overall_sentiment = "neutral"
        
        # Generate consensus summary
        total_scans = len(chat_summaries)
        if total_scans == 0:
            consensus = f"No chats discussing ${token_symbol}."
        elif total_scans == 1:
            consensus = chat_summaries[0].summary
        else:
            consensus = f"Discussed in {total_scans} chats. "
            if overall_sentiment == "bullish":
                consensus += f"Overall bullish sentiment ({overall_bullish}/{total_scans} chats positive)."
            elif overall_sentiment == "bearish":
                consensus += f"Overall cautious ({overall_bearish}/{total_scans} chats concerned)."
            else:
                consensus += "Mixed opinions across chats."
        
        analysis = TokenChatAnalysis(
            address=token_address,
            symbol=token_symbol,
            name=token_name,
            chain=chain,
            total_scans=total_scans,
            total_mentions=total_mentions,
            chat_summaries=chat_summaries,
            overall_sentiment=overall_sentiment,
            consensus_summary=consensus,
        )
        
        # Cache
        self._summary_cache[cache_key] = analysis
        self._cache_time[cache_key] = datetime.utcnow()
        
        return analysis
    
    async def analyze_tokens_batch(
        self,
        messages: List[Dict[str, Any]],
        tokens: List[Dict[str, Any]],  # List of {address, symbol, name, chain}
    ) -> Dict[str, TokenChatAnalysis]:
        """
        Analyze multiple tokens across all chats.
        
        Returns:
            Dict mapping token address to TokenChatAnalysis
        """
        results = {}
        
        for token in tokens:
            address = token.get("address", "")
            symbol = token.get("symbol", "")
            name = token.get("name", "")
            chain = token.get("chain", "solana")
            
            if not address:
                continue
            
            analysis = await self.analyze_token_across_chats(
                messages=messages,
                token_address=address,
                token_symbol=symbol,
                token_name=name,
                chain=chain,
            )
            
            results[address] = analysis
        
        return results


# Singleton
chat_summarizer = ChatSummarizer()
