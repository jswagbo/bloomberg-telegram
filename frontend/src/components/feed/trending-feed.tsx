"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { motion } from "framer-motion";
import { 
  TrendingUp, 
  TrendingDown,
  MessageSquare,
  RefreshCw,
  ExternalLink,
  Copy,
  Check,
  Users,
  Clock,
  Flame,
  Search,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDistanceToNow } from "date-fns";
import api from "@/lib/api";

interface TrendingToken {
  address: string;
  symbol: string;
  name: string;
  chain: string;
  price_usd: number | null;
  price_change_24h: number | null;
  volume_24h: number | null;
  market_cap: number | null;
  dexscreener_url: string;
  image_url: string | null;
  total_mentions: number;
  human_discussions: number;
  sources: string[];
  sentiment: {
    bullish: number;
    bearish: number;
    neutral: number;
  };
  top_messages: Array<{
    text: string;
    source_name: string;
    timestamp: string | null;
    sentiment: string;
  }>;
}

function TrendingCard({ token }: { token: TrendingToken }) {
  const [copied, setCopied] = useState(false);

  const copyAddress = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    navigator.clipboard.writeText(token.address);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const totalSentiment = token.sentiment.bullish + token.sentiment.bearish + token.sentiment.neutral;
  const bullishPercent = totalSentiment > 0 ? (token.sentiment.bullish / totalSentiment) * 100 : 50;
  
  const hasMentions = token.total_mentions > 0;
  const hasDiscussion = token.human_discussions > 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "bg-terminal-card border rounded-xl overflow-hidden hover:border-primary-600/50 transition-all",
        hasDiscussion ? "border-primary-600/30" : "border-terminal-border"
      )}
    >
      <Link href={`/token/${token.chain}/${token.address}`}>
        {/* Header */}
        <div className={cn(
          "px-4 py-3 flex items-center justify-between",
          hasDiscussion ? "bg-primary-600/10" : "bg-terminal-bg/50"
        )}>
          <div className="flex items-center gap-3">
            {/* Token Icon */}
            <div className={cn(
              "w-10 h-10 rounded-lg flex items-center justify-center text-lg font-bold",
              hasDiscussion ? "bg-primary-600/20 text-primary-400" : "bg-terminal-border text-terminal-muted"
            )}>
              {token.image_url ? (
                <img src={token.image_url} alt={token.symbol} className="w-full h-full rounded-lg object-cover" />
              ) : (
                token.symbol[0]
              )}
            </div>
            
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold">${token.symbol}</h3>
                <span className={cn(
                  "text-xs px-1.5 py-0.5 rounded",
                  token.chain === "solana" ? "bg-purple-500/20 text-purple-400" :
                  token.chain === "base" ? "bg-blue-500/20 text-blue-400" :
                  "bg-yellow-500/20 text-yellow-400"
                )}>
                  {token.chain}
                </span>
              </div>
              <p className="text-xs text-terminal-muted truncate max-w-[150px]">{token.name}</p>
            </div>
          </div>

          {/* Price */}
          <div className="text-right">
            {token.price_usd && (
              <p className="font-mono text-sm">
                ${token.price_usd < 0.01 ? token.price_usd.toExponential(2) : token.price_usd.toFixed(4)}
              </p>
            )}
            {token.price_change_24h !== null && (
              <p className={cn(
                "text-xs flex items-center gap-1 justify-end",
                token.price_change_24h >= 0 ? "text-bullish" : "text-bearish"
              )}>
                {token.price_change_24h >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                {Math.abs(token.price_change_24h).toFixed(1)}%
              </p>
            )}
          </div>
        </div>

        {/* Mentions Section */}
        <div className="p-4 border-t border-terminal-border">
          {/* Mention Stats */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1.5">
                <MessageSquare className="w-4 h-4 text-terminal-muted" />
                <span className={cn(
                  "text-sm font-medium",
                  hasDiscussion ? "text-primary-400" : "text-terminal-muted"
                )}>
                  {token.human_discussions} discussions
                </span>
              </div>
              {token.sources.length > 0 && (
                <div className="flex items-center gap-1.5">
                  <Users className="w-4 h-4 text-terminal-muted" />
                  <span className="text-sm text-terminal-muted">
                    {token.sources.length} sources
                  </span>
                </div>
              )}
            </div>
            
            {totalSentiment > 0 && (
              <span className={cn(
                "text-xs px-2 py-0.5 rounded",
                bullishPercent >= 60 ? "bg-bullish/20 text-bullish" :
                bullishPercent <= 40 ? "bg-bearish/20 text-bearish" :
                "bg-terminal-border text-terminal-muted"
              )}>
                {bullishPercent >= 60 ? "Bullish" : bullishPercent <= 40 ? "Bearish" : "Mixed"}
              </span>
            )}
          </div>

          {/* Top Discussion */}
          {hasDiscussion && token.top_messages.length > 0 ? (
            <div className="space-y-2">
              {token.top_messages.slice(0, 1).map((msg, i) => (
                <div key={i} className="bg-terminal-bg/50 rounded-lg p-3">
                  <p className="text-sm text-terminal-text leading-relaxed line-clamp-2">
                    "{msg.text}"
                  </p>
                  <p className="text-xs text-terminal-muted mt-1">
                    — {msg.source_name}
                    {msg.timestamp && ` • ${formatDistanceToNow(new Date(msg.timestamp))} ago`}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-terminal-bg/30 rounded-lg p-3 text-center">
              <p className="text-sm text-terminal-muted italic">
                No discussions yet
              </p>
              <p className="text-xs text-terminal-muted mt-1">
                Click "Refresh" to scan for mentions
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 bg-terminal-bg/30 border-t border-terminal-border flex items-center justify-between">
          <button
            onClick={copyAddress}
            className="flex items-center gap-1.5 text-xs text-terminal-muted hover:text-terminal-text transition-colors"
          >
            {copied ? (
              <>
                <Check className="w-3 h-3 text-bullish" />
                Copied!
              </>
            ) : (
              <>
                <Copy className="w-3 h-3" />
                Copy CA
              </>
            )}
          </button>
          
          <a
            href={token.dexscreener_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="flex items-center gap-1 text-xs text-terminal-muted hover:text-primary-400 transition-colors"
          >
            DexScreener
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </Link>
    </motion.div>
  );
}

export function TrendingFeed() {
  const queryClient = useQueryClient();
  const [chainFilter, setChainFilter] = useState<string | null>(null);

  // Fetch trending feed
  const { data, isLoading, error } = useQuery({
    queryKey: ["trending-feed", chainFilter],
    queryFn: () => api.getTrendingFeed({ limit: 50, chain: chainFilter || undefined }),
    staleTime: 60000, // 1 minute
    refetchInterval: 60000,
  });

  // Refresh messages mutation
  const refreshMutation = useMutation({
    mutationFn: api.refreshTrendingMessages,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trending-feed"] });
    },
  });

  const tokens: TrendingToken[] = data?.tokens || [];

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Chain Filter */}
        <div className="flex items-center gap-2">
          {["all", "solana", "base", "bsc"].map((chain) => (
            <button
              key={chain}
              onClick={() => setChainFilter(chain === "all" ? null : chain)}
              className={cn(
                "px-3 py-1.5 text-sm rounded-lg transition-colors",
                (chain === "all" && !chainFilter) || chainFilter === chain
                  ? "bg-primary-600 text-white"
                  : "bg-terminal-card text-terminal-muted hover:text-terminal-text"
              )}
            >
              {chain === "all" ? "All Chains" : chain.charAt(0).toUpperCase() + chain.slice(1)}
            </button>
          ))}
        </div>

        {/* Refresh Button */}
        <button
          onClick={() => refreshMutation.mutate()}
          disabled={refreshMutation.isPending}
          className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors",
            "bg-primary-600 text-white hover:bg-primary-500",
            refreshMutation.isPending && "opacity-50 cursor-not-allowed"
          )}
        >
          <RefreshCw className={cn("w-4 h-4", refreshMutation.isPending && "animate-spin")} />
          {refreshMutation.isPending ? "Scanning..." : "Refresh Mentions"}
        </button>
      </div>

      {/* Stats */}
      {data && (
        <div className="flex items-center gap-4 text-sm text-terminal-muted">
          <span>{data.total_tokens} trending tokens</span>
          <span>•</span>
          <span>{data.messages_scanned} messages scanned</span>
          <span>•</span>
          <span>Updated {formatDistanceToNow(new Date(data.last_updated))} ago</span>
        </div>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="bg-terminal-card border border-terminal-border rounded-xl p-4 animate-pulse">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-terminal-border rounded-lg" />
                <div className="space-y-2">
                  <div className="w-20 h-4 bg-terminal-border rounded" />
                  <div className="w-16 h-3 bg-terminal-border rounded" />
                </div>
              </div>
              <div className="h-20 bg-terminal-bg/50 rounded-lg" />
            </div>
          ))}
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="text-center py-12">
          <p className="text-bearish">Failed to load trending tokens</p>
          <p className="text-terminal-muted text-sm mt-2">Please try again</p>
        </div>
      )}

      {/* Token Grid */}
      {!isLoading && !error && tokens.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {tokens.map((token) => (
            <TrendingCard key={`${token.chain}-${token.address}`} token={token} />
          ))}
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && tokens.length === 0 && (
        <div className="text-center py-12">
          <Search className="w-12 h-12 mx-auto text-terminal-muted mb-4" />
          <p className="text-terminal-muted">No trending tokens found</p>
          <p className="text-sm text-terminal-muted mt-2">
            Try refreshing or check back later
          </p>
        </div>
      )}
    </div>
  );
}
