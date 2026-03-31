import type { DomainArchitectureItem } from "@/api/types";

interface DomainArchitectureComparisonProps {
  submittedDomains: DomainArchitectureItem[];
  mibigDomains: DomainArchitectureItem[];
  mibigAccession: string | null;
}

const DOMAIN_COLORS = [
  "#3b82f6", "#ef4444", "#22c55e", "#f97316", "#a855f7",
  "#ec4899", "#14b8a6", "#eab308", "#6366f1", "#f43f5e",
];

export function DomainArchitectureComparison({
  submittedDomains,
  mibigDomains,
  mibigAccession,
}: DomainArchitectureComparisonProps) {
  // Assign colors by domain accession
  const allAccs = [
    ...new Set([
      ...submittedDomains.map((d) => d.domain_acc),
      ...mibigDomains.map((d) => d.domain_acc),
    ]),
  ];
  const colorMap: Record<string, string> = {};
  allAccs.forEach((acc, i) => {
    colorMap[acc] = DOMAIN_COLORS[i % DOMAIN_COLORS.length];
  });

  return (
    <div className="space-y-4">
      <DomainRow
        label="Submitted BGC"
        domains={submittedDomains}
        colorMap={colorMap}
      />
      {mibigDomains.length > 0 ? (
        <DomainRow
          label={`Nearest MIBiG: ${mibigAccession || "Unknown"}`}
          domains={mibigDomains}
          colorMap={colorMap}
        />
      ) : (
        <p className="text-xs text-muted-foreground">
          {mibigAccession
            ? `Nearest MIBiG: ${mibigAccession} (domain data not available)`
            : "No MIBiG reference available for comparison"}
        </p>
      )}
    </div>
  );
}

function DomainRow({
  label,
  domains,
  colorMap,
}: {
  label: string;
  domains: DomainArchitectureItem[];
  colorMap: Record<string, string>;
}) {
  if (domains.length === 0) return null;

  const maxEnd = Math.max(...domains.map((d) => d.end), 1);

  return (
    <div>
      <p className="mb-1 text-xs font-medium">{label}</p>
      <div className="relative h-8 w-full rounded border bg-gray-50">
        {domains.map((d, i) => {
          const left = (d.start / maxEnd) * 100;
          const width = Math.max(((d.end - d.start) / maxEnd) * 100, 1);
          return (
            <div
              key={`${d.domain_acc}-${i}`}
              className="absolute top-1 h-6 rounded text-[8px] leading-6 text-white"
              style={{
                left: `${left}%`,
                width: `${width}%`,
                backgroundColor: colorMap[d.domain_acc] || "#6b7280",
                minWidth: 4,
              }}
              title={`${d.domain_name} (${d.domain_acc}) [${d.start}-${d.end}]`}
            >
              {width > 5 && (
                <span className="truncate px-0.5">{d.domain_name}</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
