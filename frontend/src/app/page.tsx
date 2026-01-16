"use client";

import { TrendingFeed } from "@/components/feed/trending-feed";

export default function HomePage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <span className="text-fire">🔥</span> Trending Tokens
        </h1>
        <p className="text-terminal-muted mt-1">
          Top trending tokens from DexScreener • Cross-referenced with Telegram discussions
        </p>
      </div>

      {/* Main Feed */}
      <TrendingFeed />
    </div>
  );
}
