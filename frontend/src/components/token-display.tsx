"use client";

import { useState, useEffect } from "react";
import { Copy, Check } from "lucide-react";
import { truncateAddress } from "@/lib/utils";

// Token info cache for displaying names
const tokenInfoCache: Record<string, { symbol: string; name: string } | null> = {};

// Fetch token info from DexScreener
async function fetchTokenInfo(chain: string, address: string): Promise<{ symbol: string; name: string } | null> {
  const cacheKey = `${chain}:${address}`;
  if (cacheKey in tokenInfoCache) {
    return tokenInfoCache[cacheKey];
  }
  
  try {
    const response = await fetch(`https://api.dexscreener.com/latest/dex/tokens/${address}`);
    if (!response.ok) return null;
    
    const data = await response.json();
    if (data.pairs && data.pairs.length > 0) {
      const pair = data.pairs[0];
      const info = {
        symbol: pair.baseToken?.symbol || "",
        name: pair.baseToken?.name || "",
      };
      tokenInfoCache[cacheKey] = info;
      return info;
    }
    tokenInfoCache[cacheKey] = null;
    return null;
  } catch {
    tokenInfoCache[cacheKey] = null;
    return null;
  }
}

interface TokenDisplayProps {
  symbol?: string;
  address?: string;
  chain: string;
  showChainBadge?: boolean;
  showCopyButton?: boolean;
  showName?: boolean;
  size?: "sm" | "md" | "lg";
  chainBadgeClass?: string;
}

export function TokenDisplay({ 
  symbol, 
  address, 
  chain,
  showChainBadge = true,
  showCopyButton = true,
  showName = true,
  size = "md",
  chainBadgeClass,
}: TokenDisplayProps) {
  const [tokenInfo, setTokenInfo] = useState<{ symbol: string; name: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Only fetch if we don't have a symbol and have an address
    if (!symbol && address && address.length > 20) {
      setLoading(true);
      fetchTokenInfo(chain, address)
        .then(setTokenInfo)
        .finally(() => setLoading(false));
    }
  }, [symbol, address, chain]);

  const displaySymbol = symbol || tokenInfo?.symbol;
  const displayName = tokenInfo?.name;

  const copyAddress = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (address) {
      navigator.clipboard.writeText(address);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const textSizeClass = {
    sm: "text-sm",
    md: "text-base",
    lg: "text-lg",
  }[size];

  const badgeSizeClass = {
    sm: "text-xs px-1.5 py-0.5",
    md: "text-xs px-2 py-0.5",
    lg: "text-sm px-2 py-1",
  }[size];

  return (
    <div>
      <div className="flex items-center gap-2">
        <span className={`font-medium ${textSizeClass}`}>
          {displaySymbol ? (
            `$${displaySymbol}`
          ) : loading ? (
            <span className="text-terminal-muted">Loading...</span>
          ) : (
            truncateAddress(address || "")
          )}
        </span>
        {showChainBadge && (
          <span className={`rounded bg-terminal-border text-terminal-muted ${badgeSizeClass} ${chainBadgeClass || ""}`}>
            {chain}
          </span>
        )}
        {showCopyButton && address && (
          <button
            onClick={copyAddress}
            className="p-1 hover:bg-terminal-border rounded transition-colors"
            title={copied ? "Copied!" : "Copy address"}
          >
            {copied ? (
              <Check className="w-3 h-3 text-bullish" />
            ) : (
              <Copy className="w-3 h-3 text-terminal-muted" />
            )}
          </button>
        )}
      </div>
      {showName && displayName && (
        <div className="text-sm text-terminal-muted">{displayName}</div>
      )}
    </div>
  );
}

// Export the fetch function for use in other components
export { fetchTokenInfo };
