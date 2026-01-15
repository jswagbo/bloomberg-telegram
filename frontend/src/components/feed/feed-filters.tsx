"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, ArrowUpDown, SlidersHorizontal, X, Radio, Loader2, Check, AlertCircle } from "lucide-react";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

const chains = [
  { id: null, label: "All", icon: "🌐" },
  { id: "solana", label: "SOL", icon: "◎" },
  { id: "base", label: "Base", icon: "🔵" },
  { id: "bsc", label: "BSC", icon: "🟡" },
];

const scoreFilters = [
  { min: 0, label: "All" },
  { min: 50, label: "50+" },
  { min: 70, label: "70+" },
  { min: 85, label: "85+" },
];

const sourceFilters = [
  { min: 1, label: "1+" },
  { min: 2, label: "2+" },
  { min: 3, label: "3+" },
];

const sortOptions = [
  { id: "score", label: "Score" },
  { id: "recent", label: "Newest" },
  { id: "velocity", label: "Velocity" },
  { id: "mentions", label: "Mentions" },
];

export function FeedFilters() {
  const { chain, minScore, minSources, setChain, setMinScore, setMinSources } = useStore();
  const [sortBy, setSortBy] = useState("score");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [scanResult, setScanResult] = useState<{ success: boolean; message: string } | null>(null);
  const [showMobileFilters, setShowMobileFilters] = useState(false);
  const queryClient = useQueryClient();

  // Fetch Telegram accounts to get account ID for scanning
  const { data: accounts } = useQuery({
    queryKey: ["telegram-accounts"],
    queryFn: () => api.getTelegramAccounts(),
    retry: false,
    staleTime: 1000 * 60 * 5,
  });

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await queryClient.invalidateQueries({ queryKey: ["signals"] });
    setTimeout(() => setIsRefreshing(false), 1000);
  };

  const handleScan = async () => {
    if (!accounts || accounts.length === 0) {
      setScanResult({ success: false, message: "No Telegram account connected" });
      setTimeout(() => setScanResult(null), 3000);
      return;
    }

    setIsScanning(true);
    setScanResult(null);

    try {
      // Scan from all connected accounts
      let totalMessages = 0;
      let totalTokens = 0;
      let totalClusters = 0;

      for (const account of accounts) {
        if (account.is_active) {
          const result = await api.ingestMessages(account.id, 100);
          totalMessages += result.messages_processed || 0;
          totalTokens += result.tokens_found || 0;
          totalClusters += result.clusters_updated || 0;
        }
      }

      // Refresh the feed after scanning
      await queryClient.invalidateQueries({ queryKey: ["signals"] });

      setScanResult({
        success: true,
        message: `Scanned ${totalMessages} messages, found ${totalTokens} tokens`,
      });
    } catch (error: any) {
      console.error("Scan error:", error);
      setScanResult({
        success: false,
        message: error?.response?.data?.detail || "Scan failed - check settings",
      });
    } finally {
      setIsScanning(false);
      setTimeout(() => setScanResult(null), 5000);
    }
  };

  const hasActiveFilters = chain !== null || minScore > 0 || minSources > 1;

  const clearFilters = () => {
    setChain(null);
    setMinScore(0);
    setMinSources(1);
  };

  return (
    <div className="space-y-3">
      {/* Main filter bar */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Scan button - triggers actual Telegram ingestion */}
        <button
          onClick={handleScan}
          disabled={isScanning}
          className={cn(
            "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
            isScanning 
              ? "bg-primary-600/20 text-primary-400" 
              : "bg-primary-600 text-white hover:bg-primary-700"
          )}
        >
          {isScanning ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Radio className="w-4 h-4" />
          )}
          <span>{isScanning ? "Scanning..." : "Scan Now"}</span>
        </button>

        {/* Scan result feedback */}
        {scanResult && (
          <div className={cn(
            "flex items-center gap-2 px-3 py-2 rounded-lg text-sm animate-in fade-in slide-in-from-left-2",
            scanResult.success 
              ? "bg-bullish/20 text-bullish" 
              : "bg-bearish/20 text-bearish"
          )}>
            {scanResult.success ? (
              <Check className="w-4 h-4" />
            ) : (
              <AlertCircle className="w-4 h-4" />
            )}
            <span>{scanResult.message}</span>
          </div>
        )}

        {/* Refresh button - just refreshes UI */}
        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className={cn(
            "flex items-center gap-2 px-3 py-2 bg-terminal-card rounded-lg text-sm font-medium transition-colors",
            isRefreshing 
              ? "text-primary-400" 
              : "text-terminal-muted hover:text-terminal-text hover:bg-terminal-border"
          )}
        >
          <RefreshCw className={cn("w-4 h-4", isRefreshing && "animate-spin")} />
          <span className="hidden sm:inline">Refresh</span>
        </button>

        <div className="w-px h-6 bg-terminal-border hidden sm:block" />

        {/* Chain Filter - Always visible */}
        <div className="flex gap-1 bg-terminal-card rounded-lg p-1">
          {chains.map((c) => (
            <button
              key={c.id || "all"}
              onClick={() => setChain(c.id)}
              className={cn(
                "px-2 sm:px-3 py-1.5 rounded-md text-sm font-medium transition-colors flex items-center gap-1",
                chain === c.id
                  ? "bg-primary-600 text-white"
                  : "text-terminal-muted hover:text-terminal-text hover:bg-terminal-border"
              )}
            >
              <span>{c.icon}</span>
              <span className="hidden sm:inline">{c.label}</span>
            </button>
          ))}
        </div>

        {/* Desktop filters */}
        <div className="hidden md:flex items-center gap-2">
          <div className="w-px h-6 bg-terminal-border" />
          
          {/* Score Filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-terminal-muted">Score:</span>
            <div className="flex gap-0.5 bg-terminal-card rounded-lg p-0.5">
              {scoreFilters.map((s) => (
                <button
                  key={s.min}
                  onClick={() => setMinScore(s.min)}
                  className={cn(
                    "px-2 py-1 rounded text-xs font-medium transition-colors",
                    minScore === s.min
                      ? "bg-primary-600 text-white"
                      : "text-terminal-muted hover:text-terminal-text"
                  )}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Sources Filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-terminal-muted">Sources:</span>
            <div className="flex gap-0.5 bg-terminal-card rounded-lg p-0.5">
              {sourceFilters.map((s) => (
                <button
                  key={s.min}
                  onClick={() => setMinSources(s.min)}
                  className={cn(
                    "px-2 py-1 rounded text-xs font-medium transition-colors",
                    minSources === s.min
                      ? "bg-primary-600 text-white"
                      : "text-terminal-muted hover:text-terminal-text"
                  )}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          <div className="w-px h-6 bg-terminal-border" />

          {/* Sort */}
          <div className="flex items-center gap-1.5">
            <ArrowUpDown className="w-3 h-3 text-terminal-muted" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="bg-terminal-card border border-terminal-border rounded-lg px-2 py-1 text-xs font-medium text-terminal-text focus:outline-none focus:ring-1 focus:ring-primary-600"
            >
              {sortOptions.map((opt) => (
                <option key={opt.id} value={opt.id}>{opt.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Mobile filter toggle */}
        <button
          onClick={() => setShowMobileFilters(!showMobileFilters)}
          className="md:hidden flex items-center gap-2 px-3 py-2 bg-terminal-card rounded-lg text-sm font-medium text-terminal-muted hover:text-terminal-text"
        >
          <SlidersHorizontal className="w-4 h-4" />
          Filters
          {hasActiveFilters && (
            <span className="w-2 h-2 bg-primary-600 rounded-full" />
          )}
        </button>

        {/* Clear filters button */}
        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="flex items-center gap-1 px-2 py-1 text-xs text-terminal-muted hover:text-terminal-text"
          >
            <X className="w-3 h-3" />
            Clear
          </button>
        )}
      </div>

      {/* Mobile filters panel */}
      {showMobileFilters && (
        <div className="md:hidden bg-terminal-card rounded-lg p-4 space-y-4 animate-in slide-in-from-top-2">
          {/* Score */}
          <div>
            <label className="text-xs text-terminal-muted block mb-2">Minimum Score</label>
            <div className="flex gap-1">
              {scoreFilters.map((s) => (
                <button
                  key={s.min}
                  onClick={() => setMinScore(s.min)}
                  className={cn(
                    "flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                    minScore === s.min
                      ? "bg-primary-600 text-white"
                      : "bg-terminal-border text-terminal-muted"
                  )}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Sources */}
          <div>
            <label className="text-xs text-terminal-muted block mb-2">Minimum Sources</label>
            <div className="flex gap-1">
              {sourceFilters.map((s) => (
                <button
                  key={s.min}
                  onClick={() => setMinSources(s.min)}
                  className={cn(
                    "flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                    minSources === s.min
                      ? "bg-primary-600 text-white"
                      : "bg-terminal-border text-terminal-muted"
                  )}
                >
                  {s.label} sources
                </button>
              ))}
            </div>
          </div>

          {/* Sort */}
          <div>
            <label className="text-xs text-terminal-muted block mb-2">Sort By</label>
            <div className="flex gap-1">
              {sortOptions.map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => setSortBy(opt.id)}
                  className={cn(
                    "flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                    sortBy === opt.id
                      ? "bg-primary-600 text-white"
                      : "bg-terminal-border text-terminal-muted"
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
