import Plot from "react-plotly.js";
import type { AssessChemicalSpacePoint, MibigReferencePoint } from "@/api/types";

const BGC_CLASS_COLORS: Record<string, string> = {
  Polyketide: "#3b82f6",
  NRP: "#ef4444",
  RiPP: "#22c55e",
  Terpene: "#f97316",
  Saccharide: "#a855f7",
  Alkaloid: "#ec4899",
  Other: "#6b7280",
};

interface ChemicalSpaceMapProps {
  points: AssessChemicalSpacePoint[];
  mibigPoints: MibigReferencePoint[];
  meanMibigDistance: number;
  sparseFraction: number;
}

export function ChemicalSpaceMap({
  points,
  mibigPoints,
  meanMibigDistance,
  sparseFraction,
}: ChemicalSpaceMapProps) {
  const traces: Plotly.Data[] = [];

  // MIBiG references (grey triangles, low opacity)
  if (mibigPoints.length > 0) {
    traces.push({
      type: "scatter",
      mode: "markers",
      x: mibigPoints.map((p) => p.umap_x),
      y: mibigPoints.map((p) => p.umap_y),
      marker: {
        symbol: "triangle-up",
        size: 5,
        color: "rgba(150,150,150,0.3)",
      },
      text: mibigPoints.map((p) => `${p.accession} (${p.compound_name})`),
      hoverinfo: "text",
      name: "MIBiG references",
    });
  }

  // Genome BGCs as stars, colored by class
  if (points.length > 0) {
    traces.push({
      type: "scatter",
      mode: "markers",
      x: points.map((p) => p.umap_x),
      y: points.map((p) => p.umap_y),
      marker: {
        symbol: "star",
        size: 14,
        color: points.map(
          (p) => BGC_CLASS_COLORS[p.classification_l1] || BGC_CLASS_COLORS.Other
        ),
        line: { color: "black", width: 1 },
      },
      text: points.map(
        (p) =>
          `${p.accession}<br>${p.classification_l1}<br>MIBiG dist: ${p.nearest_mibig_distance.toFixed(3)}${p.is_sparse ? "<br>(sparse region)" : ""}`
      ),
      hoverinfo: "text",
      name: "Genome BGCs",
    });
  }

  return (
    <div>
      <div className="mb-2 flex gap-4 text-xs text-muted-foreground">
        <span>
          Mean MIBiG distance: <strong>{meanMibigDistance.toFixed(3)}</strong>
        </span>
        <span>
          In sparse regions: <strong>{(sparseFraction * 100).toFixed(0)}%</strong>
        </span>
      </div>
      <Plot
        data={traces}
        layout={{
          xaxis: { title: "UMAP 1", zeroline: false },
          yaxis: { title: "UMAP 2", zeroline: false },
          showlegend: true,
          legend: { orientation: "h", y: -0.15 },
          margin: { t: 10, b: 60, l: 60, r: 20 },
          autosize: true,
        }}
        config={{ responsive: true, displayModeBar: false }}
        useResizeHandler
        style={{ width: "100%", height: 400 }}
      />
    </div>
  );
}
