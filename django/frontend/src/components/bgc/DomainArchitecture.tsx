import { useMemo } from "react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { DomainArchitectureItem } from "@/api/types";

const DOMAIN_COLORS: Record<string, string> = {
  Pfam: "#3b82f6",
  TIGRFAM: "#22c55e",
  antismash: "#f97316",
};

const DEFAULT_COLOR = "#6b7280";

interface DomainArchitectureProps {
  domains: DomainArchitectureItem[];
}

export function DomainArchitecture({ domains }: DomainArchitectureProps) {
  const { totalWidth, items } = useMemo(() => {
    if (domains.length === 0) return { totalWidth: 0, items: [] };
    const maxEnd = Math.max(...domains.map((d) => d.end));
    return {
      totalWidth: maxEnd,
      items: domains.map((d) => ({
        ...d,
        leftPct: (d.start / maxEnd) * 100,
        widthPct: ((d.end - d.start) / maxEnd) * 100,
      })),
    };
  }, [domains]);

  if (domains.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">No domain information</p>
    );
  }

  return (
    <TooltipProvider delayDuration={100}>
      <div className="space-y-1">
        <div className="relative h-8 w-full rounded bg-muted">
          {/* Backbone line */}
          <div className="absolute left-0 right-0 top-1/2 h-px bg-border" />
          {/* Domains */}
          {items.map((d, i) => (
            <Tooltip key={i}>
              <TooltipTrigger asChild>
                <div
                  className="absolute top-1 h-6 cursor-pointer rounded-sm border border-white/30 transition-opacity hover:opacity-80"
                  style={{
                    left: `${d.leftPct}%`,
                    width: `${Math.max(d.widthPct, 0.5)}%`,
                    backgroundColor:
                      DOMAIN_COLORS[d.ref_db] ?? DEFAULT_COLOR,
                  }}
                />
              </TooltipTrigger>
              <TooltipContent side="top" className="text-xs">
                <div>
                  <strong>{d.domain_acc}</strong> — {d.domain_name}
                </div>
                <div className="text-muted-foreground">
                  {d.ref_db} | {d.start}–{d.end}
                  {d.score !== null && ` | score: ${d.score.toFixed(1)}`}
                </div>
              </TooltipContent>
            </Tooltip>
          ))}
        </div>
        <div className="flex justify-between text-[10px] text-muted-foreground">
          <span>0</span>
          <span>{totalWidth}</span>
        </div>
      </div>
    </TooltipProvider>
  );
}
