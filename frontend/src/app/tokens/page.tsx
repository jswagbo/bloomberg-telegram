"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { 
  Search, 
  TrendingUp, 
  TrendingDown,
  ExternalLink
} from "lucide-react";
import { api } from "@/lib/api";
import { cn, formatPrice, formatNumber, truncateAddress } from "@/lib/utils";
import { TokenDisplay } from "@/components/token-display";

export default function TokensPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedChain, setSelectedChain] = useState<string | null>(null);

  const { data: searchResults, isLoading: searching } = useQuery({
    queryKey: ["token-search", searchQuery, selectedChain],
    queryFn: () => api.searchTokens(searchQuery, selectedChain || undefined),
    enabled: searchQuery.length > 1,
  });

  const { data: trendingSignals } = useQuery({
    queryKey: ["trending-signals"],
    queryFn: () => api.getTrendingSignals(undefined, 10),
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Token Search</h1>
        <p className="text-terminal-muted mt-1">
          Search for tokens or browse trending signals
        </p>
      </div>

      {/* Search */}
      <div className="flex gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-terminal-muted" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by name, symbol, or address..."
            className="w-full pl-10 pr-4 py-3 bg-terminal-card border border-terminal-border rounded-xl focus:border-primary-600 focus:outline-none"
          />
        </div>
        <select
          value={selectedChain || ""}
          onChange={(e) => setSelectedChain(e.target.value || null)}
          className="px-4 py-3 bg-terminal-card border border-terminal-border rounded-xl focus:border-primary-600 focus:outline-none"
        >
          <option value="">All Chains</option>
          <option value="solana">Solana</option>
          <option value="base">Base</option>
          <option value="bsc">BSC</option>
        </select>
      </div>

      {/* Search Results */}
      {searchQuery.length > 1 && (
        <div className="bg-terminal-card border border-terminal-border rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-terminal-border">
            <h2 className="font-medium">Search Results</h2>
          </div>

          {searching ? (
            <div className="p-6 text-center text-terminal-muted">
              Searching...
            </div>
          ) : searchResults?.length > 0 ? (
            <div className="divide-y divide-terminal-border">
              {searchResults.map((token: any) => (
                <Link
                  key={`${token.chain}-${token.address}`}
                  href={`/token/${token.chain}/${token.address}`}
                  className="flex items-center justify-between px-6 py-4 hover:bg-terminal-border/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-primary-600/20 flex items-center justify-center">
                      {token.symbol?.[0] || "?"}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{token.symbol || truncateAddress(token.address)}</span>
                        <span className="text-xs px-2 py-0.5 rounded bg-terminal-border text-terminal-muted">
                          {token.chain}
                        </span>
                      </div>
                      {token.name && (
                        <div className="text-sm text-terminal-muted">{token.name}</div>
                      )}
                    </div>
                  </div>
                  {token.price_usd && (
                    <div className="text-right">
                      <div className="font-medium">${formatPrice(token.price_usd)}</div>
                      {token.market_cap && (
                        <div className="text-sm text-terminal-muted">
                          MC: ${formatNumber(token.market_cap)}
                        </div>
                      )}
                    </div>
                  )}
                </Link>
              ))}
            </div>
          ) : (
            <div className="p-6 text-center text-terminal-muted">
              No tokens found
            </div>
          )}
        </div>
      )}

      {/* Trending */}
      {!searchQuery && trendingSignals?.length > 0 && (
        <div className="bg-terminal-card border border-terminal-border rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-terminal-border flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-fire" />
            <h2 className="font-medium">Trending Now</h2>
          </div>

          <div className="divide-y divide-terminal-border">
            {trendingSignals.map((signal: any, index: number) => (
              <Link
                key={signal.cluster_id}
                href={`/token/${signal.token.chain}/${signal.token.address || signal.token.symbol}`}
                className="flex items-center justify-between px-6 py-4 hover:bg-terminal-border/50 transition-colors"
              >
                <div className="flex items-center gap-4">
                  <div className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center font-bold",
                    index < 3 ? "bg-fire/20 text-fire" : "bg-terminal-border text-terminal-muted"
                  )}>
                    {index + 1}
                  </div>
                  <div>
                    <TokenDisplay 
                      symbol={signal.token.symbol}
                      address={signal.token.address}
                      chain={signal.token.chain}
                    />
                    <div className="text-sm text-terminal-muted mt-1">
                      {signal.metrics.unique_sources} sources • {signal.metrics.total_mentions} mentions
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className={cn(
                    "font-bold",
                    signal.score >= 70 ? "text-fire" : "text-terminal-text"
                  )}>
                    Score: {signal.score.toFixed(0)}
                  </div>
                  <div className={cn(
                    "text-sm",
                    signal.sentiment.percent_bullish >= 60 ? "text-bullish" : "text-terminal-muted"
                  )}>
                    {signal.sentiment.percent_bullish.toFixed(0)}% bullish
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
