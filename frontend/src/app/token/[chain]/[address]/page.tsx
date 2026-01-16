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
  MessageSquare,
  Copy,
  Check,
  Users,
  Clock,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { formatDistanceToNow } from "date-fns";
import { useState } from "react";

interface TokenMessage {
  text: string;
  source_name: string;
  timestamp: string | null;
  sentiment: string;
  is_human_discussion: boolean;
}

interface KOLHolder {
  address: string;
  name: string;
  twitter: string | null;
  tier: string;
}

export default function TokenDetailPage() {
  const params = useParams();
  const chain = params.chain as string;
  const address = params.address as string;
  const [copied, setCopied] = useState(false);

  // Fetch token detail with mentions
  const { data, isLoading, error } = useQuery({
    queryKey: ["trending-token-detail", chain, address],
    queryFn: () => api.getTrendingTokenDetail(chain, address),
    staleTime: 1000 * 60 * 2, // 2 minutes
  });

  const copyAddress = () => {
    navigator.clipboard.writeText(address);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-32 bg-terminal-border rounded" />
          <div className="h-24 bg-terminal-card rounded-xl" />
          <div className="h-64 bg-terminal-card rounded-xl" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-4xl mx-auto">
        <Link href="/" className="flex items-center gap-2 text-terminal-muted hover:text-terminal-text mb-6">
          <ArrowLeft className="w-4 h-4" />
          Back to Feed
        </Link>
        <div className="text-center py-12">
          <p className="text-bearish">Failed to load token details</p>
        </div>
      </div>
    );
  }

  const totalSentiment = data.sentiment.bullish + data.sentiment.bearish + data.sentiment.neutral;
  const bullishPercent = totalSentiment > 0 ? (data.sentiment.bullish / totalSentiment) * 100 : 50;
  const messages: TokenMessage[] = data.messages || [];
  const kolHolders: KOLHolder[] = data.kol_holders || [];
  const priceChange = data.price_change_6h ?? data.price_change_24h;
  const priceChangeLabel = data.price_change_6h !== null ? "6h" : "24h";

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Back Button */}
      <Link href="/" className="flex items-center gap-2 text-terminal-muted hover:text-terminal-text">
        <ArrowLeft className="w-4 h-4" />
        Back to Feed
      </Link>

      {/* Token Header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-terminal-card border border-terminal-border rounded-xl p-6"
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-xl bg-primary-600/20 flex items-center justify-center text-2xl font-bold text-primary-400">
              {data.symbol[0]}
            </div>
            <div>
              <h1 className="text-2xl font-bold">${data.symbol}</h1>
              <p className="text-terminal-muted">{data.name}</p>
              <div className="flex items-center gap-2 mt-1">
                <span className={cn(
                  "text-xs px-2 py-0.5 rounded",
                  chain === "solana" ? "bg-purple-500/20 text-purple-400" :
                  chain === "base" ? "bg-blue-500/20 text-blue-400" :
                  "bg-yellow-500/20 text-yellow-400"
                )}>
                  {chain}
                </span>
                <button
                  onClick={copyAddress}
                  className="flex items-center gap-1 text-xs text-terminal-muted hover:text-terminal-text"
                >
                  {copied ? <Check className="w-3 h-3 text-bullish" /> : <Copy className="w-3 h-3" />}
                  {copied ? "Copied!" : "Copy Address"}
                </button>
              </div>
            </div>
          </div>

          {/* Price Info */}
          <div className="text-right">
            {data.price_usd !== null && (
              <p className="text-xl font-mono">
                ${data.price_usd < 0.01 ? data.price_usd.toExponential(2) : data.price_usd.toFixed(6)}
              </p>
            )}
            {priceChange !== null && (
              <p className={cn(
                "flex items-center gap-1 justify-end font-medium",
                priceChange >= 0 ? "text-bullish" : "text-bearish"
              )}>
                {priceChange >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                {Math.abs(priceChange).toFixed(2)}% ({priceChangeLabel})
              </p>
            )}
            <a
              href={data.dexscreener_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-primary-400 hover:text-primary-300 mt-2"
            >
              View on DexScreener
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
      </motion.div>

      {/* Mention Stats */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="grid grid-cols-4 gap-4"
      >
        <div className="bg-terminal-card border border-terminal-border rounded-xl p-4 text-center">
          <div className="text-3xl font-bold text-primary-400">{data.total_mentions}</div>
          <div className="text-sm text-terminal-muted">Total Mentions</div>
        </div>
        <div className="bg-terminal-card border border-terminal-border rounded-xl p-4 text-center">
          <div className="text-3xl font-bold text-bullish">{data.human_discussions}</div>
          <div className="text-sm text-terminal-muted">Discussions</div>
        </div>
        <div className="bg-terminal-card border border-terminal-border rounded-xl p-4 text-center">
          <div className="text-3xl font-bold">{data.sources.length}</div>
          <div className="text-sm text-terminal-muted">Sources</div>
        </div>
        <div className="bg-terminal-card border border-terminal-border rounded-xl p-4 text-center">
          <div className="text-3xl font-bold text-yellow-500">{data.kol_count || 0}</div>
          <div className="text-sm text-terminal-muted">KOL Mentions</div>
        </div>
      </motion.div>

      {/* KOL Holders Section */}
      {kolHolders.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.12 }}
          className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4"
        >
          <h3 className="font-semibold text-yellow-500 mb-3 flex items-center gap-2">
            🔥 KOL Activity
          </h3>
          <div className="flex flex-wrap gap-3">
            {kolHolders.map((kol, i) => (
              <div key={i} className="bg-terminal-card rounded-lg px-3 py-2 flex items-center gap-2">
                <span className="font-medium">{kol.name}</span>
                {kol.twitter && (
                  <a 
                    href={`https://twitter.com/${kol.twitter.replace('@', '')}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary-400 text-sm hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {kol.twitter}
                  </a>
                )}
                <span className={cn(
                  "text-xs px-1.5 py-0.5 rounded",
                  kol.tier === "mega" ? "bg-yellow-500/20 text-yellow-500" :
                  kol.tier === "large" ? "bg-purple-500/20 text-purple-400" :
                  "bg-terminal-border text-terminal-muted"
                )}>
                  {kol.tier}
                </span>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Sentiment Bar */}
      {totalSentiment > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="bg-terminal-card border border-terminal-border rounded-xl p-4"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-terminal-muted">Sentiment</span>
            <span className={cn(
              "text-sm font-medium",
              bullishPercent >= 60 ? "text-bullish" :
              bullishPercent <= 40 ? "text-bearish" :
              "text-terminal-muted"
            )}>
              {bullishPercent >= 60 ? "Bullish" : bullishPercent <= 40 ? "Bearish" : "Mixed"}
            </span>
          </div>
          <div className="h-3 bg-terminal-border rounded-full overflow-hidden flex">
            <div 
              className="bg-bullish h-full transition-all"
              style={{ width: `${bullishPercent}%` }}
            />
            <div 
              className="bg-bearish h-full transition-all"
              style={{ width: `${100 - bullishPercent}%` }}
            />
          </div>
          <div className="flex justify-between mt-1 text-xs text-terminal-muted">
            <span>{data.sentiment.bullish} bullish</span>
            <span>{data.sentiment.neutral} neutral</span>
            <span>{data.sentiment.bearish} bearish</span>
          </div>
        </motion.div>
      )}

      {/* Discussion Messages */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="bg-terminal-card border border-terminal-border rounded-xl p-6"
      >
        <div className="flex items-center gap-2 mb-4">
          <MessageSquare className="w-5 h-5 text-primary-400" />
          <h2 className="text-lg font-semibold">Community Discussion</h2>
        </div>

        {messages.length > 0 ? (
          <div className="space-y-4">
            {messages.map((msg, i) => (
              <div 
                key={i}
                className={cn(
                  "border-l-2 pl-4 py-2",
                  msg.sentiment === "bullish" ? "border-bullish" :
                  msg.sentiment === "bearish" ? "border-bearish" :
                  "border-terminal-border"
                )}
              >
                <p className="text-terminal-text leading-relaxed">{msg.text}</p>
                <div className="flex items-center gap-3 mt-2 text-xs text-terminal-muted">
                  <span className="flex items-center gap-1">
                    <Users className="w-3 h-3" />
                    {msg.source_name}
                  </span>
                  {msg.timestamp && (
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatDistanceToNow(new Date(msg.timestamp))} ago
                    </span>
                  )}
                  <span className={cn(
                    "px-1.5 py-0.5 rounded",
                    msg.sentiment === "bullish" ? "bg-bullish/20 text-bullish" :
                    msg.sentiment === "bearish" ? "bg-bearish/20 text-bearish" :
                    "bg-terminal-border text-terminal-muted"
                  )}>
                    {msg.sentiment}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-12">
            <MessageSquare className="w-12 h-12 mx-auto text-terminal-muted mb-4" />
            <p className="text-terminal-muted text-lg">No mentions yet</p>
            <p className="text-terminal-muted text-sm mt-2">
              This token hasn't been discussed in your monitored Telegram channels.
            </p>
            <p className="text-terminal-muted text-sm mt-1">
              Click "Refresh Mentions" on the main page to scan for new messages.
            </p>
          </div>
        )}
      </motion.div>

      {/* Sources */}
      {data.sources.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="bg-terminal-card border border-terminal-border rounded-xl p-4"
        >
          <h3 className="text-sm font-medium text-terminal-muted mb-3">Discussed In</h3>
          <div className="flex flex-wrap gap-2">
            {data.sources.map((source: string, i: number) => (
              <span 
                key={i}
                className="px-3 py-1 bg-terminal-bg rounded-lg text-sm"
              >
                {source}
              </span>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  );
}
