import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { accessionKindLabel, classifyAccession } from "@/lib/accession";
import { useFilterStore } from "@/stores/filter-store";
import { FilterChip } from "./FilterChip";

export function AccessionsFilter() {
  const accession = useFilterStore((s) => s.accession);
  const setAccession = useFilterStore((s) => s.setAccession);

  // Multiple comma-separated accessions are OR-ed by the backend, which also
  // owns the per-token kind detection. The single-token hint below is purely
  // cosmetic (helps the user confirm what they typed) — not used for querying.
  const tokens = accession
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
  const activeCount = tokens.length;
  const singleKind = tokens.length === 1 ? classifyAccession(tokens[0]!) : null;

  return (
    <FilterChip
      label="Accessions"
      count={activeCount}
      onClear={() => setAccession("")}
      width="md"
    >
      <div className="space-y-1.5">
        <Label className="text-xs">Accession(s)</Label>
        <Input
          placeholder="Assembly, contig, BGC, iBGC or protein…"
          value={accession}
          onChange={(e) => setAccession(e.target.value)}
          className="vf-form__input h-8 text-xs"
        />
        <p className="text-[11px] leading-tight text-muted-foreground">
          {tokens.length > 1 ? (
            <>
              <span className="font-medium text-foreground">
                {tokens.length} accessions
              </span>{" "}
              — matched as OR.
            </>
          ) : singleKind ? (
            <>
              Detected:{" "}
              <span className="font-medium text-foreground">
                {accessionKindLabel(singleKind)}
              </span>
            </>
          ) : (
            <>
              e.g. <code>ERZ…</code>, <code>MGYB-AB12CD</code>,{" "}
              <code>MGYB-AB12CD-0A</code>, <code>MGYP…</code> or a contig id.
              Separate multiple with commas.
            </>
          )}
        </p>
      </div>
    </FilterChip>
  );
}
