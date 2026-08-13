"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Play, RefreshCw, Sparkles } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { WorkItemDetail } from "@/components/panel/work-queue";
import { callApi } from "@/lib/api";
import type { NextItem, RunSummary, UniverseMember } from "@/lib/types";

const STATE_LABEL: Record<string, string> = {
  waiting_for_result: "ChatGPT sonucu bekleniyor",
  result_attached: "Sonuç bağlandı",
  screen_recorded: "Tarama kaydedildi",
};

const STATE_VARIANT: Record<string, "default" | "secondary" | "outline"> = {
  waiting_for_result: "outline",
  result_attached: "secondary",
  screen_recorded: "default",
};

function runToItem(r: RunSummary): NextItem {
  return {
    run_id: r.run_id,
    ticker: r.run_id,
    bucket: null,
    workflow: "idea",
    requested_workflow: "idea",
    reason: STATE_LABEL[r.state] ?? r.state,
    action: "attach_result",
    artifact_dir: r.artifact_dir ?? undefined,
  };
}

export function IdeaRuns({ runs, onChanged }: { runs: RunSummary[]; onChanged: () => void }) {
  const [activeItem, setActiveItem] = useState<NextItem | null>(null);

  const [universe, setUniverse] = useState<UniverseMember[]>([]);
  const [universeFilter, setUniverseFilter] = useState("");
  const [tickers, setTickers] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    callApi<{ members: UniverseMember[] }>("/api/universe")
      .then((data) => setUniverse(data.members))
      .catch(() => undefined);
  }, []);

  const selectedTickers = tickers
    .split(",")
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean);

  const toggleTicker = (t: string) => {
    const list = selectedTickers.includes(t)
      ? selectedTickers.filter((x) => x !== t)
      : [...selectedTickers, t];
    setTickers(list.join(", "));
  };

  const filteredUniverse = universe.filter((m) => {
    const q = universeFilter.trim().toUpperCase();
    if (!q) return true;
    return m.ticker.includes(q) || m.name.toUpperCase().includes(q) || m.sector.toUpperCase().includes(q);
  });

  const runStartIdea = async () => {
    if (!selectedTickers.length) {
      toast.error("Lütfen en az bir hisse sembolü seçin");
      return;
    }
    setBusy(true);
    try {
      const data = await callApi<{ run_id: string; artifact_dir: string }>("/api/start-idea", {
        tickers: selectedTickers,
      });
      toast.success(`Akış başlatıldı: ${data.run_id}`);
      setTickers("");
      setActiveItem({
        run_id: data.run_id,
        ticker: data.run_id,
        bucket: null,
        workflow: "idea",
        requested_workflow: "idea",
        reason: "idea-generation pack hazır; ChatGPT sonucu bekleniyor",
        action: "attach_result",
        artifact_dir: data.artifact_dir,
      });
      onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Fikir başlatma başarısız oldu");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card className="border-border/80 bg-card/60">
        <CardHeader>
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            Yeni Idea-Generation Başlat
          </CardTitle>
          <CardDescription className="text-xs">
            SEC verilerini çekip taramak istediğiniz ABD hisse ticker&apos;larını girin.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input
            placeholder="Evrende ara: ticker, isim veya sektör"
            value={universeFilter}
            onChange={(e) => setUniverseFilter(e.target.value)}
            className="text-xs"
          />

          <ScrollArea className="h-48 rounded-md border border-border/80">
            <div className="p-1">
              {filteredUniverse.map((m) => {
                const checked = selectedTickers.includes(m.ticker);
                return (
                  <label
                    key={m.ticker}
                    className="flex items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-muted/40 cursor-pointer"
                  >
                    <input type="checkbox" checked={checked} onChange={() => toggleTicker(m.ticker)} />
                    <span className="font-mono font-medium w-14 shrink-0">{m.ticker}</span>
                    <span className="text-muted-foreground truncate flex-1">{m.name}</span>
                    <span className="text-[10px] text-muted-foreground/70">{m.sector}</span>
                  </label>
                );
              })}
              {universe.length > 0 && filteredUniverse.length === 0 && (
                <div className="px-2 py-3 text-xs text-muted-foreground">eşleşme yok</div>
              )}
            </div>
          </ScrollArea>

          <div className="flex gap-2">
            <Input
              placeholder="Seçilenler (elle de düzenleyebilirsiniz)"
              value={tickers}
              onChange={(e) => setTickers(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runStartIdea()}
              className="font-mono text-xs uppercase"
            />
            <Button onClick={runStartIdea} disabled={busy} className="gap-1.5 px-4">
              {busy ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
              Başlat
            </Button>
          </div>
          <div className="text-[11px] text-muted-foreground">{selectedTickers.length} seçili</div>
        </CardContent>
      </Card>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Run ID</TableHead>
            <TableHead>Ticker sayısı</TableHead>
            <TableHead>Durum</TableHead>
            <TableHead>Son olay</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {runs.map((r) => (
            <TableRow
              key={r.run_id}
              className="cursor-pointer"
              onClick={() => setActiveItem(runToItem(r))}
            >
              <TableCell className="font-mono text-xs">{r.run_id}</TableCell>
              <TableCell>{r.tickers.length}</TableCell>
              <TableCell>
                <Badge variant={STATE_VARIANT[r.state] ?? "outline"}>
                  {STATE_LABEL[r.state] ?? r.state}
                </Badge>
              </TableCell>
              <TableCell className="font-mono text-xs text-muted-foreground">
                {r.last_event_at}
              </TableCell>
            </TableRow>
          ))}
          {runs.length === 0 && (
            <TableRow>
              <TableCell colSpan={4} className="text-center text-muted-foreground">
                -
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {activeItem && <WorkItemDetail item={activeItem} onDone={onChanged} />}
    </div>
  );
}
