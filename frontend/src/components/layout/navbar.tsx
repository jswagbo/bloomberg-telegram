"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  Flame, 
  BarChart3, 
  Users, 
  Settings, 
  Bell,
  Search,
  Menu,
  Command
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useStore } from "@/lib/store";
import { SearchModal } from "@/components/search/search-modal";
import { MobileNav } from "@/components/layout/mobile-nav";

const navItems = [
  { href: "/", label: "Feed", icon: Flame },
  { href: "/leaderboard", label: "Sources", icon: Users },
  { href: "/tokens", label: "Tokens", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Navbar() {
  const pathname = usePathname();
  const { token, logout } = useStore();
  const [searchOpen, setSearchOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  // Keyboard shortcut for search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen(true);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <>
      <nav className="sticky top-0 z-40 border-b border-terminal-border bg-terminal-bg/95 backdrop-blur">
        <div className="container mx-auto px-4">
          <div className="flex h-16 items-center justify-between">
            {/* Logo */}
            <Link href="/" className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center">
                <Flame className="w-5 h-5 text-white" />
              </div>
              <span className="font-bold text-lg hidden sm:block">
                Bloomberg Telegram
              </span>
            </Link>

            {/* Navigation */}
            <div className="hidden md:flex items-center gap-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = pathname === item.href;
                
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-2 px-4 py-2 rounded-lg transition-colors",
                      isActive
                        ? "bg-primary-600/20 text-primary-400"
                        : "text-terminal-muted hover:text-terminal-text hover:bg-terminal-card"
                    )}
                  >
                    <Icon className="w-4 h-4" />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </div>

            {/* Right side */}
            <div className="flex items-center gap-2">
              {/* Search button */}
              <button 
                onClick={() => setSearchOpen(true)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-terminal-card hover:bg-terminal-border transition-colors text-terminal-muted"
              >
                <Search className="w-4 h-4" />
                <span className="hidden sm:inline text-sm">Search...</span>
                <kbd className="hidden sm:flex items-center gap-0.5 px-1.5 py-0.5 text-xs bg-terminal-border rounded">
                  <Command className="w-3 h-3" />K
                </kbd>
              </button>

              {/* Notifications */}
              <button className="p-2 rounded-lg hover:bg-terminal-card transition-colors relative">
                <Bell className="w-5 h-5 text-terminal-muted" />
                <span className="absolute top-1 right-1 w-2 h-2 bg-fire rounded-full" />
              </button>

              {/* Mobile menu */}
              <button 
                onClick={() => setMobileNavOpen(true)}
                className="p-2 rounded-lg hover:bg-terminal-card transition-colors md:hidden"
              >
                <Menu className="w-5 h-5" />
              </button>

              {/* Profile */}
              {token ? (
                <button
                  onClick={() => logout()}
                  className="hidden sm:flex items-center gap-2 px-4 py-2 rounded-lg bg-terminal-card hover:bg-terminal-border transition-colors text-terminal-text font-medium"
                >
                  Sign Out
                </button>
              ) : (
                <Link
                  href="/login"
                  className="hidden sm:flex items-center gap-2 px-4 py-2 rounded-lg bg-primary-600 hover:bg-primary-700 transition-colors text-white font-medium"
                >
                  Sign In
                </Link>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Search Modal */}
      <SearchModal isOpen={searchOpen} onClose={() => setSearchOpen(false)} />
      
      {/* Mobile Nav */}
      <MobileNav isOpen={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />
    </>
  );
}
