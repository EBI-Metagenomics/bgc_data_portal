import { useFilterStore } from "@/stores/filter-store";

const TYPES = ["", "metagenome", "genome", "region"] as const;
const LABELS: Record<string, string> = {
  "": "All types",
  metagenome: "Metagenome",
  genome: "Genome",
  region: "Region",
};

export function AssemblyTypeFilter() {
  const assemblyType = useFilterStore((s) => s.assemblyType);
  const setAssemblyType = useFilterStore((s) => s.setAssemblyType);

  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-muted-foreground">Assembly Type</label>
      <select
        value={assemblyType}
        onChange={(e) => setAssemblyType(e.target.value)}
        className="w-full rounded-md border bg-background px-2 py-1 text-sm"
      >
        {TYPES.map((t) => (
          <option key={t} value={t}>{LABELS[t]}</option>
        ))}
      </select>
    </div>
  );
}
