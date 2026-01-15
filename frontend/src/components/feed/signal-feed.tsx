"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { SignalCard } from "./signal-card";
import { SignalCardSkeleton } from "./signal-card-skeleton";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";

// Check if a token has a valid name/symbol (not just an address)
function hasValidTokenName(signal: any): boolean {
  const token = signal?.token;
  if (!token) return false;
  
  // Check for symbol or name
  const symbol = token.symbol;
  const name = token.name;
  
  // Must have a symbol that's not just an address
  if (symbol) {
    // Reject if symbol looks like an address (starts with 0x or is very long)
    if (symbol.startsWith("0x") || symbol.length > 20) return false;
    // Accept valid symbols
    return true;
  }
  
  // Check name as fallback
  if (name) {
    if (name.startsWith("0x") || name.length > 40) return false;
    return true;
  }
  
  return false;
}

// Check if chain is valid (sol, base, bsc only)
function isValidChain(signal: any): boolean {
  const chain = signal?.token?.chain?.toLowerCase();
  return chain === "solana" || chain === "base" || chain === "bsc";
}

export function SignalFeed() {
  const { chain, minScore, minSources } = useStore();

  const { data: signals, isLoading, error } = useQuery({
    queryKey: ["signals", chain, minScore, minSources],
    queryFn: () => api.getSignalFeed({ chain, minScore, minSources }),
    refetchInterval: 10000, // Refetch every 10 seconds
  });

  // Filter signals to only show tokens with valid names on valid chains
  const filteredSignals = useMemo(() => {
    if (!signals) return [];
    
    return signals.filter((signal: any) => {
      // Must be on a valid chain (sol, base, bsc)
      if (!isValidChain(signal)) return false;
      
      // Must have a valid token name/symbol (not just address)
      if (!hasValidTokenName(signal)) return false;
      
      return true;
    });
  }, [signals]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(5)].map((_, i) => (
          <SignalCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-terminal-muted">Failed to load signals</p>
        <button
          onClick={() => window.location.reload()}
          className="mt-4 px-4 py-2 bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!filteredSignals || filteredSignals.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-terminal-muted">No signals found</p>
        <p className="text-sm text-terminal-muted mt-2">
          {signals && signals.length > 0 
            ? `${signals.length} signals were filtered out (missing token names)`
            : "Adjust your filters or check back later"
          }
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {filteredSignals.map((signal: any) => (
        <SignalCard key={signal.cluster_id} signal={signal} />
      ))}
    </div>
  );
}
