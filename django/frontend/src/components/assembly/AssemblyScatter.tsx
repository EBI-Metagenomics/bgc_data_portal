import { useMemo, useState, useCallback } from "react";
import Plot from "react-plotly.js";
import { useAssemblyScatter } from "@/hooks/use-assembly-scatter";
import { useSelectionStore } from "@/stores/selection-store";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const AXIS_OPTIONS = [
  { value: "bgc_diversity_score", label: "Diversity" },
  { value: "bgc_novelty_score", label: "Novelty" },
  { value: "bgc_density", label: "Density" },
  { value: "taxonomic_novelty", label: "Tax. Novelty" },
  { value: "assembly_quality", label: "Quality" },
];

// Color palette for taxonomy
const TAXONOMY_COLORS = [
  "#3b82f6", "#ef4444", "#22c55e", "#f97316", "#a855f7",
  "#14b8a6", "#ec4899", "#eab308", "#6366f1", "#84cc16",
  "#f43f5e", "#06b6d4", "#d946ef", "#f59e0b", "#10b981",
];

export function AssemblyScatter() {
  const [xAxis, setXAxis] = useState("bgc_diversity_score");
  const [yAxis, setYAxis] = useState("bgc_novelty_score");
  const { data: points, isLoading } = useAssemblyScatter(xAxis, yAxis);
  const activeAssemblyId = useSelectionStore((s) => s.activeAssemblyId);
  const setActiveAssemblyId = useSelectionStore((s) => s.setActiveAssemblyId);

  // Group by dominant taxonomy label for coloring
  const traces = useMemo(() => {
    if (!points?.length) return [];
    const groups = new Map<string, typeof points>();
    for (const pt of points) {
      const taxonomy = pt.dominant_taxonomy_label ?? "Unknown";
      const existing = groups.get(taxonomy);
      if (existing) {
        existing.push(pt);
      } else {
        groups.set(taxonomy, [pt]);
      }
    }

    let colorIdx = 0;
    const result: Plotly.Data[] = [];
    for (const [taxonomy, pts] of groups) {
      const color = TAXONOMY_COLORS[colorIdx % TAXONOMY_COLORS.length]!;
      colorIdx++;
      result.push({
        type: "scatter" as const,
        mode: "markers" as const,
        name: taxonomy,
        x: pts.map((p) => p.x),
        y: pts.map((p) => p.y),
        customdata: pts.map((p) => p.id),
        text: pts.map(
          (p) =>
            `${p.organism_name ?? "Unknown"}${p.is_type_strain ? "<br>Type Strain" : ""}`
        ),
        hoverinfo: "text" as const,
        marker: {
          color,
          size: 8,
          opacity: 0.7,
          line: {
            color: pts.map((p) =>
              p.id === activeAssemblyId ? "#000" : "transparent"
            ),
            width: pts.map((p) => (p.id === activeAssemblyId ? 2 : 0)),
          },
        },
      });
    }
    return result;
  }, [points, activeAssemblyId]);

  const handleClick = useCallback(
    (event: Plotly.PlotMouseEvent) => {
      const point = event.points[0];
      if (point?.customdata) {
        setActiveAssemblyId(point.customdata as number);
      }
    },
    [setActiveAssemblyId]
  );

  const xLabel = AXIS_OPTIONS.find((o) => o.value === xAxis)?.label ?? xAxis;
  const yLabel = AXIS_OPTIONS.find((o) => o.value === yAxis)?.label ?? yAxis;

  if (isLoading) {
    return <Skeleton className="h-64 w-full" />;
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">X:</span>
        <Select value={xAxis} onValueChange={setXAxis}>
          <SelectTrigger className="h-7 w-28 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {AXIS_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value} className="text-xs">
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-xs text-muted-foreground">Y:</span>
        <Select value={yAxis} onValueChange={setYAxis}>
          <SelectTrigger className="h-7 w-28 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {AXIS_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value} className="text-xs">
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <Plot
        data={traces}
        layout={{
          autosize: true,
          height: 300,
          margin: { l: 40, r: 10, t: 10, b: 40 },
          xaxis: { title: { text: xLabel, font: { size: 11 } } },
          yaxis: { title: { text: yLabel, font: { size: 11 } } },
          showlegend: true,
          legend: { font: { size: 9 }, orientation: "h" as const, y: -0.3 },
          hovermode: "closest" as const,
        }}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: "100%" }}
        onClick={handleClick}
      />
    </div>
  );
}
