import Plot from "react-plotly.js";
import type { RedundancyCell } from "@/api/types";

interface RedundancyMatrixProps {
  matrix: RedundancyCell[];
}

const STATUS_LABELS: Record<string, string> = {
  novel_gcf: "Novel GCF",
  known_gcf_no_type_strain: "Known GCF\n(no type strain)",
  known_gcf_type_strain: "Known GCF\n(type strain available)",
};

const STATUS_COLORS: Record<string, number> = {
  novel_gcf: 0,
  known_gcf_no_type_strain: 0.5,
  known_gcf_type_strain: 1,
};

export function RedundancyMatrix({ matrix }: RedundancyMatrixProps) {
  if (matrix.length === 0) {
    return <p className="py-8 text-center text-sm text-muted-foreground">No BGCs found.</p>;
  }

  const categories = ["novel_gcf", "known_gcf_no_type_strain", "known_gcf_type_strain"];
  const bgcLabels = matrix.map((r) => r.accession);

  // Build z-matrix: rows=BGCs, cols=3 categories
  const z = matrix.map((r) =>
    categories.map((cat) => (r.status === cat ? 1 : 0))
  );

  const hoverText = matrix.map((r) =>
    categories.map((cat) => {
      if (r.status === cat) {
        return `${r.accession}<br>${r.classification_l1}<br>${STATUS_LABELS[cat]}${r.gcf_family_id ? `<br>GCF: ${r.gcf_family_id} (${r.gcf_member_count} members)` : ""}`;
      }
      return "";
    })
  );

  return (
    <Plot
      data={[
        {
          type: "heatmap",
          z,
          x: categories.map((c) => STATUS_LABELS[c]),
          y: bgcLabels,
          colorscale: [
            [0, "rgb(240,240,240)"],
            [0.5, "rgb(59,130,246)"],
            [1, "rgb(34,197,94)"],
          ],
          showscale: false,
          hovertext: hoverText,
          hoverinfo: "text",
        },
      ]}
      layout={{
        xaxis: { side: "top", tickangle: 0 },
        yaxis: { automargin: true },
        margin: { t: 60, b: 20, l: 120, r: 20 },
        autosize: true,
        height: Math.max(200, matrix.length * 28 + 80),
      }}
      config={{ responsive: true, displayModeBar: false }}
      useResizeHandler
      style={{ width: "100%", height: "100%" }}
    />
  );
}
