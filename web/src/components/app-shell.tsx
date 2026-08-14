"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  AlertCircle,
  BarChart3,
  BookOpenCheck,
  Briefcase,
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
import { useAppData } from "@/lib/app-data";

interface NavLeaf {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  count?: number;
}

interface NavGroup {
  title: string;
  items: NavLeaf[];
}

// Operasyon merkezi bu grupları temel alır: ARAŞTIRMA = tarama->kuyruk->
// şirket akışı (günlük iş), PORTFÖY = pozisyon yönetimi, SİSTEM = denetim/
// makine görünümü. Önceki tasarımda hepsi tek düz sekme sırasındaydı; burada
// işlev bazlı ayrım fiziksel olarak da (bölüm başlıklarıyla) görünür.
function useNavGroups(): NavGroup[] {
  const { status, portfolio, watchlist } = useAppData();
  return [
    {
      title: "Araştırma",
      items: [
        { href: "/", label: "Genel Bakış", icon: BarChart3 },
        { href: "/screening", label: "Fikir Taraması", icon: History, count: status?.runs.length },
        { href: "/queue", label: "Çalışma Kuyruğu", icon: ListTodo, count: status?.next.length },
        { href: "/companies", label: "Şirketler", icon: TrendingUp, count: status?.candidates.length },
      ],
    },
    {
      title: "Portföy",
      items: [
        { href: "/portfolio", label: "Portföy", icon: Briefcase, count: portfolio?.positions.length },
        { href: "/watchlist", label: "İzleme Listesi", icon: Eye, count: watchlist?.items.length },
        { href: "/thesis", label: "Tez Takibi", icon: BookOpenCheck },
      ],
    },
    {
      title: "Sistem",
      items: [
        { href: "/system/events", label: "Olay Günlüğü", icon: Activity, count: status?.event_count },
        { href: "/system/catalog", label: "Katalog", icon: Layers },
      ],
    },
  ];
}

function Sidebar({ pathname }: { pathname: string }) {
  const groups = useNavGroups();
  return (
    <aside className="hidden lg:flex w-60 shrink-0 flex-col border-r border-border/80 bg-card/40 h-[calc(100vh-3.5rem)] sticky top-14 overflow-y-auto">
      <nav className="flex-1 px-3 py-4 space-y-6">
        {groups.map((group) => (
          <div key={group.title} className="space-y-1">
            <div className="px-2.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">
              {group.title}
            </div>
            {group.items.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors",
                    isActive
                      ? "bg-primary/15 text-primary border border-primary/20 font-semibold"
                      : "text-muted-foreground hover:bg-muted/60 hover:text-foreground border border-transparent"
                  )}
                >
                  <Icon className={cn("h-3.5 w-3.5 shrink-0", isActive ? "text-primary" : "text-muted-foreground")} />
                  <span className="flex-1">{item.label}</span>
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
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
    </aside>
  );
}

function TopBar() {
  const { status, isLoading, refresh, searchQuery, setSearchQuery } = useAppData();
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
  }, [theme]);

  return (
    <header className="sticky top-0 z-40 h-14 border-b border-border/80 bg-background/95 backdrop-blur-md flex items-center justify-between px-4 lg:px-6">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 font-semibold tracking-tight text-foreground">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary border border-primary/20">
            <Sparkles className="h-4 w-4" />
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-bold leading-tight">PEI Operasyon Merkezi</span>
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
          {status?.last_event_at && (
            <span className="text-xs font-mono text-muted-foreground hidden xl:inline-block">
              Son Olay: {status.last_event_at}
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <div className="relative w-44 sm:w-64">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Ticker veya kelime ara..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-8 w-full rounded-md border border-input bg-muted/40 pl-8 pr-3 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring transition-colors"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-mono text-muted-foreground hover:text-foreground"
            >
              ESC
            </button>
          )}
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={refresh}
          disabled={isLoading}
          className="h-8 gap-1.5 px-2.5 text-xs border-border/80"
        >
          <RefreshCw className={cn("h-3.5 w-3.5 text-muted-foreground", isLoading && "animate-spin text-primary")} />
          <span className="hidden sm:inline">Yenile</span>
        </Button>

        <Button
          variant="ghost"
          size="icon"
          onClick={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))}
          className="h-8 w-8 text-muted-foreground hover:text-foreground"
          title="Tema Değiştir"
        >
          {theme === "dark" ? <Sun className="h-4 w-4 text-amber-400" /> : <Moon className="h-4 w-4" />}
        </Button>
      </div>
    </header>
  );
}

function MobileNav({ pathname }: { pathname: string }) {
  const groups = useNavGroups();
  const items = groups.flatMap((g) => g.items);
  return (
    <div className="lg:hidden flex items-center overflow-x-auto px-4 border-b border-border/40 scrollbar-none">
      <nav className="flex space-x-1 py-1.5">
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium whitespace-nowrap",
                isActive
                  ? "bg-primary/15 text-primary border border-primary/20 font-semibold"
                  : "text-muted-foreground hover:bg-muted/60 border border-transparent"
              )}
            >
              <Icon className="h-3.5 w-3.5 shrink-0" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { error } = useAppData();

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      <TopBar />
      <MobileNav pathname={pathname} />
      <div className="flex flex-1 min-h-0">
        <Sidebar pathname={pathname} />
        <main className="flex-1 min-w-0 p-4 sm:p-6 lg:p-8 max-w-6xl mx-auto w-full space-y-6">
          {error && (
            <div className="flex items-center gap-2 p-4 rounded-lg border border-rose-500/40 bg-rose-500/10 text-rose-600 dark:text-rose-400 text-xs font-medium">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>Sistem Hatası: {error}</span>
            </div>
          )}
          {children}
        </main>
      </div>
    </div>
  );
}
