"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { 
  BarChart3, 
  TrendingUp, 
  TrendingDown,
  Clock,
  Users,
  ArrowUpRight,
  Flame
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { formatDistanceToNow } from "date-fns";

// Check if a token has a valid name/symbol (not just an address)
function hasValidTokenName(signal: any): boolean {
  const token = signal?.token;
  if (!token) return false;
  
  const symbol = token.symbol;
  const name = token.name;
  
  // Helper to check if a string looks like an address or truncated address
  const looksLikeAddress = (str: string): boolean => {
    if (!str) return true;
    if (str.startsWith("0x")) return true;
    if (str.includes("...")) return true;
    if (str.length > 15) return true;
    if (str.length > 10 && /^[a-zA-Z0-9]+$/.test(str) && /[a-z]/.test(str) && /[A-Z]/.test(str) && /\d/.test(str)) return true;
    if (str.toLowerCase().endsWith("pump")) return true;
    return false;
  };
  
  if (symbol && !looksLikeAddress(symbol)) {
    return true;
  }
  
  if (name && !looksLikeAddress(name)) {
    return true;
  }
  
  return false;
}

// Check if chain is valid (sol, base, bsc only)
function isValidChain(signal: any): boolean {
  const chain = signal?.token?.chain?.toLowerCase();
  return chain === "solana" || chain === "base" || chain === "bsc";
}

export default function TokensPage() {
  const { data: rawSignals, isLoading } = useQuery({
    queryKey: ["all-tokens"],
    queryFn: () => api.getSignalFeed({ limit: 50 }),
    staleTime: 1000 * 60,
  });

  // Filter to only show tokens with valid names on valid chains
  const signals = useMemo(() => {
    if (!rawSignals) return [];
    return rawSignals.filter((signal: any) => 
      isValidChain(signal) && hasValidTokenName(signal)
    );
  }, [rawSignals]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <BarChart3 className="w-6 h-6 text-primary-400" />
          Token Tracker
        </h1>
        <p className="text-terminal-muted mt-1">
          All tokens being discussed in monitored channels
        </p>
      </div>

      {/* Token Table */}
      <div className="bg-terminal-card border border-terminal-border rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-terminal-border">
                <th className="text-left text-sm font-medium text-terminal-muted px-4 py-3">Token</th>
                <th className="text-left text-sm font-medium text-terminal-muted px-4 py-3">Chain</th>
                <th className="text-right text-sm font-medium text-terminal-muted px-4 py-3">Score</th>
                <th className="text-right text-sm font-medium text-terminal-muted px-4 py-3">Mentions</th>
                <th className="text-right text-sm font-medium text-terminal-muted px-4 py-3">Sources</th>
                <th className="text-right text-sm font-medium text-terminal-muted px-4 py-3">Sentiment</th>
                <th className="text-right text-sm font-medium text-terminal-muted px-4 py-3">First Seen</th>
                <th className="text-right text-sm font-medium text-terminal-muted px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                Array(10).fill(0).map((_, i) => (
                  <tr key={i} className="border-b border-terminal-border">
                    {Array(8).fill(0).map((_, j) => (
                      <td key={j} className="px-4 py-4">
                        <div className="h-5 bg-terminal-border rounded animate-pulse" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : signals?.length > 0 ? (
                signals.map((signal: any, i: number) => (
                  <motion.tr
                    key={signal.cluster_id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.03 }}
                    className="border-b border-terminal-border hover:bg-terminal-border/50 transition-colors"
                  >
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-primary-600/20 flex items-center justify-center font-bold">
                          {signal.token?.symbol?.[0] || signal.token?.name?.[0] || "?"}
                        </div>
                        <div>
                          <div className="font-medium">
                            ${signal.token?.symbol || signal.token?.name}
                          </div>
                          {signal.token?.name && signal.token?.symbol && (
                            <div className="text-xs text-terminal-muted">{signal.token.name}</div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <span className={cn(
                        "px-2 py-0.5 rounded text-xs",
                        signal.token?.chain === "solana" ? "bg-purple-500/20 text-purple-400" :
                        signal.token?.chain === "base" ? "bg-blue-500/20 text-blue-400" :
                        "bg-yellow-500/20 text-yellow-400"
                      )}>
                        {signal.token?.chain}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-right">
                      <div className={cn(
                        "flex items-center justify-end gap-1 font-medium",
                        signal.score >= 70 ? "text-fire" : "text-terminal-text"
                      )}>
                        {signal.score >= 70 && <Flame className="w-4 h-4" />}
                        {signal.score.toFixed(0)}
                      </div>
                    </td>
                    <td className="px-4 py-4 text-right text-terminal-text">
                      {signal.metrics?.total_mentions}
                    </td>
                    <td className="px-4 py-4 text-right">
                      <div className="flex items-center justify-end gap-1 text-terminal-text">
                        <Users className="w-3 h-3 text-terminal-muted" />
                        {signal.metrics?.unique_sources}
                      </div>
                    </td>
                    <td className="px-4 py-4 text-right">
                      <div className="flex items-center justify-end gap-1">
                        {signal.sentiment?.percent_bullish >= 60 ? (
                          <TrendingUp className="w-4 h-4 text-bullish" />
                        ) : signal.sentiment?.percent_bullish <= 40 ? (
                          <TrendingDown className="w-4 h-4 text-bearish" />
                        ) : (
                          <div className="w-4 h-4 rounded-full bg-yellow-500/20" />
                        )}
                        <span className={cn(
                          signal.sentiment?.percent_bullish >= 60 ? "text-bullish" :
                          signal.sentiment?.percent_bullish <= 40 ? "text-bearish" :
                          "text-yellow-400"
                        )}>
                          {signal.sentiment?.percent_bullish?.toFixed(0)}%
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-right text-terminal-muted text-sm">
                      {signal.timing?.first_seen && formatDistanceToNow(new Date(signal.timing.first_seen))}
                    </td>
                    <td className="px-4 py-4 text-right">
                      <Link
                        href={`/token/${signal.token?.chain}/${signal.token?.address}`}
                        className="p-2 hover:bg-terminal-border rounded-lg transition-colors inline-flex"
                      >
                        <ArrowUpRight className="w-4 h-4 text-primary-400" />
                      </Link>
                    </td>
                  </motion.tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-terminal-muted">
                    No tokens found. Check back when signals start flowing.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
