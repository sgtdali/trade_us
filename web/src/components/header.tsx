"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  BarChart3,
  BookOpenCheck,
  Briefcase,
  CheckCircle2,
  Eye,
  History,
  Layers,
  ListTodo,
  Moon,
  RefreshCw,
  Search,
  Sparkles,
  Sun,
  TrendingUp,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export type NavId =
  | "overview"
  | "ideaRuns"
  | "candidates"
  | "queue"
  | "portfolio"
  | "watchlist"
  | "thesis"
  | "events"
  | "catalog";

interface HeaderProps {
  activeTab: NavId;
  onSelectTab: (id: NavId) => void;
  eventCount?: number;
  queueCount?: number;
  runsCount?: number;
  portfolioCount?: number;
  watchlistCount?: number;
  lastEventAt?: string | null;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  onRefresh: () => void;
  isLoading: boolean;
}

export function Header({
  activeTab,
  onSelectTab,
  eventCount = 0,
  queueCount = 0,
  runsCount = 0,
  portfolioCount = 0,
  watchlistCount = 0,
  lastEventAt,
  searchQuery,
  onSearchChange,
  onRefresh,
  isLoading,
}: HeaderProps) {
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  const NAV_ITEMS: { id: NavId; label: string; icon: React.ComponentType<{ className?: string }>; count?: number }[] = [
    { id: "overview", label: "Genel Bakış", icon: BarChart3 },
    { id: "ideaRuns", label: "Fikir Koşuları", icon: History, count: runsCount },
    { id: "candidates", label: "Adaylar", icon: TrendingUp },
    { id: "queue", label: "İş Kuyruğu", icon: ListTodo, count: queueCount },
    { id: "portfolio", label: "Portföy", icon: Briefcase, count: portfolioCount },
    { id: "watchlist", label: "İzleme Listesi", icon: Eye, count: watchlistCount },
    { id: "thesis", label: "Tez Takibi", icon: BookOpenCheck },
    { id: "events", label: "Olay Günlüğü", icon: Activity, count: eventCount },
    { id: "catalog", label: "Katalog", icon: Layers },
  ];

  return (
    <header className="sticky top-0 z-40 border-b border-border/80 bg-background/95 backdrop-blur-md">
      {/* Top Banner Bar */}
      <div className="flex h-14 items-center justify-between px-4 lg:px-6">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 font-semibold tracking-tight text-foreground">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary border border-primary/20">
              <Sparkles className="h-4 w-4" />
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-bold leading-tight">PEI Terminal</span>
              <span className="text-[10px] font-mono text-muted-foreground">US Market Engine</span>
            </div>
          </div>

          <div className="hidden md:flex items-center gap-2 ml-4 pl-4 border-l border-border/60">
            <Badge variant="outline" className="gap-1.5 border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-medium">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              SEC XBRL Canlı
            </Badge>

            {lastEventAt && (
              <span className="text-xs font-mono text-muted-foreground hidden lg:inline-block">
                Son Olay: {lastEventAt}
              </span>
            )}
          </div>
        </div>

        {/* Global Search & Actions */}
        <div className="flex items-center gap-2">
          <div className="relative w-44 sm:w-64">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="Ticker veya kelime ara..."
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              className="h-8 w-full rounded-md border border-input bg-muted/40 pl-8 pr-3 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring transition-colors"
            />
            {searchQuery && (
              <button
                onClick={() => onSearchChange("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-mono text-muted-foreground hover:text-foreground"
              >
                ESC
              </button>
            )}
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            disabled={isLoading}
            className="h-8 gap-1.5 px-2.5 text-xs border-border/80"
          >
            <RefreshCw className={cn("h-3.5 w-3.5 text-muted-foreground", isLoading && "animate-spin text-primary")} />
            <span className="hidden sm:inline">Yenile</span>
          </Button>

          <Button
            variant="ghost"
            size="icon"
            onClick={toggleTheme}
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            title="Tema Değiştir"
          >
            {theme === "dark" ? <Sun className="h-4 w-4 text-amber-400" /> : <Moon className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      {/* Main Tab Navigation */}
      <div className="flex items-center overflow-x-auto px-4 lg:px-6 border-t border-border/40 scrollbar-none">
        <nav className="flex space-x-1 py-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium transition-all whitespace-nowrap",
                  isActive
                    ? "bg-primary/15 text-primary border border-primary/20 shadow-xs font-semibold"
                    : "text-muted-foreground hover:bg-muted/60 hover:text-foreground border border-transparent",
                )}
              >
                <Icon className={cn("h-3.5 w-3.5", isActive ? "text-primary" : "text-muted-foreground")} />
                <span>{item.label}</span>
                {typeof item.count === "number" && item.count > 0 && (
                  <Badge
                    variant={isActive ? "default" : "secondary"}
                    className={cn(
                      "h-4 min-w-[16px] px-1 text-[10px] font-mono leading-none rounded-full justify-center",
                      isActive ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                    )}
                  >
                    {item.count}
                  </Badge>
                )}
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
