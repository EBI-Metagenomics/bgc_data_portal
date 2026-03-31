import Plot from "react-plotly.js";
import type { NoveltyDecomposition } from "@/api/types";

interface NoveltyGaugesProps {
  novelty: NoveltyDecomposition;
}

const GAUGE_CONFIG = [
  { key: "sequence_novelty" as const, label: "Sequence", color: "#3b82f6" },
  { key: "chemistry_novelty" as const, label: "Chemistry", color: "#f97316" },
  { key: "architecture_novelty" as const, label: "Architecture", color: "#22c55e" },
];

export function NoveltyGauges({ novelty }: NoveltyGaugesProps) {
  return (
    <div className="grid grid-cols-3 gap-4">
      {GAUGE_CONFIG.map(({ key, label, color }) => (
        <div key={key} className="flex flex-col items-center">
          <Plot
            data={[
              {
                type: "indicator",
                mode: "gauge+number",
                value: novelty[key],
                gauge: {
                  axis: { range: [0, 1], tickvals: [0, 0.25, 0.5, 0.75, 1] },
                  bar: { color },
                  shape: "angular",
                  steps: [
                    { range: [0, 0.33], color: "rgba(200,200,200,0.2)" },
                    { range: [0.33, 0.66], color: "rgba(200,200,200,0.1)" },
                    { range: [0.66, 1], color: "rgba(200,200,200,0.05)" },
                  ],
                },
                number: { valueformat: ".3f" },
              },
            ]}
            layout={{
              height: 180,
              margin: { t: 30, b: 0, l: 30, r: 30 },
              autosize: true,
            }}
            config={{ responsive: true, displayModeBar: false }}
            useResizeHandler
            style={{ width: "100%", height: 180 }}
          />
          <span className="text-xs font-medium">{label} Novelty</span>
        </div>
      ))}
    </div>
  );
}
