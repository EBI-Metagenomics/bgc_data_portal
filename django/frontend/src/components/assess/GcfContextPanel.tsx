import type { GcfContext } from "@/api/types";

interface GcfContextPanelProps {
  gcfContext: GcfContext | null;
  distance: number | null;
  isNovelSingleton: boolean;
}

export function GcfContextPanel({
  gcfContext,
  distance,
  isNovelSingleton,
}: GcfContextPanelProps) {
  if (isNovelSingleton) {
    return (
      <div className="space-y-3">
        <div className="rounded-lg border border-purple-200 bg-purple-50 p-4">
          <p className="text-sm font-medium text-purple-800">Novel Singleton</p>
          <p className="mt-1 text-xs text-purple-600">
            This BGC does not belong to any known Gene Cluster Family in the
            database. It may represent novel chemistry.
          </p>
        </div>
      </div>
    );
  }

  if (!gcfContext) {
    return (
      <p className="py-4 text-sm text-muted-foreground">
        No GCF assignment available.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Family" value={gcfContext.family_id} />
        <Stat label="Members" value={gcfContext.member_count.toString()} />
        <Stat label="MIBiG" value={gcfContext.mibig_count > 0 ? "Yes" : "No"} />
        <Stat label="Mean Novelty" value={gcfContext.mean_novelty.toFixed(3)} />
      </div>

      {distance !== null && (
        <p className="text-xs text-muted-foreground">
          Distance to representative: {distance.toFixed(4)}
        </p>
      )}

      {gcfContext.known_chemistry_annotation && (
        <p className="text-xs">
          Known chemistry:{" "}
          <span className="font-medium">{gcfContext.known_chemistry_annotation}</span>
        </p>
      )}

      {/* Taxonomy distribution */}
      {gcfContext.taxonomy_distribution.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">
            Taxonomy distribution
          </p>
          <div className="flex flex-wrap gap-1">
            {gcfContext.taxonomy_distribution.slice(0, 8).map((t) => (
              <span
                key={t.taxonomy_family}
                className="rounded bg-muted px-1.5 py-0.5 text-[10px]"
              >
                {t.taxonomy_family} ({t.count})
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Core domains */}
      {gcfContext.domain_frequency.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">
            Core domains ({">"}80% of members)
          </p>
          <div className="flex flex-wrap gap-1">
            {gcfContext.domain_frequency
              .filter((d) => d.category === "core")
              .slice(0, 10)
              .map((d) => (
                <span
                  key={d.domain_acc}
                  className="rounded bg-blue-50 px-1.5 py-0.5 text-[10px] text-blue-700"
                >
                  {d.domain_name} ({(d.frequency * 100).toFixed(0)}%)
                </span>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border p-2 text-center">
      <p className="text-[10px] text-muted-foreground">{label}</p>
      <p className="text-sm font-semibold">{value}</p>
    </div>
  );
}
