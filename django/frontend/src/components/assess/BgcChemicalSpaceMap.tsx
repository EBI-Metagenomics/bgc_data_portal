import Plot from "react-plotly.js";
import type {
  AssessChemicalSpacePoint,
  AssessNearestNeighborPoint,
  MibigReferencePoint,
} from "@/api/types";

interface BgcChemicalSpaceMapProps {
  submittedPoint: AssessChemicalSpacePoint | null;
  neighbors: AssessNearestNeighborPoint[];
  mibigPoints: MibigReferencePoint[];
}

export function BgcChemicalSpaceMap({
  submittedPoint,
  neighbors,
  mibigPoints,
}: BgcChemicalSpaceMapProps) {
  const traces: Plotly.Data[] = [];

  // MIBiG background (faded)
  if (mibigPoints.length > 0) {
    traces.push({
      type: "scatter",
      mode: "markers",
      x: mibigPoints.map((p) => p.umap_x),
      y: mibigPoints.map((p) => p.umap_y),
      marker: { symbol: "triangle-up", size: 5, color: "rgba(150,150,150,0.2)" },
      text: mibigPoints.map((p) => `${p.accession} (${p.compound_name})`),
      hoverinfo: "text",
      name: "MIBiG",
    });
  }

  // DB nearest neighbors
  const dbNeighbors = neighbors.filter((n) => !n.is_mibig);
  if (dbNeighbors.length > 0) {
    traces.push({
      type: "scatter",
      mode: "markers+text",
      x: dbNeighbors.map((n) => n.umap_x),
      y: dbNeighbors.map((n) => n.umap_y),
      marker: { size: 7, color: "rgba(59,130,246,0.5)" },
      text: dbNeighbors.map((n) => n.label),
      textposition: "top center",
      textfont: { size: 8 },
      hovertext: dbNeighbors.map(
        (n) => `${n.label}<br>Distance: ${n.distance.toFixed(4)}`
      ),
      hoverinfo: "text",
      name: "Nearest DB BGCs",
    });
  }

  // MIBiG nearest neighbors (labeled)
  const mibigNeighbors = neighbors.filter((n) => n.is_mibig);
  if (mibigNeighbors.length > 0) {
    traces.push({
      type: "scatter",
      mode: "markers+text",
      x: mibigNeighbors.map((n) => n.umap_x),
      y: mibigNeighbors.map((n) => n.umap_y),
      marker: { symbol: "triangle-up", size: 10, color: "#f97316" },
      text: mibigNeighbors.map((n) => n.label),
      textposition: "top center",
      textfont: { size: 8 },
      hovertext: mibigNeighbors.map(
        (n) => `${n.label}<br>Distance: ${n.distance.toFixed(4)}`
      ),
      hoverinfo: "text",
      name: "Nearest MIBiG",
    });
  }

  // Submitted BGC as star
  if (submittedPoint) {
    traces.push({
      type: "scatter",
      mode: "markers",
      x: [submittedPoint.umap_x],
      y: [submittedPoint.umap_y],
      marker: {
        symbol: "star",
        size: 18,
        color: "#ef4444",
        line: { color: "black", width: 1.5 },
      },
      text: [`Submitted: ${submittedPoint.accession}`],
      hoverinfo: "text",
      name: "Submitted BGC",
    });
  }

  return (
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
  );
}
