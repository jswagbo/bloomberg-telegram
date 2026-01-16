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
  Shield,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDistanceToNow } from "date-fns";
import api from "@/lib/api";

interface NewPairToken {
  address: string;
  symbol: string;
  name: string;
  chain: string;
  price_usd: number | null;
  price_change_24h: number | null;
  price_change_1h: number | null;
  volume_24h: number | null;
  liquidity_usd: number | null;
  market_cap: number | null;
  
  // Holder data
  holder_count: number;
  top_10_percent: number;
  top_11_30_percent: number;
  top_31_50_percent: number;
  rest_percent: number;
  
  // Metadata
  age_hours: number;
  dex_name: string;
  is_boosted: boolean;
  
  image_url: string | null;
  dexscreener_url: string;
  gecko_terminal_url: string;
  
  // Telegram mentions
  total_mentions: number;
  human_discussions: number;
  top_messages: Array<{
    text: string;
    source_name: string;
    timestamp: string | null;
    sentiment: string;
  }>;
  kol_count: number;
}

function NewPairCard({ token }: { token: NewPairToken }) {
  const [copied, setCopied] = useState(false);

  const copyAddress = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    navigator.clipboard.writeText(token.address);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Use 1h price change as primary for new pairs
  const priceChange = token.price_change_1h ?? token.price_change_24h;
  const priceChangeLabel = token.price_change_1h !== null ? "1h" : "24h";

  // Format age
  const formatAge = (hours: number) => {
    if (hours < 1) return `${Math.round(hours * 60)}m`;
    if (hours < 24) return `${Math.round(hours)}h`;
    return `${Math.round(hours / 24)}d`;
  };

  // Holder distribution health (good if top 10 holds less)
  const holderHealth = token.top_10_percent < 20 ? "excellent" : 
                       token.top_10_percent < 30 ? "good" : 
                       token.top_10_percent < 40 ? "fair" : "risky";

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-terminal-card border border-primary-600/30 rounded-xl overflow-hidden hover:border-primary-600/50 transition-all"
    >
      <Link href={`/token/${token.chain}/${token.address}`}>
        {/* Header */}
        <div className="px-4 py-3 flex items-center justify-between bg-primary-600/10">
          <div className="flex items-center gap-3">
            {/* Token Icon */}
            <div className="w-10 h-10 rounded-lg flex items-center justify-center text-lg font-bold bg-primary-600/20 text-primary-400">
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
                {token.is_boosted && (
                  <span className="text-xs px-1.5 py-0.5 rounded bg-green-500/20 text-green-400 flex items-center gap-1">
                    <Zap className="w-3 h-3" /> Paid
                  </span>
                )}
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
            {priceChange !== null && (
              <p className={cn(
                "text-xs flex items-center gap-1 justify-end font-medium",
                priceChange >= 0 ? "text-bullish" : "text-bearish"
              )}>
                {priceChange >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                {Math.abs(priceChange).toFixed(1)}% ({priceChangeLabel})
              </p>
            )}
          </div>
        </div>

        {/* Key Stats Row */}
        <div className="px-4 py-3 grid grid-cols-4 gap-2 border-b border-terminal-border bg-terminal-bg/50">
          {/* Age */}
          <div className="text-center">
            <div className="flex items-center justify-center gap-1 text-primary-400">
              <Clock className="w-3 h-3" />
              <span className="text-sm font-bold">{formatAge(token.age_hours)}</span>
            </div>
            <p className="text-[10px] text-terminal-muted">Age</p>
          </div>
          
          {/* Holders */}
          <div className="text-center">
            <div className="flex items-center justify-center gap-1 text-bullish">
              <Users className="w-3 h-3" />
              <span className="text-sm font-bold">
                {token.holder_count > 0 ? token.holder_count.toLocaleString() : "—"}
              </span>
            </div>
            <p className="text-[10px] text-terminal-muted">Holders</p>
          </div>
          
          {/* Top 10 % - only show if we have real data */}
          <div className="text-center">
            {token.holder_count > 0 ? (
              <div className={cn(
                "text-sm font-bold",
                holderHealth === "excellent" ? "text-bullish" :
                holderHealth === "good" ? "text-green-400" :
                holderHealth === "fair" ? "text-yellow-400" :
                "text-bearish"
              )}>
                {token.top_10_percent.toFixed(0)}%
              </div>
            ) : (
              <div className="text-sm font-bold text-terminal-muted">—</div>
            )}
            <p className="text-[10px] text-terminal-muted">Top 10</p>
          </div>
          
          {/* Mentions */}
          <div className="text-center">
            <div className="flex items-center justify-center gap-1 text-primary-400">
              <MessageSquare className="w-3 h-3" />
              <span className="text-sm font-bold">{token.total_mentions}</span>
            </div>
            <p className="text-[10px] text-terminal-muted">Mentions</p>
          </div>
        </div>

        {/* Holder Distribution Bar - only show if we have data */}
        {token.holder_count > 0 ? (
          <div className="px-4 py-2 border-b border-terminal-border">
            <div className="flex items-center gap-2 mb-1">
              <Shield className={cn(
                "w-3 h-3",
                holderHealth === "excellent" || holderHealth === "good" ? "text-bullish" : "text-yellow-400"
              )} />
              <span className="text-xs text-terminal-muted">Holder Distribution</span>
            </div>
            <div className="h-2 rounded-full overflow-hidden flex bg-terminal-border">
              <div 
                className="bg-bearish" 
                style={{ width: `${token.top_10_percent}%` }}
                title={`Top 10: ${token.top_10_percent.toFixed(1)}%`}
              />
              <div 
                className="bg-yellow-500" 
                style={{ width: `${token.top_11_30_percent}%` }}
                title={`Top 11-30: ${token.top_11_30_percent.toFixed(1)}%`}
              />
              <div 
                className="bg-primary-500" 
                style={{ width: `${token.top_31_50_percent}%` }}
                title={`Top 31-50: ${token.top_31_50_percent.toFixed(1)}%`}
              />
              <div 
                className="bg-bullish" 
                style={{ width: `${token.rest_percent}%` }}
                title={`Rest: ${token.rest_percent.toFixed(1)}%`}
              />
            </div>
            <div className="flex justify-between text-[10px] text-terminal-muted mt-1">
              <span>Top 10: {token.top_10_percent.toFixed(0)}%</span>
              <span>Others: {token.rest_percent.toFixed(0)}%</span>
            </div>
          </div>
        ) : (
          <div className="px-4 py-2 border-b border-terminal-border">
            <div className="flex items-center gap-2">
              <Shield className="w-3 h-3 text-terminal-muted" />
              <span className="text-xs text-terminal-muted">Holder data pending (token too new)</span>
            </div>
          </div>
        )}

        {/* KOL Mentions */}
        {token.kol_count > 0 && (
          <div className="px-4 py-2 bg-yellow-500/10 border-b border-terminal-border">
            <div className="flex items-center gap-2">
              <Flame className="w-4 h-4 text-yellow-500" />
              <span className="text-xs font-medium text-yellow-500">
                {token.kol_count} KOL{token.kol_count > 1 ? 's' : ''} mentioned
              </span>
            </div>
          </div>
        )}

        {/* Top Discussion */}
        <div className="p-4">
          {token.top_messages.length > 0 ? (
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
          ) : token.total_mentions > 0 ? (
            <p className="text-sm text-terminal-muted italic text-center">
              Mentioned but no discussion captured yet
            </p>
          ) : (
            <p className="text-sm text-terminal-muted italic text-center">
              New token - no Telegram mentions yet
            </p>
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
          
          <div className="flex items-center gap-3">
            <a
              href={token.gecko_terminal_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="flex items-center gap-1 text-xs text-terminal-muted hover:text-primary-400 transition-colors"
            >
              GeckoTerminal
              <ExternalLink className="w-3 h-3" />
            </a>
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
        </div>
      </Link>
    </motion.div>
  );
}

export function TrendingFeed() {
  const [chainFilter, setChainFilter] = useState<string | null>(null);
  const [minHolders, setMinHolders] = useState(50);
  const [maxTop10, setMaxTop10] = useState(40);
  const queryClient = useQueryClient();

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["new-pairs-feed", chainFilter, minHolders, maxTop10],
    queryFn: () => api.getNewPairsFeed({
      chain: chainFilter || undefined,
      min_holders: minHolders,
      max_top_10_percent: maxTop10,
      max_age_hours: 24,
      min_liquidity: 1000,
      limit: 50,
    }),
    staleTime: 60000,
    refetchOnWindowFocus: false,
  });

  const refreshMutation = useMutation({
    mutationFn: () => api.refreshTrendingMessages(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["new-pairs-feed"] });
    },
  });

  const handleRefresh = async () => {
    await refreshMutation.mutateAsync();
    refetch();
  };

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-bearish mb-4">Failed to load new pairs</p>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold">New Pairs (Last 24h)</h2>
          <p className="text-sm text-terminal-muted">
            50+ holders • Top 10 wallets &lt; 40% • Fresh launches
          </p>
        </div>
        
        <button
          onClick={handleRefresh}
          disabled={refreshMutation.isPending || isFetching}
          className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors",
            refreshMutation.isPending || isFetching
              ? "bg-terminal-border text-terminal-muted cursor-not-allowed"
              : "bg-primary-600 hover:bg-primary-700 text-white"
          )}
        >
          <RefreshCw className={cn(
            "w-4 h-4",
            (refreshMutation.isPending || isFetching) && "animate-spin"
          )} />
          {refreshMutation.isPending ? "Scanning..." : isFetching ? "Loading..." : "Refresh Mentions"}
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Chain Filter */}
        <div className="flex items-center gap-2 bg-terminal-bg rounded-lg p-1">
          {["all", "solana", "base", "bsc"].map((chain) => (
            <button
              key={chain}
              onClick={() => setChainFilter(chain === "all" ? null : chain)}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                (chain === "all" && !chainFilter) || chainFilter === chain
                  ? "bg-primary-600 text-white"
                  : "text-terminal-muted hover:text-terminal-text"
              )}
            >
              {chain === "all" ? "All Chains" : chain.charAt(0).toUpperCase() + chain.slice(1)}
            </button>
          ))}
        </div>

        {/* Holder Filter */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-terminal-muted">Min Holders:</span>
          <select
            value={minHolders}
            onChange={(e) => setMinHolders(Number(e.target.value))}
            className="bg-terminal-bg border border-terminal-border rounded-lg px-3 py-1.5 text-sm"
          >
            <option value={25}>25+</option>
            <option value={50}>50+</option>
            <option value={100}>100+</option>
            <option value={200}>200+</option>
          </select>
        </div>

        {/* Top 10 Filter */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-terminal-muted">Top 10 Max:</span>
          <select
            value={maxTop10}
            onChange={(e) => setMaxTop10(Number(e.target.value))}
            className="bg-terminal-bg border border-terminal-border rounded-lg px-3 py-1.5 text-sm"
          >
            <option value={30}>30%</option>
            <option value={40}>40%</option>
            <option value={50}>50%</option>
            <option value={60}>60%</option>
          </select>
        </div>
      </div>

      {/* Stats */}
      {data && (
        <div className="flex flex-wrap items-center gap-4 text-sm text-terminal-muted">
          <span className="font-medium text-primary-400">{data.total_pairs} tokens found</span>
          <span>•</span>
          <span>{data.messages_scanned} Telegram messages scanned</span>
          <span>•</span>
          <span>Updated {formatDistanceToNow(new Date(data.last_updated))} ago</span>
        </div>
      )}

      {/* Loading State */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="bg-terminal-card border border-terminal-border rounded-xl h-64 animate-pulse" />
          ))}
        </div>
      ) : data?.pairs?.length === 0 ? (
        <div className="text-center py-12 bg-terminal-card border border-terminal-border rounded-xl">
          <Users className="w-12 h-12 text-terminal-muted mx-auto mb-4" />
          <h3 className="font-semibold mb-2">No New Pairs Found</h3>
          <p className="text-sm text-terminal-muted mb-4">
            No tokens match your filters. Try adjusting the criteria.
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            <button
              onClick={() => setMinHolders(25)}
              className="px-3 py-1.5 bg-terminal-border rounded-lg text-sm hover:bg-terminal-border/80"
            >
              Lower holder requirement
            </button>
            <button
              onClick={() => setMaxTop10(50)}
              className="px-3 py-1.5 bg-terminal-border rounded-lg text-sm hover:bg-terminal-border/80"
            >
              Increase top 10 max
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data?.pairs?.map((token: NewPairToken) => (
            <NewPairCard key={`${token.chain}-${token.address}`} token={token} />
          ))}
        </div>
      )}
    </div>
  );
}
