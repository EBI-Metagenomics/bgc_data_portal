import Plot from "react-plotly.js";
import type { DomainDifferential } from "@/api/types";

interface DomainDifferentialChartProps {
  domains: DomainDifferential[];
}

const CATEGORY_COLORS: Record<string, string> = {
  core: "#3b82f6",
  variable: "#f97316",
  absent: "#ef4444",
};

export function DomainDifferentialChart({
  domains,
}: DomainDifferentialChartProps) {
  const core = domains.filter((d) => d.category === "core");
  const variable = domains.filter((d) => d.category === "variable");
  const absent = domains.filter((d) => d.category === "absent");

  const totalCount = domains.length || 1;

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <Plot
        data={[
          {
            type: "bar",
            orientation: "h",
            y: ["Domain Composition"],
            x: [core.length],
            name: `Core (${core.length})`,
            marker: { color: CATEGORY_COLORS.core },
            hoverinfo: "name+x",
          },
          {
            type: "bar",
            orientation: "h",
            y: ["Domain Composition"],
            x: [variable.length],
            name: `Variable (${variable.length})`,
            marker: { color: CATEGORY_COLORS.variable },
            hoverinfo: "name+x",
          },
          {
            type: "bar",
            orientation: "h",
            y: ["Domain Composition"],
            x: [absent.length],
            name: `Absent (${absent.length})`,
            marker: { color: CATEGORY_COLORS.absent },
            hoverinfo: "name+x",
          },
        ]}
        layout={{
          barmode: "stack",
          height: 80,
          margin: { t: 10, b: 20, l: 120, r: 20 },
          showlegend: true,
          legend: { orientation: "h", y: -0.5 },
          xaxis: { title: "Number of domains" },
          autosize: true,
        }}
        config={{ responsive: true, displayModeBar: false }}
        useResizeHandler
        style={{ width: "100%", height: 80 }}
      />

      {/* Domain detail table */}
      <div className="max-h-64 overflow-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="py-1">Domain</th>
              <th className="py-1">Accession</th>
              <th className="py-1 text-right">GCF Frequency</th>
              <th className="py-1 text-right">Category</th>
            </tr>
          </thead>
          <tbody>
            {domains.map((d) => (
              <tr key={`${d.domain_acc}-${d.category}`} className="border-b last:border-0">
                <td className="py-1">{d.domain_name}</td>
                <td className="py-1 font-mono">{d.domain_acc}</td>
                <td className="py-1 text-right">
                  {(d.gcf_frequency * 100).toFixed(0)}%
                </td>
                <td className="py-1 text-right">
                  <span
                    className="inline-block rounded px-1.5 py-0.5 text-[10px] font-medium"
                    style={{
                      backgroundColor: `${CATEGORY_COLORS[d.category]}20`,
                      color: CATEGORY_COLORS[d.category],
                    }}
                  >
                    {d.category}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
