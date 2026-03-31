import Plot from "react-plotly.js";
import type { PercentileRank, RadarReference } from "@/api/types";

interface PriorityRadarProps {
  percentileRanks: PercentileRank[];
  radarReferences: RadarReference[];
}

export function PriorityRadar({
  percentileRanks,
  radarReferences,
}: PriorityRadarProps) {
  const labels = percentileRanks.map((p) => p.label);
  const values = percentileRanks.map((p) => p.value);
  const dbMeans = radarReferences.map((r) => r.db_mean);
  const dbP90s = radarReferences.map((r) => r.db_p90);

  // Close the polygon
  const closedLabels = [...labels, labels[0]];
  const closedValues = [...values, values[0]];
  const closedMeans = [...dbMeans, dbMeans[0]];
  const closedP90s = [...dbP90s, dbP90s[0]];

  return (
    <Plot
      data={[
        {
          type: "scatterpolar",
          r: closedP90s,
          theta: closedLabels,
          name: "DB 90th percentile",
          fill: "toself",
          fillcolor: "rgba(200,200,200,0.15)",
          line: { color: "rgba(150,150,150,0.5)", dash: "dot" },
        },
        {
          type: "scatterpolar",
          r: closedMeans,
          theta: closedLabels,
          name: "DB mean",
          fill: "toself",
          fillcolor: "rgba(100,150,200,0.1)",
          line: { color: "rgba(100,150,200,0.6)", dash: "dash" },
        },
        {
          type: "scatterpolar",
          r: closedValues,
          theta: closedLabels,
          name: "This genome",
          fill: "toself",
          fillcolor: "rgba(59,130,246,0.2)",
          line: { color: "rgb(59,130,246)", width: 2 },
          marker: { size: 6 },
        },
      ]}
      layout={{
        polar: {
          radialaxis: {
            visible: true,
            range: [0, 1],
            tickvals: [0.2, 0.4, 0.6, 0.8, 1.0],
          },
        },
        showlegend: true,
        legend: { orientation: "h", y: -0.15 },
        margin: { t: 30, b: 60, l: 60, r: 60 },
        autosize: true,
      }}
      config={{ responsive: true, displayModeBar: false }}
      useResizeHandler
      style={{ width: "100%", height: "100%" }}
    />
  );
}
