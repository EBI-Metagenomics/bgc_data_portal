import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { accessionKindLabel, classifyAccession } from "@/lib/accession";
import { useFilterStore } from "@/stores/filter-store";
import { FilterChip } from "./FilterChip";

export function AccessionsFilter() {
  const accession = useFilterStore((s) => s.accession);
  const setAccession = useFilterStore((s) => s.setAccession);

  const trimmed = accession.trim();
  const activeCount = trimmed ? 1 : 0;
  const detectedKind = trimmed ? classifyAccession(trimmed) : null;

  return (
    <FilterChip
      label="Accessions"
      count={activeCount}
      onClear={() => setAccession("")}
      width="md"
    >
      <div className="space-y-1.5">
        <Label className="text-xs">Accession</Label>
        <Input
          placeholder="Assembly, contig, BGC, iBGC or protein…"
          value={accession}
          onChange={(e) => setAccession(e.target.value)}
          className="vf-form__input h-8 text-xs"
        />
        <p className="text-[11px] leading-tight text-muted-foreground">
          {detectedKind ? (
            <>
              Detected:{" "}
              <span className="font-medium text-foreground">
                {accessionKindLabel(detectedKind)}
              </span>
            </>
          ) : (
            <>
              e.g. <code>ERZ…</code>, <code>MGYB-AB12CD</code>,{" "}
              <code>MGYB-AB12CD-0A</code>, <code>MGYP…</code> or a contig id
            </>
          )}
        </p>
      </div>
    </FilterChip>
  );
}
