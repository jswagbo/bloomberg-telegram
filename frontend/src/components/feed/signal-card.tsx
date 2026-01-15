"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { 
  TrendingUp, 
  TrendingDown,
  Users, 
  Clock, 
  Wallet,
  ChevronRight,
  Flame,
  AlertCircle,
  Copy,
  Check,
  Zap,
  MessageSquare
} from "lucide-react";
import { cn, truncateAddress } from "@/lib/utils";
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

// Circular score indicator
function ScoreRing({ score, size = 56 }: { score: number; size?: number }) {
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 100) * circumference;
  
  const getScoreColor = () => {
    if (score >= 80) return "#f97316"; // fire
    if (score >= 60) return "#22c55e"; // bullish
    if (score >= 40) return "#eab308"; // neutral
    return "#71717a"; // muted
  };

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg className="transform -rotate-90" width={size} height={size}>
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth="4"
          className="text-terminal-border"
        />
        {/* Progress circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={getScoreColor()}
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          style={{ transition: "stroke-dashoffset 0.5s ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-lg font-bold" style={{ color: getScoreColor() }}>
          {score.toFixed(0)}
        </span>
      </div>
    </div>
  );
}

export function SignalCard({ signal }: SignalCardProps) {
  const [tokenInfo, setTokenInfo] = useState<{ symbol: string; name: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const isHot = signal.score >= 70;
  const isNew = signal.timing.age_minutes < 5;
  const isUrgent = signal.metrics.velocity > 3;

  // Fetch token info if symbol is missing (fallback if backend didn't provide it)
  useEffect(() => {
    const hasSymbol = signal.token.symbol || (signal.token as any).name;
    if (!hasSymbol && signal.token.address && signal.token.address.length > 20) {
      fetchTokenInfo(signal.token.chain, signal.token.address).then(setTokenInfo);
    }
  }, [signal.token.symbol, signal.token.address, signal.token.chain]);

  const displaySymbol = signal.token.symbol || tokenInfo?.symbol;
  const displayName = (signal.token as any).name || tokenInfo?.name;

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
      case "solana":
        return "bg-purple-500/20 text-purple-400 border-purple-500/30";
      case "base":
        return "bg-blue-500/20 text-blue-400 border-blue-500/30";
      case "bsc":
        return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
      default:
        return "bg-gray-500/20 text-gray-400 border-gray-500/30";
    }
  };

  const getSentimentIcon = () => {
    if (signal.sentiment.percent_bullish >= 65) {
      return <TrendingUp className="w-4 h-4 text-bullish" />;
    }
    if (signal.sentiment.percent_bullish <= 35) {
      return <TrendingDown className="w-4 h-4 text-bearish" />;
    }
    return null;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "bg-terminal-card border rounded-xl p-5 hover:border-primary-600/50 transition-all cursor-pointer group",
        isHot ? "border-fire/40 shadow-lg shadow-fire/5" : "border-terminal-border",
        isUrgent && "animate-pulse-slow"
      )}
    >
      <Link href={`/token/${signal.token.chain}/${signal.token.address || signal.token.symbol}`}>
        {/* Header - Token Info + Score */}
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            {/* Token Avatar */}
            <div className={cn(
              "w-12 h-12 rounded-xl flex items-center justify-center text-xl font-bold flex-shrink-0",
              isHot ? "bg-fire/20 text-fire" : "bg-primary-600/20 text-primary-400"
            )}>
              {(displaySymbol)?.[0] || "?"}
            </div>
            
            {/* Token Info */}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="font-bold text-lg truncate">
                  {displaySymbol ? `$${displaySymbol}` : truncateAddress(signal.token.address || "")}
                </h3>
                <span className={cn("px-2 py-0.5 rounded text-xs font-medium border", getChainBadgeColor())}>
                  {signal.token.chain}
                </span>
                {isNew && (
                  <span className="px-2 py-0.5 rounded text-xs font-medium bg-bullish/20 text-bullish animate-pulse">
                    NEW
                  </span>
                )}
                {isHot && (
                  <Flame className="w-4 h-4 text-fire fire-icon" />
                )}
              </div>
              <div className="flex items-center gap-2 text-sm text-terminal-muted mt-0.5">
                {displayName && <span className="truncate">{displayName}</span>}
                {displayName && <span>•</span>}
                <Clock className="w-3 h-3" />
                <span>{formatDistanceToNow(new Date(signal.timing.first_seen))} ago</span>
                {signal.token.address && (
                  <button
                    onClick={copyAddress}
                    className="p-1 hover:bg-terminal-border rounded transition-colors ml-1"
                    title={copied ? "Copied!" : "Copy address"}
                  >
                    {copied ? (
                      <Check className="w-3 h-3 text-bullish" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Score Ring */}
          <ScoreRing score={signal.score} />
        </div>

        {/* Quick Stats Row */}
        <div className="flex items-center gap-4 mb-4 py-3 px-4 bg-terminal-bg/50 rounded-lg">
          <div className="flex items-center gap-1.5" title="Sources mentioning">
            <Users className="w-4 h-4 text-primary-400" />
            <span className="font-semibold">{signal.metrics.unique_sources}</span>
            <span className="text-xs text-terminal-muted hidden sm:inline">sources</span>
          </div>
          <div className="w-px h-4 bg-terminal-border" />
          <div className="flex items-center gap-1.5" title="Total mentions">
            <MessageSquare className="w-4 h-4 text-terminal-muted" />
            <span className="font-semibold">{signal.metrics.total_mentions}</span>
            <span className="text-xs text-terminal-muted hidden sm:inline">mentions</span>
          </div>
          <div className="w-px h-4 bg-terminal-border" />
          <div className="flex items-center gap-1.5" title="Wallets mentioned">
            <Wallet className="w-4 h-4 text-whale" />
            <span className="font-semibold">{signal.metrics.unique_wallets}</span>
            <span className="text-xs text-terminal-muted hidden sm:inline">wallets</span>
          </div>
          <div className="w-px h-4 bg-terminal-border" />
          <div className="flex items-center gap-1.5" title="Mentions per minute">
            <Zap className={cn("w-4 h-4", signal.metrics.velocity > 2 ? "text-fire" : "text-terminal-muted")} />
            <span className={cn("font-semibold", signal.metrics.velocity > 2 && "text-fire")}>
              {signal.metrics.velocity.toFixed(1)}
            </span>
            <span className="text-xs text-terminal-muted hidden sm:inline">/min</span>
          </div>
        </div>

        {/* Sentiment Bar - Improved */}
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              {getSentimentIcon()}
              <span className={cn(
                "font-medium",
                signal.sentiment.percent_bullish >= 65 ? "text-bullish" :
                signal.sentiment.percent_bullish <= 35 ? "text-bearish" :
                "text-yellow-400"
              )}>
                {signal.sentiment.percent_bullish.toFixed(0)}% bullish
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs text-terminal-muted">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-bullish" />
                {signal.sentiment.bullish}
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-bearish" />
                {signal.sentiment.bearish}
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-terminal-muted" />
                {signal.sentiment.neutral}
              </span>
            </div>
          </div>
          <div className="h-2 bg-terminal-border rounded-full overflow-hidden flex">
            <div 
              className="bg-bullish h-full transition-all duration-500"
              style={{ width: `${signal.sentiment.percent_bullish}%` }}
            />
            <div 
              className="bg-bearish h-full transition-all duration-500"
              style={{ width: `${100 - signal.sentiment.percent_bullish}%` }}
            />
          </div>
        </div>

        {/* Top Signal */}
        {signal.top_signal.text && (
          <div className="bg-terminal-bg rounded-lg p-3 mb-4">
            <p className="text-sm text-terminal-muted mb-1">
              Top signal from <strong>{signal.top_signal.source}</strong>:
            </p>
            <p className="text-sm line-clamp-2">
              "{signal.top_signal.text}"
            </p>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between pt-3 border-t border-terminal-border">
          <div className="flex gap-2">
            {signal.sources.slice(0, 3).map((source, i) => (
              <span 
                key={i}
                className="px-2 py-1 bg-terminal-border rounded text-xs text-terminal-muted"
              >
                {source}
              </span>
            ))}
            {signal.sources.length > 3 && (
              <span className="px-2 py-1 text-xs text-terminal-muted">
                +{signal.sources.length - 3} more
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 text-primary-400 text-sm font-medium">
            View Details
            <ChevronRight className="w-4 h-4" />
          </div>
        </div>
      </Link>
    </motion.div>
  );
}
