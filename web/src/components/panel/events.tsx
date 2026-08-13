"use client";

import { Fragment, useState } from "react";
import {
  Activity,
  ChevronDown,
  ChevronRight,
  Clock,
  Copy,
  Filter,
  Search,
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
import type { WorkflowEvent } from "@/lib/types";
import { cn } from "@/lib/utils";

const EVENT_TYPE_STYLES: Record<string, string> = {
  idea_started: "bg-sky-500/15 text-sky-600 dark:text-sky-400 border-sky-500/30",
  trigger_matched: "bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30",
  workflow_completed: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30",
  draft_approved: "bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 border-indigo-500/30",
  rejected: "bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30",
};

export function EventLog({
  events,
  searchQuery = "",
}: {
  events: WorkflowEvent[];
  searchQuery?: string;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [localQuery, setLocalQuery] = useState("");

  const query = (searchQuery || localQuery).toLowerCase();

  const filteredEvents = events.filter((e) => {
    if (!query) return true;
    return (
      e.event_type.toLowerCase().includes(query) ||
      (e.ticker && e.ticker.toLowerCase().includes(query)) ||
      e.run_id.toLowerCase().includes(query) ||
      e.event_id.toLowerCase().includes(query)
    );
  });

  const copyEventJson = (e: WorkflowEvent) => {
    navigator.clipboard.writeText(JSON.stringify(e, null, 2));
    toast.success("Olay verisi panoya kopyalandı");
  };

  return (
    <div className="space-y-4">
      {/* Search Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-lg border border-border/80 bg-card/60">
        <div className="relative w-72">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Olay ara (Olay tipi, Ticker, Run ID)..."
            value={localQuery}
            onChange={(e) => setLocalQuery(e.target.value)}
            className="h-8 pl-8 text-xs bg-muted/30 border-border/60"
          />
        </div>
        <div className="text-xs font-mono text-muted-foreground">
          Gösterilen Olaylar: <span className="font-bold text-foreground">{filteredEvents.length}</span> / {events.length}
        </div>
      </div>

      {/* Main Events Table */}
      <div className="rounded-lg border border-border/80 overflow-hidden bg-card/60 shadow-xs">
        <Table>
          <TableHeader className="bg-muted/40">
            <TableRow>
              <TableHead className="w-10" />
              <TableHead className="w-44 font-mono">Zaman Damgası</TableHead>
              <TableHead className="w-48">Olay Tipi</TableHead>
              <TableHead className="w-28 font-bold">Ticker</TableHead>
              <TableHead className="w-44 font-mono">Run ID</TableHead>
              <TableHead className="font-mono">Event ID</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredEvents.map((e) => {
              const isOpen = expanded === e.event_id;
              const badgeStyle = EVENT_TYPE_STYLES[e.event_type] || "bg-muted text-muted-foreground border-border";

              return (
                <Fragment key={e.event_id}>
                  <TableRow
                    onClick={() => setExpanded(isOpen ? null : e.event_id)}
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
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      <div className="flex items-center gap-1.5">
                        <Clock className="h-3 w-3" />
                        {e.recorded_at}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className={cn("font-mono text-[10px]", badgeStyle)}>
                        {e.event_type}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-bold font-mono text-sm">
                      {e.ticker ? (
                        <>
                          <span className="text-primary mr-0.5">$</span>
                          {e.ticker}
                        </>
                      ) : (
                        <span className="text-muted-foreground font-normal">-</span>
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-foreground/80">{e.run_id}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">{e.event_id}</TableCell>
                  </TableRow>
                  {isOpen && (
                    <TableRow className="hover:bg-transparent">
                      <TableCell colSpan={6} className="p-0 border-b border-border/80">
                        <div className="bg-muted/20 p-5 rounded-b-lg border-x border-b border-border/80 space-y-3">
                          <div className="flex items-center justify-between">
                            <div className="text-xs font-semibold text-foreground flex items-center gap-2">
                              <Activity className="h-4 w-4 text-primary" />
                              Olay Ham Verisi (Payload & Source Artifacts)
                            </div>
                            <button
                              onClick={() => copyEventJson(e)}
                              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground font-mono"
                            >
                              <Copy className="h-3.5 w-3.5" /> JSON Kopyala
                            </button>
                          </div>

                          <div className="rounded-lg border border-border/60 bg-background/80 overflow-hidden shadow-xs">
                            <ScrollArea className="h-72 p-3">
                              <pre className="font-mono text-xs text-foreground/90 whitespace-pre-wrap">
                                {JSON.stringify(e, null, 2)}
                              </pre>
                            </ScrollArea>
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              );
            })}

            {filteredEvents.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
                  Filtreye uygun olay kaydı bulunamadı.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
