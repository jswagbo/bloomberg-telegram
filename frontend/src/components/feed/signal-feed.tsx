"use client";

import { useQuery } from "@tanstack/react-query";
import { SignalCard } from "./signal-card";
import { SignalCardSkeleton } from "./signal-card-skeleton";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";

export function SignalFeed() {
  const { chain, minScore, minSources } = useStore();

  const { data: signals, isLoading, error } = useQuery({
    queryKey: ["signals", chain, minScore, minSources],
    queryFn: () => api.getSignalFeed({ chain, minScore, minSources }),
    refetchInterval: 10000, // Refetch every 10 seconds
  });

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

  if (!signals || signals.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-terminal-muted">No signals found</p>
        <p className="text-sm text-terminal-muted mt-2">
          Adjust your filters or check back later
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {signals.map((signal: any) => (
        <SignalCard key={signal.cluster_id} signal={signal} />
      ))}
    </div>
  );
}
