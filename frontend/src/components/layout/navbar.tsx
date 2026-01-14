"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  Flame, 
  BarChart3, 
  Users, 
  Settings, 
  Bell,
  Search,
  Menu
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Feed", icon: Flame },
  { href: "/leaderboard", label: "Sources", icon: Users },
  { href: "/tokens", label: "Tokens", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Navbar() {
  const pathname = usePathname();

  return (
    <nav className="sticky top-0 z-50 border-b border-terminal-border bg-terminal-bg/95 backdrop-blur">
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
            {/* Search */}
            <button className="p-2 rounded-lg hover:bg-terminal-card transition-colors">
              <Search className="w-5 h-5 text-terminal-muted" />
            </button>

            {/* Notifications */}
            <button className="p-2 rounded-lg hover:bg-terminal-card transition-colors relative">
              <Bell className="w-5 h-5 text-terminal-muted" />
              <span className="absolute top-1 right-1 w-2 h-2 bg-fire rounded-full" />
            </button>

            {/* Mobile menu */}
            <button className="p-2 rounded-lg hover:bg-terminal-card transition-colors md:hidden">
              <Menu className="w-5 h-5" />
            </button>

            {/* Profile */}
            <Link
              href="/login"
              className="hidden sm:flex items-center gap-2 px-4 py-2 rounded-lg bg-primary-600 hover:bg-primary-700 transition-colors text-white font-medium"
            >
              Sign In
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
}
