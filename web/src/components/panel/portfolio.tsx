"use client";

import { useState } from "react";
import { toast } from "sonner";
import {
  ArrowDownRight,
  ArrowUpRight,
  Briefcase,
  DollarSign,
  Plus,
  Trash2,
  TrendingDown,
  TrendingUp,
  Edit2,
  CheckCircle2,
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
import type { PortfolioPayload, PortfolioPosition } from "@/lib/types";
import { cn } from "@/lib/utils";

export function Portfolio({
  portfolio,
  onChanged,
  searchQuery = "",
}: {
  portfolio: PortfolioPayload | null;
  onChanged: () => void;
  searchQuery?: string;
}) {
  const [showAddModal, setShowAddModal] = useState(false);
  const [busy, setBusy] = useState(false);

  // Form State
  const [ticker, setTicker] = useState("");
  const [shares, setShares] = useState("");
  const [avgCost, setAvgCost] = useState("");
  const [targetPrice, setTargetPrice] = useState("");
  const [stopLoss, setStopLoss] = useState("");
  const [positionType, setPositionType] = useState<"Long" | "Short">("Long");
  const [conviction, setConviction] = useState<"High" | "Medium" | "Low">("High");
  const [notes, setNotes] = useState("");

  const positions = portfolio?.positions ?? [];

  const filteredPositions = positions.filter((p) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return p.ticker.toLowerCase().includes(q) || (p.notes && p.notes.toLowerCase().includes(q));
  });

  const handleOpenEdit = (p: PortfolioPosition) => {
    setTicker(p.ticker);
    setShares(p.shares.toString());
    setAvgCost(p.avg_cost.toString());
    setTargetPrice(p.target_price ? p.target_price.toString() : "");
    setStopLoss(p.stop_loss ? p.stop_loss.toString() : "");
    setPositionType(p.position_type || "Long");
    setConviction(p.conviction || "High");
    setNotes(p.notes || "");
    setShowAddModal(true);
  };

  const handleSavePosition = async () => {
    if (!ticker.trim()) {
      toast.error("Ticker sembolü zorunludur");
      return;
    }
    if (!shares || parseFloat(shares) <= 0) {
      toast.error("Hisse adedi 0'dan büyük olmalıdır");
      return;
    }
    if (!avgCost || parseFloat(avgCost) < 0) {
      toast.error("Maliyet pozitif bir sayı olmalıdır");
      return;
    }

    setBusy(true);
    try {
      await callApi("/api/portfolio", {
        ticker: ticker.trim().toUpperCase(),
        shares: parseFloat(shares),
        avg_cost: parseFloat(avgCost),
        target_price: targetPrice ? parseFloat(targetPrice) : null,
        stop_loss: stopLoss ? parseFloat(stopLoss) : null,
        position_type: positionType,
        conviction: conviction,
        notes: notes.trim(),
      });

      toast.success(`${ticker.toUpperCase()} pozisyonu kaydedildi`);
      setShowAddModal(false);
      // Reset form
      setTicker("");
      setShares("");
      setAvgCost("");
      setTargetPrice("");
      setStopLoss("");
      setNotes("");
      onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Pozisyon kaydedilemedi");
    } finally {
      setBusy(false);
    }
  };

  const handleDeletePosition = async (t: string) => {
    if (!confirm(`${t} pozisyonunu silmek istediğinize emin misiniz?`)) return;
    setBusy(true);
    try {
      await fetch("/api/portfolio", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker: t }),
      });
      toast.success(`${t} pozisyonu silindi`);
      onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Silme başarısız");
    } finally {
      setBusy(false);
    }
  };

  const isProfit = (portfolio?.total_pnl ?? 0) >= 0;

  return (
    <div className="space-y-6">
      {/* Portfolio Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Value */}
        <Card className="border-border/80 bg-card/60">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Portföy Değeri</CardTitle>
            <div className="rounded-md bg-primary/10 p-1.5 text-primary">
              <Briefcase className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-mono tracking-tight">
              ${(portfolio?.total_value ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </div>
            <div className="mt-1 text-[11px] text-muted-foreground font-mono">
              Maliyet: ${(portfolio?.total_cost ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </div>
          </CardContent>
        </Card>

        {/* Total PnL */}
        <Card className="border-border/80 bg-card/60">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Kâr / Zarar (Unrealized P&L)</CardTitle>
            <div
              className={cn(
                "rounded-md p-1.5",
                isProfit ? "bg-emerald-500/10 text-emerald-500" : "bg-rose-500/10 text-rose-500"
              )}
            >
              {isProfit ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
            </div>
          </CardHeader>
          <CardContent>
            <div className={cn("text-2xl font-bold font-mono tracking-tight flex items-center gap-1", isProfit ? "text-emerald-500" : "text-rose-500")}>
              {isProfit ? "+" : ""}
              ${(portfolio?.total_pnl ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </div>
            <div className={cn("mt-1 text-[11px] font-mono font-semibold flex items-center gap-1", isProfit ? "text-emerald-500" : "text-rose-500")}>
              {isProfit ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
              {isProfit ? "+" : ""}
              {portfolio?.total_pnl_pct ?? 0}% Toplam Getiri
            </div>
          </CardContent>
        </Card>

        {/* Position Count */}
        <Card className="border-border/80 bg-card/60">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Aktif Pozisyonlar</CardTitle>
            <div className="rounded-md bg-sky-500/10 p-1.5 text-sky-500">
              <DollarSign className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-mono tracking-tight">{positions.length} Hissede</div>
            <div className="mt-1 text-[11px] text-muted-foreground">
              {positions.filter((p) => p.position_type === "Long").length} Long • {positions.filter((p) => p.position_type === "Short").length} Short
            </div>
          </CardContent>
        </Card>

        {/* Add Position CTA */}
        <Card className="border-border/80 bg-card/60 flex flex-col justify-between">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">İşlemler</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <Button
              onClick={() => {
                setTicker("");
                setShares("");
                setAvgCost("");
                setTargetPrice("");
                setStopLoss("");
                setNotes("");
                setShowAddModal(true);
              }}
              className="w-full gap-1.5 text-xs font-semibold"
            >
              <Plus className="h-4 w-4" /> Pozisyon Ekle
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Add / Edit Position Form Modal / Panel */}
      {showAddModal && (
        <Card className="border-primary/40 bg-card/90 shadow-md">
          <CardHeader className="pb-3 border-b border-border/60">
            <CardTitle className="text-sm font-semibold flex items-center justify-between">
              <span>{ticker ? `${ticker} Pozisyonunu Düzenle` : "Yeni Pozisyon Ekle"}</span>
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
                  placeholder="AAPL"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value)}
                  className="font-mono text-xs uppercase mt-1"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-muted-foreground">Hisse Adedi (Shares) *</label>
                <Input
                  type="number"
                  placeholder="10"
                  value={shares}
                  onChange={(e) => setShares(e.target.value)}
                  className="font-mono text-xs mt-1"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-muted-foreground">Ort. Maliyet ($) *</label>
                <Input
                  type="number"
                  placeholder="150.50"
                  value={avgCost}
                  onChange={(e) => setAvgCost(e.target.value)}
                  className="font-mono text-xs mt-1"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
              <div>
                <label className="text-[11px] font-semibold text-muted-foreground">Hedef Fiyat ($)</label>
                <Input
                  type="number"
                  placeholder="200.00"
                  value={targetPrice}
                  onChange={(e) => setTargetPrice(e.target.value)}
                  className="font-mono text-xs mt-1"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-muted-foreground">Stop Loss ($)</label>
                <Input
                  type="number"
                  placeholder="135.00"
                  value={stopLoss}
                  onChange={(e) => setStopLoss(e.target.value)}
                  className="font-mono text-xs mt-1"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-muted-foreground">Yön (Position Type)</label>
                <select
                  value={positionType}
                  onChange={(e) => setPositionType(e.target.value as "Long" | "Short")}
                  className="h-9 w-full rounded-md border border-border/80 bg-background px-2 text-xs mt-1"
                >
                  <option value="Long">Long (Alım)</option>
                  <option value="Short">Short (Satım)</option>
                </select>
              </div>

              <div>
                <label className="text-[11px] font-semibold text-muted-foreground">İnanç (Conviction)</label>
                <select
                  value={conviction}
                  onChange={(e) => setConviction(e.target.value as "High" | "Medium" | "Low")}
                  className="h-9 w-full rounded-md border border-border/80 bg-background px-2 text-xs mt-1"
                >
                  <option value="High">High (Yüksek)</option>
                  <option value="Medium">Medium (Orta)</option>
                  <option value="Low">Low (Düşük)</option>
                </select>
              </div>
            </div>

            <div>
              <label className="text-[11px] font-semibold text-muted-foreground">Yatırım Notu / Tez Gerekçesi</label>
              <Input
                placeholder="Örn: 10-Q sonrası RPO artışı beklentisi ile açıldı..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="text-xs mt-1"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" size="sm" onClick={() => setShowAddModal(false)}>
                İptal
              </Button>
              <Button size="sm" onClick={handleSavePosition} disabled={busy} className="gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5" /> Kaydet
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main Positions Table */}
      <div className="rounded-lg border border-border/80 overflow-hidden bg-card/60 shadow-xs">
        <Table>
          <TableHeader className="bg-muted/40">
            <TableRow>
              <TableHead className="w-28 font-bold">Ticker</TableHead>
              <TableHead className="w-20">Yön</TableHead>
              <TableHead className="w-24">İnanç</TableHead>
              <TableHead className="w-24 text-right">Aded</TableHead>
              <TableHead className="w-28 text-right">Ort. Maliyet</TableHead>
              <TableHead className="w-28 text-right">Güncel Fiyat</TableHead>
              <TableHead className="w-32 text-right">Piyasa Değeri</TableHead>
              <TableHead className="w-36 text-right">Kâr / Zarar ($ & %)</TableHead>
              <TableHead className="w-36">Hedef / Stop</TableHead>
              <TableHead className="w-24 text-right">İşlemler</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredPositions.map((p) => {
              const pnl = p.unrealized_pnl ?? 0;
              const pnlPct = p.unrealized_pnl_pct ?? 0;
              const posProfit = pnl >= 0;

              return (
                <TableRow key={p.ticker} className="hover:bg-muted/20 border-b border-border/40">
                  <TableCell className="font-bold font-mono text-sm">
                    <span className="text-primary mr-0.5">$</span>
                    {p.ticker}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={p.position_type === "Long" ? "default" : "secondary"}
                      className="font-mono text-[10px]"
                    >
                      {p.position_type || "Long"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {p.conviction || "Medium"}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs text-right font-medium">{p.shares}</TableCell>
                  <TableCell className="font-mono text-xs text-right">${p.avg_cost.toFixed(2)}</TableCell>
                  <TableCell className="font-mono text-xs text-right font-bold text-foreground">
                    ${(p.current_price ?? p.avg_cost).toFixed(2)}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-right font-semibold">
                    ${(p.market_value ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-right">
                    <div className={cn("font-bold flex items-center justify-end gap-0.5", posProfit ? "text-emerald-500" : "text-rose-500")}>
                      {posProfit ? "+" : ""}
                      ${pnl.toFixed(2)}
                    </div>
                    <div className={cn("text-[10px]", posProfit ? "text-emerald-500" : "text-rose-500")}>
                      ({posProfit ? "+" : ""}
                      {pnlPct.toFixed(2)}%)
                    </div>
                  </TableCell>
                  <TableCell className="font-mono text-[11px] text-muted-foreground">
                    <div>T: {p.target_price ? `$${p.target_price.toFixed(2)}` : "-"}</div>
                    <div>S: {p.stop_loss ? `$${p.stop_loss.toFixed(2)}` : "-"}</div>
                  </TableCell>
                  <TableCell className="text-right space-x-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleOpenEdit(p)}
                      className="h-7 w-7 text-muted-foreground hover:text-foreground"
                    >
                      <Edit2 className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDeletePosition(p.ticker)}
                      className="h-7 w-7 text-rose-500 hover:bg-rose-500/10"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}

            {filteredPositions.length === 0 && (
              <TableRow>
                <TableCell colSpan={10} className="h-32 text-center text-muted-foreground">
                  Portföyünüzde henüz kaydedilmiş bir pozisyon bulunmuyor.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
