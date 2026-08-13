"use client";

import { Fragment, useState } from "react";
import {
  BookOpenCheck,
  ChevronDown,
  ChevronRight,
  Clock,
  Copy,
  FileText,
  Search,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { ThesisEntry } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ThesisTracker({
  theses,
  searchQuery = "",
}: {
  theses: ThesisEntry[];
  searchQuery?: string;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [localSearch, setLocalSearch] = useState("");

  const query = (searchQuery || localSearch).toLowerCase();

  const filtered = theses.filter((t) => {
    if (!query) return true;
    return (
      t.ticker.toLowerCase().includes(query) ||
      t.thesis_id.toLowerCase().includes(query) ||
      t.file.toLowerCase().includes(query)
    );
  });

  const copyToClipboard = (data: unknown) => {
    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    toast.success("Tez detayları panoya kopyalandı");
  };

  return (
    <div className="space-y-4">
      {/* Search Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-lg border border-border/80 bg-card/60">
        <div className="relative w-72">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Tez ara (Ticker veya Thesis ID)..."
            value={localSearch}
            onChange={(e) => setLocalSearch(e.target.value)}
            className="h-8 pl-8 text-xs bg-muted/30 border-border/60"
          />
        </div>
        <div className="text-xs font-mono text-muted-foreground">
          Toplam Tez Kaydı: <span className="font-bold text-foreground">{filtered.length}</span> / {theses.length}
        </div>
      </div>

      {/* Main Table */}
      <div className="rounded-lg border border-border/80 overflow-hidden bg-card/60 shadow-xs">
        <Table>
          <TableHeader className="bg-muted/40">
            <TableRow>
              <TableHead className="w-10" />
              <TableHead className="w-28 font-bold">Ticker</TableHead>
              <TableHead className="w-48 font-mono">Thesis ID</TableHead>
              <TableHead className="w-32">Kayıt Sayısı</TableHead>
              <TableHead className="w-64">Dosya Yolu</TableHead>
              <TableHead>Son Güncelleme / Olay</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((t) => {
              const key = `${t.ticker}-${t.thesis_id}`;
              const isOpen = expanded === key;
              const last = (t.records[t.records.length - 1] || {}) as {
                event_type?: string;
                recorded_at?: string;
              };

              return (
                <Fragment key={key}>
                  <TableRow
                    onClick={() => setExpanded(isOpen ? null : key)}
                    className={cn(
                      "cursor-pointer transition-colors border-b border-border/40",
                      isOpen ? "bg-muted/40 font-medium" : "hover:bg-muted/20"
                    )}
                  >
                    <TableCell className="text-center p-0 pl-3">
                      {isOpen ? (
                        <ChevronDown className="h-4 w-4 text-primary" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      )}
                    </TableCell>
                    <TableCell className="font-bold font-mono text-sm">
                      <span className="text-primary mr-0.5">$</span>
                      {t.ticker}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-foreground/90">{t.thesis_id}</TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="font-mono text-xs">
                        {t.records.length} Olay
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground max-w-xs truncate">
                      {t.file}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="font-mono text-[10px]">
                          {last.event_type ?? "-"}
                        </Badge>
                        <span className="text-[11px] font-mono text-muted-foreground flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {last.recorded_at ?? "-"}
                        </span>
                      </div>
                    </TableCell>
                  </TableRow>
                  {isOpen && (
                    <TableRow className="hover:bg-transparent">
                      <TableCell colSpan={6} className="p-0 border-b border-border/80">
                        <div className="bg-muted/20 p-5 rounded-b-lg border-x border-b border-border/80 space-y-4">
                          <div className="flex items-center justify-between">
                            <div className="text-xs font-semibold text-foreground flex items-center gap-2">
                              <BookOpenCheck className="h-4 w-4 text-primary" />
                              Tez Geçmişi ({t.records.length} Kayıt)
                            </div>
                            <button
                              onClick={() => copyToClipboard(t.records)}
                              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground font-mono"
                            >
                              <Copy className="h-3.5 w-3.5" /> Tüm Kayıtları Kopyala
                            </button>
                          </div>

                          <div className="space-y-3">
                            {t.records.map((r, i) => (
                              <div
                                key={i}
                                className="rounded-lg border border-border/60 bg-background/80 overflow-hidden shadow-xs"
                              >
                                <div className="bg-muted/40 px-3 py-2 border-b border-border/60 flex items-center justify-between text-xs font-mono">
                                  <span className="font-semibold text-primary">
                                    Adım #{i + 1} - {(r as { event_type?: string }).event_type || "Olay"}
                                  </span>
                                  <span className="text-muted-foreground text-[11px]">
                                    {(r as { recorded_at?: string }).recorded_at}
                                  </span>
                                </div>
                                <ScrollArea className="h-44 p-3">
                                  <pre className="font-mono text-xs text-foreground/90 whitespace-pre-wrap">
                                    {JSON.stringify(r, null, 2)}
                                  </pre>
                                </ScrollArea>
                              </div>
                            ))}
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              );
            })}

            {filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
                  Tez kaydı bulunamadı.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
