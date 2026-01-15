"use client";

import { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { 
  TrendingUp, 
  TrendingDown,
  Users, 
  Clock, 
  ChevronRight,
  Flame,
  Copy,
  Check,
  MessageSquare,
  Quote,
  Sparkles,
  ExternalLink
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDistanceToNow } from "date-fns";
import { fetchTokenInfo } from "@/components/token-display";

interface SignalCardProps {
  signal: {
    cluster_id: string;
    token: {
      address: string;
      symbol: string;
      chain: string;
    };
    score: number;
    metrics: {
      unique_sources: number;
      total_mentions: number;
      unique_wallets: number;
      velocity: number;
    };
    sentiment: {
      bullish: number;
      bearish: number;
      neutral: number;
      overall: string;
      percent_bullish: number;
    };
    timing: {
      first_seen: string;
      age_minutes: number;
    };
    top_signal: {
      text: string;
      source: string;
    };
    sources: string[];
    wallets: string[];
  };
}

// Extract key themes/narratives from signal text
function extractThemes(text: string): string[] {
  const themes: string[] = [];
  const lowerText = text.toLowerCase();
  
  // Price/target mentions
  if (/\d+x|\d+X|moon|pump|send|rip/i.test(text)) themes.push("Price Target");
  if (/dip|buy|entry|load|accumulate/i.test(text)) themes.push("Entry Signal");
  if (/sell|exit|dump|rug|scam/i.test(text)) themes.push("Warning");
  
  // Catalyst mentions
  if (/launch|listing|cex|binance|coinbase/i.test(text)) themes.push("Listing");
  if (/airdrop|drop/i.test(text)) themes.push("Airdrop");
  if (/partnership|collab/i.test(text)) themes.push("Partnership");
  if (/update|upgrade|v2|release/i.test(text)) themes.push("Development");
  
  // Social proof
  if (/whale|big.*buy|large.*buy/i.test(text)) themes.push("Whale Activity");
  if (/influencer|kol|ct|crypto twitter/i.test(text)) themes.push("Influencer");
  if (/dev|team|founder/i.test(text)) themes.push("Team Activity");
  
  // Unique themes only
  return Array.from(new Set(themes)).slice(0, 3);
}

// Check if text looks like a scan/bot message rather than real discussion
function isScanMessage(text: string): boolean {
  if (!text || text.length < 20) return true;
  
  const lowerText = text.toLowerCase();
  
  // Obvious scan/bot patterns
  const scanPatterns = [
    "pump.fun", "dexscreener.com", "birdeye.so", "raydium.io", "jupiter.ag",
    "ca:", "contract:", "mint:", "token address", "buy now", "presale",
    "🔥 new", "🚀 launched", "💎 gem alert",
  ];
  if (scanPatterns.some(p => lowerText.includes(p))) return true;
  
  // URL-heavy messages
  if ((text.match(/https?:\/\//g) || []).length > 0) return true;
  if (text.split("/").length > 3) return true;
  
  // Messages that are mostly contract addresses
  const addressPattern = /[A-Za-z0-9]{32,}/g;
  const addressMatches = text.match(addressPattern) || [];
  if (addressMatches.length > 0 && addressMatches.join("").length > text.length * 0.3) return true;
  
  return false;
}

// Clean up signal text for display
function cleanSignalText(text: string): string {
  if (!text) return "";
  
  // If it looks like a scan message, don't display it
  if (isScanMessage(text)) return "";
  
  // Remove URLs
  let cleaned = text.replace(/https?:\/\/[^\s]+/g, "").trim();
  // Remove contract addresses
  cleaned = cleaned.replace(/[A-Za-z0-9]{32,}/g, "").trim();
  // Remove excessive whitespace
  cleaned = cleaned.replace(/\s+/g, " ");
  // Remove leftover URL fragments
  cleaned = cleaned.replace(/\s*\/\s*\//g, " ").trim();
  
  // Limit length
  if (cleaned.length > 280) {
    cleaned = cleaned.substring(0, 280) + "...";
  }
  
  // Return empty if too short after cleaning (likely wasn't real content)
  return cleaned.length >= 20 ? cleaned : "";
}

export function SignalCard({ signal }: SignalCardProps) {
  const [tokenInfo, setTokenInfo] = useState<{ symbol: string; name: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const isHot = signal.score >= 70;
  const isNew = signal.timing.age_minutes < 5;

  // Fetch token info if symbol is missing
  useEffect(() => {
    const hasSymbol = signal.token.symbol || (signal.token as any).name;
    if (!hasSymbol && signal.token.address && signal.token.address.length > 20) {
      fetchTokenInfo(signal.token.chain, signal.token.address).then(setTokenInfo);
    }
  }, [signal.token.symbol, signal.token.address, signal.token.chain]);

  // Helper to check if a string looks like an address
  const looksLikeAddress = (str: string | null | undefined): boolean => {
    if (!str) return true;
    if (str.startsWith("0x")) return true;
    if (str.includes("...")) return true;
    if (str.length > 15) return true;
    if (str.length > 10 && /^[a-zA-Z0-9]+$/.test(str) && /[a-z]/.test(str) && /[A-Z]/.test(str) && /\d/.test(str)) return true;
    if (str.toLowerCase().endsWith("pump")) return true;
    return false;
  };

  const rawSymbol = signal.token.symbol || tokenInfo?.symbol;
  const displaySymbol = !looksLikeAddress(rawSymbol) ? rawSymbol : null;
  const rawName = (signal.token as any).name || tokenInfo?.name;
  const displayName = !looksLikeAddress(rawName) ? rawName : null;

  // Don't render if no valid name
  if (!displaySymbol && !displayName) {
    return null;
  }

  // Extract themes from the top signal text
  const themes = useMemo(() => {
    return extractThemes(signal.top_signal?.text || "");
  }, [signal.top_signal?.text]);

  // Clean the signal text for display
  const cleanedSignalText = useMemo(() => {
    return cleanSignalText(signal.top_signal?.text || "");
  }, [signal.top_signal?.text]);

  const copyAddress = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (signal.token.address) {
      navigator.clipboard.writeText(signal.token.address);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const getChainBadgeColor = () => {
    switch (signal.token.chain) {
      case "solana": return "bg-purple-500/20 text-purple-400";
      case "base": return "bg-blue-500/20 text-blue-400";
      case "bsc": return "bg-yellow-500/20 text-yellow-400";
      default: return "bg-gray-500/20 text-gray-400";
    }
  };

  const getSentimentLabel = () => {
    if (signal.sentiment.percent_bullish >= 70) return { text: "Very Bullish", color: "text-bullish" };
    if (signal.sentiment.percent_bullish >= 55) return { text: "Bullish", color: "text-bullish" };
    if (signal.sentiment.percent_bullish <= 30) return { text: "Bearish", color: "text-bearish" };
    if (signal.sentiment.percent_bullish <= 45) return { text: "Cautious", color: "text-yellow-400" };
    return { text: "Mixed", color: "text-terminal-muted" };
  };

  const sentiment = getSentimentLabel();

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "bg-terminal-card border rounded-xl overflow-hidden hover:border-primary-600/50 transition-all cursor-pointer group",
        isHot ? "border-fire/40" : "border-terminal-border"
      )}
    >
      <Link href={`/token/${signal.token.chain}/${signal.token.address || signal.token.symbol}`}>
        {/* Header Bar */}
        <div className={cn(
          "px-5 py-3 flex items-center justify-between",
          isHot ? "bg-fire/10" : "bg-terminal-bg/50"
        )}>
          <div className="flex items-center gap-3">
            {/* Token Badge */}
            <div className={cn(
              "w-10 h-10 rounded-lg flex items-center justify-center text-lg font-bold",
              isHot ? "bg-fire/20 text-fire" : "bg-primary-600/20 text-primary-400"
            )}>
              {(displaySymbol || displayName)?.[0] || "?"}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-lg">${displaySymbol || displayName}</h3>
                {isHot && <Flame className="w-4 h-4 text-fire" />}
                {isNew && (
                  <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-bullish/20 text-bullish">
                    NEW
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 text-xs text-terminal-muted">
                <span className={cn("px-1.5 py-0.5 rounded", getChainBadgeColor())}>
                  {signal.token.chain}
                </span>
                <span>•</span>
                <Clock className="w-3 h-3" />
                <span>{formatDistanceToNow(new Date(signal.timing.first_seen))} ago</span>
              </div>
            </div>
          </div>
          
          {/* Sentiment Badge */}
          <div className="text-right">
            <div className={cn("font-semibold", sentiment.color)}>
              {sentiment.text}
            </div>
            <div className="text-xs text-terminal-muted">
              {signal.metrics.unique_sources} sources • {signal.metrics.total_mentions} mentions
            </div>
          </div>
        </div>

        {/* Main Content - The Discussion */}
        <div className="p-5">
          {/* Themes/Tags */}
          {themes.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {themes.map((theme, i) => (
                <span 
                  key={i}
                  className={cn(
                    "px-2 py-1 rounded-full text-xs font-medium",
                    theme === "Warning" ? "bg-bearish/20 text-bearish" :
                    theme === "Whale Activity" ? "bg-whale/20 text-whale" :
                    theme === "Price Target" ? "bg-bullish/20 text-bullish" :
                    "bg-primary-600/20 text-primary-400"
                  )}
                >
                  {theme}
                </span>
              ))}
            </div>
          )}

          {/* The Actual Discussion Content */}
          <div className="mb-4">
            <div className="flex items-start gap-3">
              <Quote className="w-5 h-5 text-terminal-muted flex-shrink-0 mt-0.5" />
              <div>
                {cleanedSignalText ? (
                  <>
                    <p className="text-terminal-text leading-relaxed">
                      {cleanedSignalText}
                    </p>
                    <p className="text-xs text-terminal-muted mt-2">
                      — {signal.top_signal?.source || signal.sources[0] || "Community"}
                    </p>
                  </>
                ) : (
                  <p className="text-terminal-muted italic">
                    Being discussed across {signal.sources.length} source{signal.sources.length !== 1 ? 's' : ''} — click for full context
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Sentiment Bar - Compact */}
          <div className="flex items-center gap-3 mb-4">
            <div className="flex-1 h-1.5 bg-terminal-border rounded-full overflow-hidden flex">
              <div 
                className="bg-bullish h-full"
                style={{ width: `${signal.sentiment.percent_bullish}%` }}
              />
              <div 
                className="bg-bearish h-full"
                style={{ width: `${100 - signal.sentiment.percent_bullish}%` }}
              />
            </div>
            <span className="text-xs text-terminal-muted whitespace-nowrap">
              {signal.sentiment.percent_bullish.toFixed(0)}% bullish
            </span>
          </div>

          {/* Sources */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-terminal-muted" />
              <span className="text-xs text-terminal-muted">Discussed in:</span>
              <div className="flex gap-1">
                {signal.sources.slice(0, 2).map((source, i) => (
                  <span 
                    key={i}
                    className="px-2 py-0.5 bg-terminal-border rounded text-xs text-terminal-text"
                  >
                    {source}
                  </span>
                ))}
                {signal.sources.length > 2 && (
                  <span className="px-2 py-0.5 text-xs text-terminal-muted">
                    +{signal.sources.length - 2}
                  </span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-1 text-primary-400 text-sm font-medium group-hover:gap-2 transition-all">
              <Sparkles className="w-4 h-4" />
              <span>Full Analysis</span>
              <ChevronRight className="w-4 h-4" />
            </div>
          </div>
        </div>

        {/* Copy Address Footer */}
        {signal.token.address && (
          <div className="px-5 py-2 bg-terminal-bg/30 border-t border-terminal-border flex items-center justify-between">
            <button
              onClick={copyAddress}
              className="flex items-center gap-2 text-xs text-terminal-muted hover:text-terminal-text transition-colors"
            >
              {copied ? (
                <>
                  <Check className="w-3 h-3 text-bullish" />
                  Copied!
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" />
                  Copy Contract
                </>
              )}
            </button>
            <a 
              href={`https://dexscreener.com/${signal.token.chain}/${signal.token.address}`}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="flex items-center gap-1 text-xs text-terminal-muted hover:text-primary-400 transition-colors"
            >
              DexScreener
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        )}
      </Link>
    </motion.div>
  );
}
