"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { 
  ArrowLeft, 
  ExternalLink, 
  TrendingUp, 
  TrendingDown,
  Clock,
  Users,
  Wallet,
  Copy,
  Star,
  AlertCircle
} from "lucide-react";
import { api } from "@/lib/api";
import { cn, formatPrice, formatNumber, truncateAddress, getDexScreenerUrl } from "@/lib/utils";
import { formatDistanceToNow } from "date-fns";

export default function TokenDetailPage() {
  const params = useParams();
  const chain = params.chain as string;
  const address = params.address as string;

  const { data: tokenInfo, isLoading: infoLoading } = useQuery({
    queryKey: ["token-info", chain, address],
    queryFn: () => api.getTokenInfo(chain, address),
  });

  const { data: cluster } = useQuery({
    queryKey: ["token-cluster", chain, address],
    queryFn: async () => {
      try {
        const response = await fetch(
          `/api/v1/signals/token/${chain}/${address}`
        );
        if (response.ok) return response.json();
        return null;
      } catch {
        return null;
      }
    },
  });

  const { data: whyMoving, refetch: refetchWhyMoving, isLoading: whyMovingLoading } = useQuery({
    queryKey: ["why-moving", chain, address],
    queryFn: () => api.getWhyMoving(chain, address),
    enabled: false,
  });

  const copyAddress = () => {
    navigator.clipboard.writeText(address);
  };

  if (infoLoading) {
    return <TokenDetailSkeleton />;
  }

  return (
    <div className="space-y-6">
      {/* Back button */}
      <Link href="/" className="inline-flex items-center gap-2 text-terminal-muted hover:text-terminal-text transition-colors">
        <ArrowLeft className="w-4 h-4" />
        Back to Feed
      </Link>

      {/* Header */}
      <div className="bg-terminal-card border border-terminal-border rounded-xl p-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-primary-600/20 flex items-center justify-center text-2xl font-bold">
              {tokenInfo?.symbol?.[0] || "?"}
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold">${tokenInfo?.symbol || truncateAddress(address)}</h1>
                <span className="px-2 py-1 rounded bg-purple-500/20 text-purple-400 text-sm">
                  {chain}
                </span>
              </div>
              <div className="flex items-center gap-2 mt-1 text-terminal-muted">
                <span className="font-mono text-sm">{truncateAddress(address, 8)}</span>
                <button onClick={copyAddress} className="hover:text-terminal-text transition-colors">
                  <Copy className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button className="p-2 rounded-lg hover:bg-terminal-border transition-colors">
              <Star className="w-5 h-5 text-terminal-muted" />
            </button>
            <a
              href={getDexScreenerUrl(chain, address)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-4 py-2 bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors"
            >
              <span>DEX Screener</span>
              <ExternalLink className="w-4 h-4" />
            </a>
          </div>
        </div>

        {/* Price */}
        {tokenInfo && (
          <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-terminal-bg rounded-lg p-4">
              <div className="text-terminal-muted text-sm mb-1">Price</div>
              <div className="text-xl font-bold">${formatPrice(tokenInfo.price_usd || 0)}</div>
            </div>
            <div className="bg-terminal-bg rounded-lg p-4">
              <div className="text-terminal-muted text-sm mb-1">24h Change</div>
              <div className={cn(
                "text-xl font-bold flex items-center gap-1",
                (tokenInfo.price_change_24h || 0) >= 0 ? "text-bullish" : "text-bearish"
              )}>
                {(tokenInfo.price_change_24h || 0) >= 0 ? (
                  <TrendingUp className="w-5 h-5" />
                ) : (
                  <TrendingDown className="w-5 h-5" />
                )}
                {(tokenInfo.price_change_24h || 0).toFixed(2)}%
              </div>
            </div>
            <div className="bg-terminal-bg rounded-lg p-4">
              <div className="text-terminal-muted text-sm mb-1">Market Cap</div>
              <div className="text-xl font-bold">${formatNumber(tokenInfo.market_cap || 0)}</div>
            </div>
            <div className="bg-terminal-bg rounded-lg p-4">
              <div className="text-terminal-muted text-sm mb-1">Liquidity</div>
              <div className="text-xl font-bold">${formatNumber(tokenInfo.liquidity_usd || 0)}</div>
            </div>
          </div>
        )}
      </div>

      {/* Why Is This Moving */}
      <div className="bg-terminal-card border border-terminal-border rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-fire" />
            Why Is This Moving?
          </h2>
          <button
            onClick={() => refetchWhyMoving()}
            disabled={whyMovingLoading}
            className="px-4 py-2 bg-fire/20 text-fire rounded-lg hover:bg-fire/30 transition-colors disabled:opacity-50"
          >
            {whyMovingLoading ? "Analyzing..." : "Analyze"}
          </button>
        </div>

        {whyMoving ? (
          <div className="space-y-4">
            {/* Summary */}
            <div className="bg-terminal-bg rounded-lg p-4">
              <p className="text-sm">{whyMoving.summary}</p>
              <div className="flex items-center gap-2 mt-2 text-xs text-terminal-muted">
                <span>Confidence: {(whyMoving.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>

            {/* Top Reasons */}
            <div>
              <h3 className="text-sm font-medium text-terminal-muted mb-2">Top Reasons</h3>
              <div className="space-y-2">
                {whyMoving.reasons.map((reason) => (
                  <div key={reason.rank} className="flex items-center gap-2 text-sm">
                    <span className="w-6 h-6 rounded-full bg-primary-600/20 flex items-center justify-center text-xs">
                      {reason.rank}
                    </span>
                    <span>{reason.description}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Timeline */}
            {whyMoving.timeline.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-terminal-muted mb-2">Timeline</h3>
                <div className="space-y-2">
                  {whyMoving.timeline.slice(0, 10).map((event, i) => (
                    <div key={i} className="flex items-start gap-3 text-sm">
                      <div className="text-terminal-muted text-xs whitespace-nowrap">
                        {formatDistanceToNow(new Date(event.timestamp))} ago
                      </div>
                      <div className="flex-1">
                        <span className="text-primary-400">{event.type}:</span> {event.description}
                        {event.source && (
                          <span className="text-terminal-muted ml-1">({event.source})</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="text-terminal-muted text-sm">
            Click "Analyze" to see what's driving this token's price movement.
          </p>
        )}
      </div>

      {/* Signal Cluster */}
      {cluster && (
        <div className="bg-terminal-card border border-terminal-border rounded-xl p-6">
          <h2 className="text-lg font-bold mb-4">Signal Intelligence</h2>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-terminal-bg rounded-lg p-4">
              <div className="flex items-center gap-2 text-terminal-muted text-sm mb-1">
                <Users className="w-4 h-4" />
                Sources
              </div>
              <div className="text-xl font-bold">{cluster.metrics?.unique_sources || 0}</div>
            </div>
            <div className="bg-terminal-bg rounded-lg p-4">
              <div className="flex items-center gap-2 text-terminal-muted text-sm mb-1">
                <TrendingUp className="w-4 h-4" />
                Mentions
              </div>
              <div className="text-xl font-bold">{cluster.metrics?.total_mentions || 0}</div>
            </div>
            <div className="bg-terminal-bg rounded-lg p-4">
              <div className="flex items-center gap-2 text-terminal-muted text-sm mb-1">
                <Wallet className="w-4 h-4 text-whale" />
                Wallets
              </div>
              <div className="text-xl font-bold">{cluster.metrics?.unique_wallets || 0}</div>
            </div>
            <div className="bg-terminal-bg rounded-lg p-4">
              <div className="flex items-center gap-2 text-terminal-muted text-sm mb-1">
                <Clock className="w-4 h-4" />
                First Seen
              </div>
              <div className="text-sm font-medium">
                {cluster.timing?.first_seen 
                  ? formatDistanceToNow(new Date(cluster.timing.first_seen)) + " ago"
                  : "N/A"}
              </div>
            </div>
          </div>

          {/* Sources */}
          <div className="mb-4">
            <h3 className="text-sm font-medium text-terminal-muted mb-2">Mentioned By</h3>
            <div className="flex flex-wrap gap-2">
              {cluster.sources?.map((source: string, i: number) => (
                <span key={i} className="px-3 py-1 bg-terminal-bg rounded-lg text-sm">
                  {source}
                </span>
              ))}
            </div>
          </div>

          {/* Top Messages */}
          {cluster.top_messages?.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-terminal-muted mb-2">Recent Signals</h3>
              <div className="space-y-2">
                {cluster.top_messages.slice(0, 5).map((msg: any, i: number) => (
                  <div key={i} className="bg-terminal-bg rounded-lg p-3">
                    <div className="flex items-center gap-2 text-xs text-terminal-muted mb-1">
                      <span className="font-medium text-terminal-text">{msg.source_name}</span>
                      <span>•</span>
                      <span>{formatDistanceToNow(new Date(msg.timestamp))} ago</span>
                    </div>
                    <p className="text-sm line-clamp-2">{msg.original_text}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TokenDetailSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-4 w-24 bg-terminal-border rounded" />
      <div className="bg-terminal-card border border-terminal-border rounded-xl p-6">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-full bg-terminal-border" />
          <div className="space-y-2">
            <div className="h-8 w-32 bg-terminal-border rounded" />
            <div className="h-4 w-48 bg-terminal-border rounded" />
          </div>
        </div>
        <div className="mt-6 grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-terminal-bg rounded-lg p-4">
              <div className="h-4 w-16 bg-terminal-border rounded mb-2" />
              <div className="h-6 w-24 bg-terminal-border rounded" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
