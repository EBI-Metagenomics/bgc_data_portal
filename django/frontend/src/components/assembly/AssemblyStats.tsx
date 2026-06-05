import { useMemo } from "react";
import Plot from "react-plotly.js";
import { useAssemblyStats } from "@/hooks/use-assembly-stats";
import { useFilterStore } from "@/stores/filter-store";
import { Skeleton } from "@/components/ui/skeleton";
import { StatsExportMenu } from "@/components/stats/StatsExportMenu";
import { exportAssemblyStats } from "@/api/exports";
import { colorByAncestorDepth } from "@/lib/sunburst-colors";

export function AssemblyStats({ assemblyIds, enabled = true }: { assemblyIds?: string; enabled?: boolean }) {
  const { data, isLoading } = useAssemblyStats(assemblyIds, enabled);

  if (isLoading) {
    return <Skeleton className="h-[280px] w-full" />;
  }

  if (!data || data.total_assemblies === 0) {
    return (
      <div className="flex h-[280px] items-center justify-center text-sm text-muted-foreground">
        No assembly data available
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Row 1: Taxonomy Sunburst + Biome Sunburst */}
      <div className="grid grid-cols-2 gap-2">
        <div className="flex flex-col items-center">
          <TaxonomySunburst nodes={data.taxonomy_sunburst} />
        </div>
        <div className="flex flex-col items-center">
          <BiomeSunburst nodes={data.biome_sunburst ?? []} />
        </div>
      </div>

      {/* Row 2: Score Boxplots + Type Strain Pie */}
      <div className="grid grid-cols-2 gap-2">
        <div className="flex flex-col items-center">
          <ScoreBoxplots distributions={data.score_distributions} />
        </div>
        <div className="flex flex-col items-center">
          <TypeStrainPie
            typeStrain={data.type_strain_count}
            nonTypeStrain={data.non_type_strain_count}
          />
        </div>
      </div>

      {/* Row 3: Averages */}
      <div className="grid grid-cols-2 gap-2">
        <div />
        <div className="flex flex-col items-center justify-center gap-2">
          <div className="text-center">
            <div className="text-2xl font-bold">{data.mean_bgc_per_assembly}</div>
            <div className="text-xs text-muted-foreground">Avg BGCs / assembly</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold">{data.mean_l1_class_per_assembly}</div>
            <div className="text-xs text-muted-foreground">Avg classes / assembly</div>
          </div>
          <div className="text-center text-xs text-muted-foreground">
            {data.total_assemblies} assemblies
          </div>
        </div>
      </div>
    </div>
  );
}

export function AssemblyStatsActions({ assemblyIds }: { assemblyIds?: string }) {
  const filters = useFilterStore();
  const params = useMemo(
    () => ({
      search: filters.search || undefined,
      source_names: filters.sourceNames.length ? filters.sourceNames.join(",") : undefined,
      detector_tools: filters.detectorTools.length ? filters.detectorTools.join(",") : undefined,
      bgc_class: filters.bgcClass || undefined,
      biome_lineage: filters.biomeLineage || undefined,
      assembly_ids: assemblyIds,
    }),
    [filters, assemblyIds]
  );

  return (
    <StatsExportMenu
      onExport={(format) => exportAssemblyStats(params, format)}
    />
  );
}

const PLOTLY_LAYOUT_BASE: Partial<Plotly.Layout> = {
  margin: { t: 20, b: 20, l: 30, r: 10 },
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  font: { size: 10, color: "#888" },
};

const PLOTLY_CONFIG: Partial<Plotly.Config> = {
  displayModeBar: false,
  responsive: true,
};

type SunNode = { id: string; label: string; parent: string; count: number };

function TaxonomySunburst({ nodes }: { nodes: SunNode[] }) {
  if (nodes.length === 0) return <EmptyPlaceholder label="No taxonomy data" />;

  const colors = colorByAncestorDepth(nodes, 1); // phylum
  return (
    <Plot
      data={[
        {
          type: "sunburst",
          ids: nodes.map((n) => n.id),
          labels: nodes.map((n) => n.label),
          parents: nodes.map((n) => n.parent),
          values: nodes.map((n) => n.count),
          branchvalues: "total",
          marker: { colors },
          hovertemplate: "<b>%{label}</b><br>Count: %{value}<extra></extra>",
        } as Plotly.Data,
      ]}
      layout={{
        ...PLOTLY_LAYOUT_BASE,
        width: 200,
        height: 200,
        title: { text: "Taxonomy", font: { size: 11 } },
      }}
      config={PLOTLY_CONFIG}
    />
  );
}

function BiomeSunburst({ nodes }: { nodes: SunNode[] }) {
  if (nodes.length === 0) return <EmptyPlaceholder label="No biome data" />;

  const colors = colorByAncestorDepth(nodes, 3); // depth 3
  return (
    <Plot
      data={[
        {
          type: "sunburst",
          ids: nodes.map((n) => n.id),
          labels: nodes.map((n) => n.label),
          parents: nodes.map((n) => n.parent),
          values: nodes.map((n) => n.count),
          branchvalues: "total",
          marker: { colors },
          hovertemplate: "<b>%{label}</b><br>Count: %{value}<extra></extra>",
        } as Plotly.Data,
      ]}
      layout={{
        ...PLOTLY_LAYOUT_BASE,
        width: 200,
        height: 200,
        title: { text: "Biome", font: { size: 11 } },
      }}
      config={PLOTLY_CONFIG}
    />
  );
}

function ScoreBoxplots({
  distributions,
}: {
  distributions: { label: string; values: number[] }[];
}) {
  if (distributions.length === 0) return <EmptyPlaceholder label="No score data" />;

  const traces: Plotly.Data[] = distributions.map((d) => ({
    type: "box" as const,
    y: d.values,
    name: d.label,
    boxpoints: false,
    marker: { color: "#3b82f6" },
  }));

  return (
    <Plot
      data={traces}
      layout={{
        ...PLOTLY_LAYOUT_BASE,
        width: 200,
        height: 200,
        title: { text: "Score Distributions", font: { size: 11 } },
        showlegend: false,
      }}
      config={PLOTLY_CONFIG}
    />
  );
}

function TypeStrainPie({
  typeStrain,
  nonTypeStrain,
}: {
  typeStrain: number;
  nonTypeStrain: number;
}) {
  if (typeStrain + nonTypeStrain === 0)
    return <EmptyPlaceholder label="No strain data" />;

  return (
    <Plot
      data={[
        {
          type: "pie",
          labels: ["Type Strain", "Non-Type Strain"],
          values: [typeStrain, nonTypeStrain],
          marker: { colors: ["#22c55e", "#6b7280"] },
          textinfo: "label+percent",
          hovertemplate: "<b>%{label}</b><br>Count: %{value}<extra></extra>",
        } as Plotly.Data,
      ]}
      layout={{
        ...PLOTLY_LAYOUT_BASE,
        width: 200,
        height: 200,
        title: { text: "Type Strains", font: { size: 11 } },
        showlegend: false,
      }}
      config={PLOTLY_CONFIG}
    />
  );
}

function EmptyPlaceholder({ label }: { label: string }) {
  return (
    <div className="flex h-[200px] w-[200px] items-center justify-center text-xs text-muted-foreground">
      {label}
    </div>
  );
}
