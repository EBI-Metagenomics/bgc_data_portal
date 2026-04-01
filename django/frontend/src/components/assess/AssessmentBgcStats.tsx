import { useMemo } from "react";
import Plot from "react-plotly.js";
import type { BgcNoveltyItem } from "@/api/types";

interface AssessmentBgcStatsProps {
  bgcNovelty: BgcNoveltyItem[];
}

const PLOTLY_LAYOUT_BASE: Partial<Plotly.Layout> = {
  margin: { t: 30, b: 40, l: 40, r: 10 },
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  font: { size: 10, color: "#888" },
};

const PLOTLY_CONFIG: Partial<Plotly.Config> = {
  displayModeBar: false,
  responsive: true,
};

function buildHistogramBins(values: number[], binCount: number = 10) {
  const binWidth = 1.0 / binCount;
  const counts = new Array(binCount).fill(0);
  const labels: string[] = [];

  for (let i = 0; i < binCount; i++) {
    const lo = i * binWidth;
    const hi = lo + binWidth;
    labels.push(`${lo.toFixed(1)}-${hi.toFixed(1)}`);
  }

  for (const v of values) {
    const idx = Math.min(Math.floor(v / binWidth), binCount - 1);
    counts[idx]++;
  }

  return { labels, counts };
}

export function AssessmentBgcStats({ bgcNovelty }: AssessmentBgcStatsProps) {
  const completeCount = useMemo(
    () => bgcNovelty.filter((b) => !b.is_partial).length,
    [bgcNovelty]
  );
  const partialCount = useMemo(
    () => bgcNovelty.filter((b) => b.is_partial).length,
    [bgcNovelty]
  );

  const noveltyHist = useMemo(
    () => buildHistogramBins(bgcNovelty.map((b) => b.novelty_vs_db)),
    [bgcNovelty]
  );

  const domainHist = useMemo(
    () => buildHistogramBins(bgcNovelty.map((b) => b.domain_novelty)),
    [bgcNovelty]
  );

  if (bgcNovelty.length === 0) {
    return (
      <div className="flex h-[220px] items-center justify-center text-sm text-muted-foreground">
        No BGC data available
      </div>
    );
  }

  return (
    <div className="grid grid-cols-3 gap-2">
      {/* Completeness Pie */}
      <div className="flex flex-col items-center">
        <Plot
          data={[
            {
              type: "pie",
              labels: ["Complete", "Partial"],
              values: [completeCount, partialCount],
              marker: { colors: ["#22c55e", "#f97316"] },
              textinfo: "label+percent",
              hovertemplate:
                "<b>%{label}</b><br>Count: %{value}<extra></extra>",
            } as Plotly.Data,
          ]}
          layout={{
            ...PLOTLY_LAYOUT_BASE,
            height: 220,
            title: { text: "Completeness", font: { size: 11 } },
            showlegend: false,
            autosize: true,
          }}
          config={PLOTLY_CONFIG}
          useResizeHandler
          style={{ width: "100%", height: 220 }}
        />
      </div>

      {/* Novelty Histogram */}
      <div className="flex flex-col items-center">
        <Plot
          data={[
            {
              type: "bar",
              x: noveltyHist.labels,
              y: noveltyHist.counts,
              marker: { color: "#3b82f6" },
              hovertemplate: "%{x}<br>%{y} BGCs<extra></extra>",
            },
          ]}
          layout={{
            ...PLOTLY_LAYOUT_BASE,
            height: 220,
            title: { text: "Novelty", font: { size: 11 } },
            xaxis: { title: { text: "Score", font: { size: 9 } }, tickangle: -45, tickfont: { size: 8 } },
            yaxis: { title: { text: "BGCs", font: { size: 9 } } },
            showlegend: false,
            autosize: true,
            bargap: 0.05,
          }}
          config={PLOTLY_CONFIG}
          useResizeHandler
          style={{ width: "100%", height: 220 }}
        />
      </div>

      {/* Domain Novelty Histogram */}
      <div className="flex flex-col items-center">
        <Plot
          data={[
            {
              type: "bar",
              x: domainHist.labels,
              y: domainHist.counts,
              marker: { color: "#8b5cf6" },
              hovertemplate: "%{x}<br>%{y} BGCs<extra></extra>",
            },
          ]}
          layout={{
            ...PLOTLY_LAYOUT_BASE,
            height: 220,
            title: { text: "Domain Novelty", font: { size: 11 } },
            xaxis: { title: { text: "Score", font: { size: 9 } }, tickangle: -45, tickfont: { size: 8 } },
            yaxis: { title: { text: "BGCs", font: { size: 9 } } },
            showlegend: false,
            autosize: true,
            bargap: 0.05,
          }}
          config={PLOTLY_CONFIG}
          useResizeHandler
          style={{ width: "100%", height: 220 }}
        />
      </div>
    </div>
  );
}
