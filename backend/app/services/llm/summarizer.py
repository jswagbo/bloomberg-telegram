"""LLM-powered summarization service using Groq"""

import os
from typing import List, Dict, Optional
import structlog
from groq import Groq, AsyncGroq

logger = structlog.get_logger()

# Cache for summaries to avoid repeated API calls
_summary_cache: Dict[str, Dict] = {}


class LLMSummarizer:
    """Service for generating AI summaries of token chatter"""
    
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.client = None
        self.async_client = None
        self.model = "llama-3.1-8b-instant"  # Fast, free model
        
        if self.api_key:
            self.client = Groq(api_key=self.api_key)
            self.async_client = AsyncGroq(api_key=self.api_key)
            logger.info("llm_summarizer_initialized", model=self.model)
        else:
            logger.warning("llm_summarizer_disabled", reason="GROQ_API_KEY not set")
    
    def is_available(self) -> bool:
        """Check if LLM service is available"""
        return self.client is not None
    
    async def generate_token_summary(
        self,
        token_symbol: str,
        token_address: str,
        chain: str,
        messages: List[Dict],
        sentiment_data: Dict,
        price_data: Dict,
    ) -> Dict:
        """
        Generate a comprehensive AI summary of all chatter about a token.
        
        Args:
            token_symbol: Token symbol (e.g., "PEPE")
            token_address: Contract address
            chain: Blockchain name
            messages: List of message dicts with text, source, sentiment
            sentiment_data: Aggregated sentiment analysis
            price_data: Price info from DexScreener
        
        Returns:
            Dict with summary, key_points, recommendation, confidence
        """
        # Check cache first
        cache_key = f"{chain}:{token_address}"
        if cache_key in _summary_cache:
            cached = _summary_cache[cache_key]
            # Cache valid for 5 minutes
            if cached.get("timestamp", 0) > (import_time() - 300):
                return cached["data"]
        
        if not self.is_available():
            return self._generate_fallback_summary(
                token_symbol, messages, sentiment_data, price_data
            )
        
        try:
            # Prepare message context (limit to avoid token limits)
            message_texts = []
            for msg in messages[:50]:  # Max 50 messages
                text = msg.get("original_text", msg.get("text", ""))[:300]
                source = msg.get("source_name", "Unknown")
                sentiment = msg.get("sentiment", "neutral")
                message_texts.append(f"[{source}] ({sentiment}): {text}")
            
            messages_context = "\n".join(message_texts)
            
            # Build prompt
            prompt = self._build_summary_prompt(
                token_symbol or token_address[:8],
                chain,
                messages_context,
                sentiment_data,
                price_data,
                len(messages)
            )
            
            # Call Groq API
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a crypto market analyst. Analyze Telegram chatter about tokens and provide concise, actionable insights. 
Be direct and objective. Highlight both opportunities and risks. 
Format your response as JSON with these fields:
- summary: 2-3 sentence overview
- key_bullish_points: array of bullish arguments (max 3)
- key_bearish_points: array of bearish/risk points (max 3)  
- community_consensus: what the majority thinks (bullish/bearish/mixed)
- notable_mentions: any whale activity, insider info, or significant calls
- risk_assessment: low/medium/high with brief reason
- alpha_quality: rating of the quality of alpha being shared (low/medium/high)
- recommendation: brief actionable insight"""
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800,
            )
            
            # Parse response
            content = response.choices[0].message.content
            result = self._parse_llm_response(content)
            result["generated_by"] = "llm"
            result["model"] = self.model
            
            # Cache result
            _summary_cache[cache_key] = {
                "data": result,
                "timestamp": import_time()
            }
            
            logger.info("llm_summary_generated", 
                       token=token_symbol, 
                       messages_analyzed=len(messages))
            
            return result
            
        except Exception as e:
            logger.error("llm_summary_error", error=str(e), token=token_symbol)
            return self._generate_fallback_summary(
                token_symbol, messages, sentiment_data, price_data
            )
    
    def _build_summary_prompt(
        self,
        token_symbol: str,
        chain: str,
        messages_context: str,
        sentiment_data: Dict,
        price_data: Dict,
        total_messages: int
    ) -> str:
        """Build the prompt for the LLM"""
        
        price_info = ""
        if price_data:
            price_info = f"""
Price Data:
- Current Price: ${price_data.get('price_usd', 'N/A')}
- 24h Change: {price_data.get('price_change_24h', 'N/A')}%
- Market Cap: ${price_data.get('market_cap', 'N/A')}
- Liquidity: ${price_data.get('liquidity_usd', 'N/A')}
"""
        
        sentiment_info = f"""
Sentiment Analysis:
- Overall: {sentiment_data.get('overall_sentiment', 'neutral')}
- Bullish: {sentiment_data.get('bullish_percent', 50):.0f}%
- Risk Score: {sentiment_data.get('risk_score', 50):.0f}/100
- Quality Score: {sentiment_data.get('quality_score', 50):.0f}/100
"""
        
        return f"""Analyze this Telegram chatter about ${token_symbol} on {chain}.

Total messages collected: {total_messages}
{price_info}
{sentiment_info}

Recent messages from crypto Telegram groups:
{messages_context}

Based on ALL the above information, provide a comprehensive analysis in JSON format.
Focus on:
1. What is the community saying about this token?
2. Are there any red flags or warning signs?
3. What's the quality of the alpha being shared?
4. Any notable whale activity or insider mentions?
5. Overall risk assessment

Respond ONLY with valid JSON."""
    
    def _parse_llm_response(self, content: str) -> Dict:
        """Parse the LLM response into structured data"""
        import json
        
        # Try to extract JSON from response
        try:
            # Handle potential markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            return json.loads(content.strip())
        except json.JSONDecodeError:
            # If JSON parsing fails, create structured response from text
            return {
                "summary": content[:500] if content else "Unable to generate summary.",
                "key_bullish_points": [],
                "key_bearish_points": [],
                "community_consensus": "unknown",
                "notable_mentions": None,
                "risk_assessment": "medium",
                "alpha_quality": "medium", 
                "recommendation": "DYOR - Unable to fully analyze."
            }
    
    def _generate_fallback_summary(
        self,
        token_symbol: str,
        messages: List[Dict],
        sentiment_data: Dict,
        price_data: Dict,
    ) -> Dict:
        """Generate a basic summary without LLM when API is unavailable"""
        
        bullish_pct = sentiment_data.get("bullish_percent", 50)
        risk_score = sentiment_data.get("risk_score", 50)
        quality_score = sentiment_data.get("quality_score", 50)
        
        # Determine consensus
        if bullish_pct > 65:
            consensus = "bullish"
        elif bullish_pct < 35:
            consensus = "bearish"
        else:
            consensus = "mixed"
        
        # Determine risk level
        if risk_score > 60:
            risk_level = "high"
        elif risk_score > 30:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        # Determine quality
        if quality_score > 70:
            alpha_quality = "high"
        elif quality_score > 40:
            alpha_quality = "medium"
        else:
            alpha_quality = "low"
        
        # Build summary
        summary_parts = []
        symbol = token_symbol or "This token"
        
        summary_parts.append(f"{symbol} has {len(messages)} mentions across Telegram.")
        
        if consensus == "bullish":
            summary_parts.append(f"Community sentiment is {bullish_pct:.0f}% bullish.")
        elif consensus == "bearish":
            summary_parts.append(f"Community sentiment is bearish ({100-bullish_pct:.0f}% negative).")
        else:
            summary_parts.append("Community sentiment is mixed.")
        
        if risk_level == "high":
            summary_parts.append("Multiple risk signals detected - proceed with caution.")
        elif risk_level == "low":
            summary_parts.append("Risk signals are minimal.")
        
        return {
            "summary": " ".join(summary_parts),
            "key_bullish_points": sentiment_data.get("quality_factors", [])[:3],
            "key_bearish_points": sentiment_data.get("risk_factors", [])[:3],
            "community_consensus": consensus,
            "notable_mentions": None,
            "risk_assessment": risk_level,
            "alpha_quality": alpha_quality,
            "recommendation": f"{'Approach with caution' if risk_level == 'high' else 'DYOR'} - {alpha_quality} quality alpha.",
            "generated_by": "fallback",
            "model": None
        }
    
    def clear_cache(self, token_address: Optional[str] = None, chain: Optional[str] = None):
        """Clear the summary cache"""
        global _summary_cache
        if token_address and chain:
            cache_key = f"{chain}:{token_address}"
            _summary_cache.pop(cache_key, None)
        else:
            _summary_cache = {}


def import_time():
    """Get current timestamp"""
    import time
    return time.time()


# Singleton instance
llm_summarizer = LLMSummarizer()
