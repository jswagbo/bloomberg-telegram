"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Search, X, ArrowRight, Clock, TrendingUp, Loader2 } from "lucide-react";
import { cn, truncateAddress } from "@/lib/utils";

interface SearchResult {
  type: "token" | "recent";
  symbol?: string;
  name?: string;
  address: string;
  chain: string;
  score?: number;
}

interface SearchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SearchModal({ isOpen, onClose }: SearchModalProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  // Recent searches from localStorage
  const [recentSearches, setRecentSearches] = useState<SearchResult[]>([]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("recentTokenSearches");
      if (saved) {
        setRecentSearches(JSON.parse(saved).slice(0, 5));
      }
    }
  }, [isOpen]);

  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus();
      setQuery("");
      setResults([]);
      setSelectedIndex(0);
    }
  }, [isOpen]);

  // Search logic
  const searchTokens = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      setResults([]);
      return;
    }

    setIsLoading(true);
    
    try {
      // Check if it's a contract address
      const isAddress = searchQuery.length >= 32;
      
      if (isAddress) {
        // Detect chain from address format
        const chain = searchQuery.startsWith("0x") ? "base" : "solana";
        setResults([{
          type: "token",
          address: searchQuery,
          chain,
          name: "View Token",
        }]);
      } else {
        // Search by symbol - fetch from API
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/signals/feed?limit=10`
        );
        
        if (response.ok) {
          const signals = await response.json();
          const matches = signals.filter((s: any) => {
            const symbol = s.token?.symbol?.toLowerCase() || "";
            const name = s.token?.name?.toLowerCase() || "";
            const q = searchQuery.toLowerCase();
            return symbol.includes(q) || name.includes(q);
          });
          
          setResults(matches.map((s: any) => ({
            type: "token" as const,
            symbol: s.token.symbol,
            name: s.token.name,
            address: s.token.address,
            chain: s.token.chain,
            score: s.score,
          })));
        }
      }
    } catch (error) {
      console.error("Search error:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      searchTokens(query);
    }, 300);
    return () => clearTimeout(timer);
  }, [query, searchTokens]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;

      const items = query ? results : recentSearches;
      
      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setSelectedIndex(i => Math.min(i + 1, items.length - 1));
          break;
        case "ArrowUp":
          e.preventDefault();
          setSelectedIndex(i => Math.max(i - 1, 0));
          break;
        case "Enter":
          e.preventDefault();
          if (items[selectedIndex]) {
            navigateToToken(items[selectedIndex]);
          } else if (query.length >= 32) {
            // Navigate directly to address
            const chain = query.startsWith("0x") ? "base" : "solana";
            router.push(`/token/${chain}/${query}`);
            onClose();
          }
          break;
        case "Escape":
          onClose();
          break;
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, results, recentSearches, selectedIndex, query, router, onClose]);

  const navigateToToken = (result: SearchResult) => {
    // Save to recent searches
    const newRecent = [result, ...recentSearches.filter(r => r.address !== result.address)].slice(0, 5);
    localStorage.setItem("recentTokenSearches", JSON.stringify(newRecent));
    
    router.push(`/token/${result.chain}/${result.address}`);
    onClose();
  };

  const displayResults = query ? results : recentSearches;

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
          />
          
          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="fixed left-1/2 top-[20%] -translate-x-1/2 w-full max-w-xl z-50 px-4"
          >
            <div className="bg-terminal-card border border-terminal-border rounded-xl shadow-2xl overflow-hidden">
              {/* Search Input */}
              <div className="flex items-center gap-3 px-4 border-b border-terminal-border">
                <Search className="w-5 h-5 text-terminal-muted flex-shrink-0" />
                <input
                  ref={inputRef}
                  type="text"
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setSelectedIndex(0);
                  }}
                  placeholder="Search tokens by symbol or paste address..."
                  className="flex-1 bg-transparent py-4 text-terminal-text placeholder:text-terminal-muted outline-none"
                />
                {isLoading && <Loader2 className="w-5 h-5 text-primary-400 animate-spin" />}
                <button onClick={onClose} className="p-1 hover:bg-terminal-border rounded">
                  <X className="w-5 h-5 text-terminal-muted" />
                </button>
              </div>

              {/* Results */}
              <div className="max-h-80 overflow-y-auto">
                {displayResults.length > 0 ? (
                  <div className="py-2">
                    {!query && recentSearches.length > 0 && (
                      <div className="px-4 py-2 text-xs text-terminal-muted font-medium">
                        Recent Searches
                      </div>
                    )}
                    {displayResults.map((result, index) => (
                      <button
                        key={`${result.address}-${index}`}
                        onClick={() => navigateToToken(result)}
                        className={cn(
                          "w-full flex items-center gap-3 px-4 py-3 transition-colors",
                          selectedIndex === index
                            ? "bg-primary-600/20 text-terminal-text"
                            : "hover:bg-terminal-border text-terminal-muted"
                        )}
                      >
                        <div className="w-10 h-10 rounded-full bg-terminal-border flex items-center justify-center">
                          {result.type === "recent" ? (
                            <Clock className="w-4 h-4" />
                          ) : (
                            <span className="font-bold">{result.symbol?.[0] || "?"}</span>
                          )}
                        </div>
                        <div className="flex-1 text-left">
                          <div className="font-medium text-terminal-text">
                            {result.symbol ? `$${result.symbol}` : truncateAddress(result.address)}
                          </div>
                          <div className="text-xs text-terminal-muted">
                            {result.name || result.chain} {result.score && `• Score: ${result.score.toFixed(0)}`}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={cn(
                            "px-2 py-0.5 rounded text-xs",
                            result.chain === "solana" ? "bg-purple-500/20 text-purple-400" :
                            result.chain === "base" ? "bg-blue-500/20 text-blue-400" :
                            "bg-yellow-500/20 text-yellow-400"
                          )}>
                            {result.chain}
                          </span>
                          <ArrowRight className="w-4 h-4" />
                        </div>
                      </button>
                    ))}
                  </div>
                ) : query && !isLoading ? (
                  <div className="py-8 text-center text-terminal-muted">
                    <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>No tokens found for "{query}"</p>
                    {query.length >= 32 && (
                      <button
                        onClick={() => {
                          const chain = query.startsWith("0x") ? "base" : "solana";
                          router.push(`/token/${chain}/${query}`);
                          onClose();
                        }}
                        className="mt-2 text-primary-400 hover:underline"
                      >
                        View as contract address →
                      </button>
                    )}
                  </div>
                ) : !query ? (
                  <div className="py-8 text-center text-terminal-muted">
                    <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>Search for tokens by symbol</p>
                    <p className="text-sm mt-1">or paste a contract address</p>
                  </div>
                ) : null}
              </div>

              {/* Footer */}
              <div className="px-4 py-2 border-t border-terminal-border flex items-center justify-between text-xs text-terminal-muted">
                <div className="flex items-center gap-4">
                  <span className="flex items-center gap-1">
                    <kbd className="px-1.5 py-0.5 bg-terminal-border rounded">↑↓</kbd>
                    Navigate
                  </span>
                  <span className="flex items-center gap-1">
                    <kbd className="px-1.5 py-0.5 bg-terminal-border rounded">↵</kbd>
                    Select
                  </span>
                  <span className="flex items-center gap-1">
                    <kbd className="px-1.5 py-0.5 bg-terminal-border rounded">esc</kbd>
                    Close
                  </span>
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
