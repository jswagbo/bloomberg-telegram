"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { 
  Users, 
  Trophy,
  TrendingUp,
  MessageSquare,
  Shield,
  Star,
  ExternalLink
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function LeaderboardPage() {
  const { data: stats } = useQuery({
    queryKey: ["feed-stats"],
    queryFn: () => api.getFeedStats(),
    staleTime: 1000 * 60,
  });

  // Mock source data - in production this would come from API
  const sources = [
    { name: "CopeClub", mentions: 156, accuracy: 72, signals: 23, tier: "gold" },
    { name: "monie moves™", mentions: 134, accuracy: 68, signals: 19, tier: "gold" },
    { name: "Manifesting Riches Chat", mentions: 98, accuracy: 65, signals: 15, tier: "silver" },
    { name: "Alpha Hunters", mentions: 87, accuracy: 71, signals: 12, tier: "silver" },
    { name: "Degen Plays", mentions: 76, accuracy: 58, signals: 11, tier: "bronze" },
    { name: "Solana Gems", mentions: 65, accuracy: 62, signals: 9, tier: "bronze" },
    { name: "CT Insiders", mentions: 54, accuracy: 55, signals: 8, tier: "bronze" },
  ];

  const getTierColor = (tier: string) => {
    switch (tier) {
      case "gold": return "text-yellow-400 bg-yellow-400/10";
      case "silver": return "text-gray-300 bg-gray-300/10";
      case "bronze": return "text-orange-400 bg-orange-400/10";
      default: return "text-terminal-muted bg-terminal-border";
    }
  };

  const getTierIcon = (tier: string) => {
    switch (tier) {
      case "gold": return "🥇";
      case "silver": return "🥈";
      case "bronze": return "🥉";
      default: return "📊";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Trophy className="w-6 h-6 text-yellow-400" />
          Source Leaderboard
        </h1>
        <p className="text-terminal-muted mt-1">
          Telegram channels ranked by signal quality and accuracy
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-terminal-card border border-terminal-border rounded-xl p-6">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-lg bg-primary-600/20 flex items-center justify-center">
              <Users className="w-6 h-6 text-primary-400" />
            </div>
            <div>
              <div className="text-2xl font-bold">{stats?.unique_sources || sources.length}</div>
              <div className="text-terminal-muted text-sm">Active Sources</div>
            </div>
          </div>
        </div>
        <div className="bg-terminal-card border border-terminal-border rounded-xl p-6">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-lg bg-bullish/20 flex items-center justify-center">
              <TrendingUp className="w-6 h-6 text-bullish" />
            </div>
            <div>
              <div className="text-2xl font-bold">{stats?.total_mentions || 670}</div>
              <div className="text-terminal-muted text-sm">Total Signals</div>
            </div>
          </div>
        </div>
        <div className="bg-terminal-card border border-terminal-border rounded-xl p-6">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-lg bg-yellow-400/20 flex items-center justify-center">
              <Star className="w-6 h-6 text-yellow-400" />
            </div>
            <div>
              <div className="text-2xl font-bold">64%</div>
              <div className="text-terminal-muted text-sm">Avg Accuracy</div>
            </div>
          </div>
        </div>
      </div>

      {/* Leaderboard Table */}
      <div className="bg-terminal-card border border-terminal-border rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-terminal-border">
          <h2 className="font-bold flex items-center gap-2">
            <Shield className="w-5 h-5 text-primary-400" />
            Top Sources
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-terminal-border">
                <th className="text-left text-sm font-medium text-terminal-muted px-6 py-3">Rank</th>
                <th className="text-left text-sm font-medium text-terminal-muted px-6 py-3">Source</th>
                <th className="text-right text-sm font-medium text-terminal-muted px-6 py-3">Signals</th>
                <th className="text-right text-sm font-medium text-terminal-muted px-6 py-3">Mentions</th>
                <th className="text-right text-sm font-medium text-terminal-muted px-6 py-3">Accuracy</th>
                <th className="text-right text-sm font-medium text-terminal-muted px-6 py-3">Tier</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((source, i) => (
                <motion.tr
                  key={source.name}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="border-b border-terminal-border hover:bg-terminal-border/50 transition-colors"
                >
                  <td className="px-6 py-4">
                    <span className="text-lg">{getTierIcon(source.tier)}</span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-terminal-border flex items-center justify-center font-bold">
                        {source.name[0]}
                      </div>
                      <div>
                        <div className="font-medium">{source.name}</div>
                        <div className="text-xs text-terminal-muted">Telegram Channel</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right font-medium">
                    {source.signals}
                  </td>
                  <td className="px-6 py-4 text-right text-terminal-muted">
                    {source.mentions}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <span className={cn(
                      "font-medium",
                      source.accuracy >= 70 ? "text-bullish" :
                      source.accuracy >= 60 ? "text-yellow-400" :
                      "text-terminal-muted"
                    )}>
                      {source.accuracy}%
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <span className={cn(
                      "px-2 py-1 rounded text-xs font-medium capitalize",
                      getTierColor(source.tier)
                    )}>
                      {source.tier}
                    </span>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Info Card */}
      <div className="bg-terminal-card border border-terminal-border rounded-xl p-6">
        <h3 className="font-bold mb-2">How Sources are Ranked</h3>
        <p className="text-terminal-muted text-sm">
          Sources are ranked based on signal quality, accuracy of calls, 
          consistency, and community trust. Accuracy is measured by comparing 
          price performance 24h after a signal is detected. Tier upgrades require 
          sustained performance over time.
        </p>
      </div>
    </div>
  );
}
