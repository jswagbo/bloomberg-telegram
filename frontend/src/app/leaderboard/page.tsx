"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { 
  Trophy, 
  TrendingUp, 
  Clock, 
  AlertTriangle,
  Star,
  ChevronRight
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function LeaderboardPage() {
  const { data: leaderboard, isLoading } = useQuery({
    queryKey: ["source-leaderboard"],
    queryFn: () => api.getSourceLeaderboard(5, 20),
  });

  const { data: flaggedSources } = useQuery({
    queryKey: ["flagged-sources"],
    queryFn: () => api.getFlaggedSources(),
  });

  if (isLoading) {
    return <LeaderboardSkeleton />;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Trophy className="w-6 h-6 text-yellow-500" />
          Source Leaderboard
        </h1>
        <p className="text-terminal-muted mt-1">
          Track the performance of Telegram signal callers
        </p>
      </div>

      {/* Leaderboard */}
      <div className="bg-terminal-card border border-terminal-border rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-terminal-border">
          <h2 className="font-medium">Top Callers</h2>
        </div>

        <div className="divide-y divide-terminal-border">
          {leaderboard?.map((source: any, index: number) => (
            <motion.div
              key={source.telegram_id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.05 }}
              className="px-6 py-4 hover:bg-terminal-border/50 transition-colors cursor-pointer"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  {/* Rank */}
                  <div className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center font-bold",
                    index === 0 ? "bg-yellow-500/20 text-yellow-500" :
                    index === 1 ? "bg-gray-400/20 text-gray-400" :
                    index === 2 ? "bg-orange-600/20 text-orange-600" :
                    "bg-terminal-border text-terminal-muted"
                  )}>
                    {source.rank}
                  </div>

                  {/* Source info */}
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{source.name}</span>
                      {source.metrics.hit_rate >= 0.5 && (
                        <div className="flex">
                          {[...Array(Math.min(5, Math.floor(source.metrics.hit_rate * 10)))].map((_, i) => (
                            <Star key={i} className="w-3 h-3 text-yellow-500 fill-yellow-500" />
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="text-sm text-terminal-muted">
                      {source.source_type} • {source.metrics.total_calls} calls
                    </div>
                  </div>
                </div>

                {/* Stats */}
                <div className="flex items-center gap-6">
                  <div className="text-center">
                    <div className="text-sm text-terminal-muted">Hit Rate</div>
                    <div className={cn(
                      "font-bold",
                      source.metrics.hit_rate >= 0.5 ? "text-bullish" : "text-bearish"
                    )}>
                      {(source.metrics.hit_rate * 100).toFixed(0)}%
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm text-terminal-muted">Avg Return</div>
                    <div className={cn(
                      "font-bold",
                      source.metrics.avg_return >= 0 ? "text-bullish" : "text-bearish"
                    )}>
                      {source.metrics.avg_return >= 0 ? "+" : ""}
                      {(source.metrics.avg_return * 100).toFixed(0)}%
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm text-terminal-muted">Trust Score</div>
                    <div className="font-bold text-primary-400">
                      {source.scores.trust.toFixed(0)}
                    </div>
                  </div>
                  <ChevronRight className="w-5 h-5 text-terminal-muted" />
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Flagged Sources */}
      {flaggedSources?.flagged?.length > 0 && (
        <div className="bg-terminal-card border border-bearish/30 rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-terminal-border flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-bearish" />
            <h2 className="font-medium text-bearish">Flagged Sources</h2>
          </div>

          <div className="divide-y divide-terminal-border">
            {flaggedSources.flagged.map((source: any) => (
              <div key={source.telegram_id} className="px-6 py-4">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-medium">{source.name}</span>
                    <p className="text-sm text-bearish mt-1">
                      {source.flags.reason}
                    </p>
                  </div>
                  <div className="text-right">
                    <div className="text-sm text-terminal-muted">Hit Rate</div>
                    <div className="font-bold text-bearish">
                      {(source.metrics.hit_rate * 100).toFixed(0)}%
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function LeaderboardSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-8 w-48 bg-terminal-border rounded" />
      <div className="bg-terminal-card border border-terminal-border rounded-xl">
        <div className="px-6 py-4 border-b border-terminal-border">
          <div className="h-5 w-24 bg-terminal-border rounded" />
        </div>
        {[...Array(10)].map((_, i) => (
          <div key={i} className="px-6 py-4 border-b border-terminal-border last:border-0">
            <div className="flex items-center gap-4">
              <div className="w-8 h-8 rounded-full bg-terminal-border" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-32 bg-terminal-border rounded" />
                <div className="h-3 w-24 bg-terminal-border rounded" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
