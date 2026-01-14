"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { 
  TrendingUp, 
  Users, 
  Clock, 
  Wallet,
  ChevronRight,
  Flame,
  AlertCircle
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDistanceToNow } from "date-fns";

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

export function SignalCard({ signal }: SignalCardProps) {
  const isHot = signal.score >= 70;
  const isNew = signal.timing.age_minutes < 5;

  const getSentimentColor = () => {
    if (signal.sentiment.percent_bullish >= 70) return "text-bullish";
    if (signal.sentiment.percent_bullish <= 30) return "text-bearish";
    return "text-neutral";
  };

  const getChainBadgeColor = () => {
    switch (signal.token.chain) {
      case "solana":
        return "bg-purple-500/20 text-purple-400";
      case "base":
        return "bg-blue-500/20 text-blue-400";
      case "bsc":
        return "bg-yellow-500/20 text-yellow-400";
      default:
        return "bg-gray-500/20 text-gray-400";
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "bg-terminal-card border border-terminal-border rounded-xl p-5 hover:border-primary-600/50 transition-all cursor-pointer signal-card-glow",
        isHot && "border-fire/30"
      )}
    >
      <Link href={`/token/${signal.token.chain}/${signal.token.address || signal.token.symbol}`}>
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-primary-600/20 flex items-center justify-center text-lg font-bold">
              {signal.token.symbol?.[0] || "?"}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-lg">
                  ${signal.token.symbol || signal.token.address?.slice(0, 8)}
                </h3>
                <span className={cn("px-2 py-0.5 rounded text-xs font-medium", getChainBadgeColor())}>
                  {signal.token.chain}
                </span>
                {isNew && (
                  <span className="px-2 py-0.5 rounded text-xs font-medium bg-bullish/20 text-bullish">
                    NEW
                  </span>
                )}
              </div>
              <p className="text-sm text-terminal-muted">
                First seen {formatDistanceToNow(new Date(signal.timing.first_seen))} ago
              </p>
            </div>
          </div>

          {/* Score */}
          <div className={cn(
            "flex items-center gap-2 px-3 py-1.5 rounded-lg",
            isHot ? "bg-fire/20" : "bg-terminal-border"
          )}>
            {isHot && <Flame className="w-4 h-4 text-fire fire-icon" />}
            <span className={cn("font-bold", isHot ? "text-fire" : "text-terminal-text")}>
              {signal.score.toFixed(0)}
            </span>
          </div>
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-4 gap-4 mb-4">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-terminal-muted" />
            <span className="text-sm">
              <strong>{signal.metrics.unique_sources}</strong> sources
            </span>
          </div>
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-terminal-muted" />
            <span className="text-sm">
              <strong>{signal.metrics.total_mentions}</strong> mentions
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Wallet className="w-4 h-4 text-whale" />
            <span className="text-sm">
              <strong>{signal.metrics.unique_wallets}</strong> wallets
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-terminal-muted" />
            <span className="text-sm">
              <strong>{signal.metrics.velocity.toFixed(1)}</strong>/min
            </span>
          </div>
        </div>

        {/* Sentiment Bar */}
        <div className="mb-4">
          <div className="flex items-center justify-between text-sm mb-1">
            <span className={getSentimentColor()}>
              {signal.sentiment.percent_bullish.toFixed(0)}% bullish
            </span>
            <span className="text-terminal-muted text-xs">
              {signal.sentiment.bullish}🟢 {signal.sentiment.bearish}🔴 {signal.sentiment.neutral}⚪
            </span>
          </div>
          <div className="h-1.5 bg-terminal-border rounded-full overflow-hidden flex">
            <div 
              className="bg-bullish h-full transition-all"
              style={{ width: `${signal.sentiment.percent_bullish}%` }}
            />
            <div 
              className="bg-bearish h-full transition-all"
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
