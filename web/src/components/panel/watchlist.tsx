"use client";

import { useState } from "react";
import { toast } from "sonner";
import {
  Bell,
  Bookmark,
  CheckCircle2,
  Edit2,
  Eye,
  Plus,
  Play,
  Sparkles,
  Trash2,
  Target,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { callApi } from "@/lib/api";
import type { WatchlistPayload, WatchlistItem } from "@/lib/types";
import { cn } from "@/lib/utils";

const PRIORITY_BADGES: Record<string, { label: string; className: string }> = {
  A: { label: "Öncelik A (Yüksek)", className: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 font-bold" },
  B: { label: "Öncelik B (Orta)", className: "bg-sky-500/15 text-sky-600 dark:text-sky-400 border-sky-500/30 font-bold" },
  C: { label: "Öncelik C (Düşük)", className: "bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30 font-bold" },
};

export function Watchlist({
  watchlist,
  onChanged,
  searchQuery = "",
}: {
  watchlist: WatchlistPayload | null;
  onChanged: () => void;
  searchQuery?: string;
}) {
  const [showAddModal, setShowAddModal] = useState(false);
  const [busy, setBusy] = useState(false);

  // Form State
  const [ticker, setTicker] = useState("");
  const [targetEntry, setTargetEntry] = useState("");
  const [priority, setPriority] = useState<"A" | "B" | "C">("A");
  const [catalyst, setCatalyst] = useState("");
  const [watchReason, setWatchReason] = useState("");
  const [alertCondition, setAlertCondition] = useState("");

  const items = watchlist?.items ?? [];

  const filteredItems = items.filter((item) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      item.ticker.toLowerCase().includes(q) ||
      (item.catalyst && item.catalyst.toLowerCase().includes(q)) ||
      (item.watch_reason && item.watch_reason.toLowerCase().includes(q))
    );
  });

  const handleOpenEdit = (item: WatchlistItem) => {
    setTicker(item.ticker);
    setTargetEntry(item.target_entry ? item.target_entry.toString() : "");
    setPriority(item.priority || "A");
    setCatalyst(item.catalyst || "");
    setWatchReason(item.watch_reason || "");
    setAlertCondition(item.alert_condition || "");
    setShowAddModal(true);
  };

  const handleSaveItem = async () => {
    if (!ticker.trim()) {
      toast.error("Ticker sembolü zorunludur");
      return;
    }

    setBusy(true);
    try {
      await callApi("/api/watchlist", {
        ticker: ticker.trim().toUpperCase(),
        target_entry: targetEntry ? parseFloat(targetEntry) : null,
        priority: priority,
        catalyst: catalyst.trim(),
        watch_reason: watchReason.trim(),
        alert_condition: alertCondition.trim(),
      });

      toast.success(`${ticker.toUpperCase()} izleme listesine kaydedildi`);
      setShowAddModal(false);
      // Reset form
      setTicker("");
      setTargetEntry("");
      setCatalyst("");
      setWatchReason("");
      setAlertCondition("");
      onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "İzleme öğesi kaydedilemedi");
    } finally {
      setBusy(false);
    }
  };

  const handleDeleteItem = async (t: string) => {
    if (!confirm(`${t} öğesini izleme listesinden çıkarmak istediğinize emin misiniz?`)) return;
    setBusy(true);
    try {
      await fetch("/api/watchlist", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker: t }),
      });
      toast.success(`${t} izleme listesinden silindi`);
      onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Silme başarısız");
    } finally {
      setBusy(false);
    }
  };

  const handleStartIdeaForTicker = async (t: string) => {
    setBusy(true);
    try {
      const data = await callApi<{ run_id: string }>("/api/start-idea", { tickers: [t] });
      toast.success(`${t} için Idea-Generation akışı başlatıldı: ${data.run_id}`);
      onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Idea akışı başlatılamadı");
    } finally {
      setBusy(false);
    }
  };

  const priorityACount = items.filter((i) => i.priority === "A").length;

  return (
    <div className="space-y-6">
      {/* Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Items */}
        <Card className="border-border/80 bg-card/60">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">İzleme Listesi Hisseleri</CardTitle>
            <div className="rounded-md bg-sky-500/10 p-1.5 text-sky-500">
              <Eye className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-mono tracking-tight">{items.length} Hisse</div>
            <div className="mt-1 text-[11px] text-muted-foreground font-mono">
              Takip edilen hedef fiyatlar & katalizörler
            </div>
          </CardContent>
        </Card>

        {/* Priority A Count */}
        <Card className="border-border/80 bg-card/60">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Yüksek Öncelik (A)</CardTitle>
            <div className="rounded-md bg-emerald-500/10 p-1.5 text-emerald-500">
              <Target className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-mono tracking-tight text-emerald-500">{priorityACount} Hisse</div>
            <div className="mt-1 text-[11px] text-muted-foreground">
              Alım fırsatı yakından izlenen isimler
            </div>
          </CardContent>
        </Card>

        {/* Catalysts Tracked */}
        <Card className="border-border/80 bg-card/60">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Katalizör Takibi</CardTitle>
            <div className="rounded-md bg-amber-500/10 p-1.5 text-amber-500">
              <Sparkles className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-mono tracking-tight">
              {items.filter((i) => i.catalyst).length} Katalizör
            </div>
            <div className="mt-1 text-[11px] text-muted-foreground">
              Bilanço veya ürün etkinliği tanımlı
            </div>
          </CardContent>
        </Card>

        {/* Add CTA */}
        <Card className="border-border/80 bg-card/60 flex flex-col justify-between">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">İşlemler</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <Button
              onClick={() => {
                setTicker("");
                setTargetEntry("");
                setCatalyst("");
                setWatchReason("");
                setAlertCondition("");
                setShowAddModal(true);
              }}
              className="w-full gap-1.5 text-xs font-semibold"
            >
              <Plus className="h-4 w-4" /> İzleme Listesine Ekle
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Add / Edit Form Modal */}
      {showAddModal && (
        <Card className="border-primary/40 bg-card/90 shadow-md">
          <CardHeader className="pb-3 border-b border-border/60">
            <CardTitle className="text-sm font-semibold flex items-center justify-between">
              <span>{ticker ? `${ticker} İzleme Kaydını Düzenle` : "İzleme Listesine Yeni Hisse Ekle"}</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowAddModal(false)}
                className="h-7 px-2 text-xs"
              >
                Kapat
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="text-[11px] font-semibold text-muted-foreground">Ticker Symbol *</label>
                <Input
                  placeholder="NVDA"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value)}
                  className="font-mono text-xs uppercase mt-1"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-muted-foreground">Hedef Giriş Fiyatı ($)</label>
                <Input
                  type="number"
                  placeholder="115.00"
                  value={targetEntry}
                  onChange={(e) => setTargetEntry(e.target.value)}
                  className="font-mono text-xs mt-1"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-muted-foreground">Öncelik (Priority)</label>
                <select
                  value={priority}
                  onChange={(e) => setPriority(e.target.value as "A" | "B" | "C")}
                  className="h-9 w-full rounded-md border border-border/80 bg-background px-2 text-xs mt-1"
                >
                  <option value="A">Öncelik A (Yüksek)</option>
                  <option value="B">Öncelik B (Orta)</option>
                  <option value="C">Öncelik C (İzleme)</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] font-semibold text-muted-foreground">Yaklaşan Katalizör / Olay</label>
                <Input
                  placeholder="Örn: Q2 Bilanço (28 Ağustos) veya GTC Etkinliği"
                  value={catalyst}
                  onChange={(e) => setCatalyst(e.target.value)}
                  className="text-xs mt-1"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-muted-foreground">Alarm Koşulu / Tetik</label>
                <Input
                  placeholder="Örn: Fiyat $110 altına inerse veya PE < 30 olursa"
                  value={alertCondition}
                  onChange={(e) => setAlertCondition(e.target.value)}
                  className="text-xs mt-1"
                />
              </div>
            </div>

            <div>
              <label className="text-[11px] font-semibold text-muted-foreground">İzleme Gerekçesi (Watch Reason)</label>
              <Input
                placeholder="Örn: Yüksek büyüme potansiyeli, valuation çekilmesi bekleniyor..."
                value={watchReason}
                onChange={(e) => setWatchReason(e.target.value)}
                className="text-xs mt-1"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" size="sm" onClick={() => setShowAddModal(false)}>
                İptal
              </Button>
              <Button size="sm" onClick={handleSaveItem} disabled={busy} className="gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5" /> Kaydet
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main Watchlist Table */}
      <div className="rounded-lg border border-border/80 overflow-hidden bg-card/60 shadow-xs">
        <Table>
          <TableHeader className="bg-muted/40">
            <TableRow>
              <TableHead className="w-28 font-bold">Ticker</TableHead>
              <TableHead className="w-36">Öncelik</TableHead>
              <TableHead className="w-28 text-right">Güncel Fiyat</TableHead>
              <TableHead className="w-28 text-right">Hedef Giriş</TableHead>
              <TableHead className="w-32 text-right">Hedeften Uzaklık</TableHead>
              <TableHead className="w-48">Katalizör / Olay</TableHead>
              <TableHead>İzleme Gerekçesi / Alarm</TableHead>
              <TableHead className="w-32 text-right">İşlemler</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredItems.map((item) => {
              const badgeCfg = PRIORITY_BADGES[item.priority || "B"] || PRIORITY_BADGES.B;
              const dist = item.distance_to_target_pct;

              return (
                <TableRow key={item.ticker} className="hover:bg-muted/20 border-b border-border/40">
                  <TableCell className="font-bold font-mono text-sm">
                    <span className="text-primary mr-0.5">$</span>
                    {item.ticker}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className={badgeCfg.className}>
                      {item.priority || "B"}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs text-right font-bold text-foreground">
                    {item.current_price ? `$${item.current_price.toFixed(2)}` : "-"}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-right font-semibold text-primary">
                    {item.target_entry ? `$${item.target_entry.toFixed(2)}` : "-"}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-right">
                    {dist !== null && dist !== undefined ? (
                      <span
                        className={cn(
                          "font-bold",
                          dist <= 0 ? "text-emerald-500" : "text-amber-500"
                        )}
                      >
                        {dist <= 0 ? "Hedefte! (" : "+"}
                        {dist}%{dist <= 0 ? ")" : ""}
                      </span>
                    ) : (
                      "-"
                    )}
                  </TableCell>
                  <TableCell className="text-xs font-medium max-w-xs truncate">
                    {item.catalyst || "-"}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground max-w-md truncate">
                    {item.watch_reason || item.alert_condition || "-"}
                  </TableCell>
                  <TableCell className="text-right space-x-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      title="Idea Akışı Başlat"
                      onClick={() => handleStartIdeaForTicker(item.ticker)}
                      className="h-7 w-7 text-sky-500 hover:bg-sky-500/10"
                    >
                      <Play className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleOpenEdit(item)}
                      className="h-7 w-7 text-muted-foreground hover:text-foreground"
                    >
                      <Edit2 className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDeleteItem(item.ticker)}
                      className="h-7 w-7 text-rose-500 hover:bg-rose-500/10"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}

            {filteredItems.length === 0 && (
              <TableRow>
                <TableCell colSpan={8} className="h-32 text-center text-muted-foreground">
                  İzleme listenizde henüz kaydedilmiş bir hisse bulunmuyor.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
