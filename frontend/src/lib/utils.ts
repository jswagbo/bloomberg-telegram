import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(num: number, decimals: number = 2): string {
  if (num >= 1_000_000_000) {
    return `${(num / 1_000_000_000).toFixed(decimals)}B`;
  }
  if (num >= 1_000_000) {
    return `${(num / 1_000_000).toFixed(decimals)}M`;
  }
  if (num >= 1_000) {
    return `${(num / 1_000).toFixed(decimals)}K`;
  }
  return num.toFixed(decimals);
}

export function formatPrice(price: number): string {
  if (price < 0.00001) {
    return price.toExponential(2);
  }
  if (price < 1) {
    return price.toFixed(6);
  }
  if (price < 100) {
    return price.toFixed(4);
  }
  return formatNumber(price, 2);
}

export function formatPercent(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function truncateAddress(address: string, chars: number = 4): string {
  if (!address) return "";
  return `${address.slice(0, chars)}...${address.slice(-chars)}`;
}

export function getChainExplorerUrl(chain: string, address: string): string {
  switch (chain) {
    case "solana":
      return `https://solscan.io/token/${address}`;
    case "base":
      return `https://basescan.org/token/${address}`;
    case "bsc":
      return `https://bscscan.com/token/${address}`;
    case "ethereum":
      return `https://etherscan.io/token/${address}`;
    default:
      return "";
  }
}

export function getDexScreenerUrl(chain: string, address: string): string {
  return `https://dexscreener.com/${chain}/${address}`;
}
