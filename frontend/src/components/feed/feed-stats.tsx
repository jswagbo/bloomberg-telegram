"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, Zap, Users } from "lucide-react";
import { api } from "@/lib/api";

export function FeedStats() {
  const { data: stats } = useQuery({
    queryKey: ["feed-stats"],
    queryFn: () => api.getFeedStats(),
    refetchInterval: 30000,
  });

  if (!stats) {
    return null;
  }

  return (
    <div className="flex items-center gap-6 text-sm">
      <div className="flex items-center gap-2 text-terminal-muted">
        <Activity className="w-4 h-4 text-bullish" />
        <span>
          <strong className="text-terminal-text">{stats.active_clusters || 0}</strong> active signals
        </span>
      </div>
      <div className="flex items-center gap-2 text-terminal-muted">
        <Zap className="w-4 h-4 text-fire" />
        <span>
          <strong className="text-terminal-text">{stats.total_mentions || 0}</strong> mentions
        </span>
      </div>
      <div className="flex items-center gap-2 text-terminal-muted">
        <Users className="w-4 h-4 text-primary-400" />
        <span>
          <strong className="text-terminal-text">{stats.unique_sources || 0}</strong> sources
        </span>
      </div>
    </div>
  );
}
