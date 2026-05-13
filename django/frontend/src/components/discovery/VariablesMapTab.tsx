import { useQuery } from "@tanstack/react-query";
import { fetchNrbScatter } from "@/api/nrbs";
import { useDiscoveryStore } from "@/stores/discovery-store";
import type { NrbScatterAxis } from "@/api/types";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2 } from "lucide-react";

const AXIS_OPTIONS: { value: NrbScatterAxis; label: string }[] = [
  { value: "novelty_score", label: "Novelty" },
  { value: "domain_novelty", label: "Domain novelty" },
  { value: "size_kb", label: "Size (kb)" },
  { value: "n_cds", label: "# CDS" },
  { value: "similarity_score", label: "Query similarity (post-query)" },
];

/**
 * Plotly integration is wired in P2.2b — for now this tab fetches the
 * scatter data and renders a list of points so the data path can be
 * smoke-tested end-to-end against the new `/nrbs/scatter/` endpoint.
 */
export function VariablesMapTab() {
  const xAxis = useDiscoveryStore((s) => s.variablesAxisX);
  const yAxis = useDiscoveryStore((s) => s.variablesAxisY);
  const setAxes = useDiscoveryStore((s) => s.setVariablesAxes);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["nrb-scatter", xAxis, yAxis],
    queryFn: () => fetchNrbScatter({ x_axis: xAxis, y_axis: yAxis }),
    // similarity_score isn't a stored column — the API rejects it for the
    // raw scatter endpoint.
    enabled: xAxis !== "similarity_score" && yAxis !== "similarity_score",
  });

  return (
    <div className="flex h-full flex-col p-3">
      <div className="flex items-center gap-2 pb-2 text-xs">
        <span className="text-muted-foreground">X:</span>
        <Select
          value={xAxis}
          onValueChange={(v) => setAxes(v as NrbScatterAxis, yAxis)}
        >
          <SelectTrigger className="h-8 w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {AXIS_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="ml-3 text-muted-foreground">Y:</span>
        <Select
          value={yAxis}
          onValueChange={(v) => setAxes(xAxis, v as NrbScatterAxis)}
        >
          <SelectTrigger className="h-8 w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {AXIS_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="flex flex-1 items-center justify-center rounded border bg-muted/20 text-sm text-muted-foreground">
        {isLoading ? (
          <span>
            <Loader2 className="mr-2 inline h-4 w-4 animate-spin" />
            Loading {data ? "…" : "axes…"}
          </span>
        ) : isError ? (
          <span className="text-destructive">
            {(error as Error)?.message ?? "Failed to load scatter data"}
          </span>
        ) : (
          <span>
            {data?.length ?? 0} points fetched · Plotly view wires up next
          </span>
        )}
      </div>
    </div>
  );
}
