import Plot from "react-plotly.js";
import type { GcfMemberPoint, AssessChemicalSpacePoint } from "@/api/types";

interface GcfMemberMapProps {
  members: GcfMemberPoint[];
  submittedPoint: AssessChemicalSpacePoint | null;
}

export function GcfMemberMap({ members, submittedPoint }: GcfMemberMapProps) {
  const traces: Plotly.Data[] = [];

  // Non-type-strain members
  const nonTs = members.filter((m) => !m.is_type_strain);
  if (nonTs.length > 0) {
    traces.push({
      type: "scatter",
      mode: "markers",
      x: nonTs.map((m) => m.umap_x),
      y: nonTs.map((m) => m.umap_y),
      marker: { size: 7, color: "rgba(150,150,150,0.6)" },
      text: nonTs.map((m) => `${m.accession}<br>Dist: ${m.distance_to_representative.toFixed(4)}`),
      hoverinfo: "text",
      name: "Non-purchasable",
    });
  }

  // Type-strain members (purchasable)
  const ts = members.filter((m) => m.is_type_strain);
  if (ts.length > 0) {
    traces.push({
      type: "scatter",
      mode: "markers",
      x: ts.map((m) => m.umap_x),
      y: ts.map((m) => m.umap_y),
      marker: { size: 9, color: "#f97316" },
      text: ts.map((m) => `${m.accession} (type strain)<br>Dist: ${m.distance_to_representative.toFixed(4)}`),
      hoverinfo: "text",
      name: "Purchasable (type strain)",
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
        size: 16,
        color: "#3b82f6",
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
      style={{ width: "100%", height: 350 }}
    />
  );
}
