import { Button } from "@/components/ui/button";
import { RotateCcw } from "lucide-react";
import { SourceFilter } from "./SourceFilter";
import { DetectorFilter } from "./DetectorFilter";
import { AssemblyTypeFilter } from "./AssemblyTypeFilter";
import { TaxonomyFilter } from "./TaxonomyFilter";
import { BiomeLineageFilter } from "./BiomeLineageFilter";
import { BgcClassFilter } from "./BgcClassFilter";
import { GcfFilter } from "./GcfFilter";
import { ChemOntClassFilter } from "./ChemOntClassFilter";
import { AccessionsFilter } from "./AccessionsFilter";
import { DomainsFilter } from "./DomainsFilter";
import { LengthFilter } from "./LengthFilter";
import { SequenceFilter } from "./SequenceFilter";
import { ChemicalStructureFilter } from "./ChemicalStructureFilter";
import { LoadAssetChip } from "./LoadAssetChip";
import { useFilterStore } from "@/stores/filter-store";
import { useQueryStore } from "@/stores/query-store";

export function FilterPanel() {
  const clearFilters = useFilterStore((s) => s.clearFilters);
  const clearQuery = useQueryStore((s) => s.clearQuery);

  // The filter surface is split across two stores: scalar/list filters live in
  // filter-store, while the domain/architecture/sequence/chemical query state
  // lives in query-store. Reset must clear both so every filter returns to its
  // default (e.g. ARCH-mode domain text and sequence searches).
  const resetAll = () => {
    clearFilters();
    clearQuery();
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <SourceFilter />
      <DetectorFilter />
      <AssemblyTypeFilter />
      <TaxonomyFilter />
      <BiomeLineageFilter />
      <BgcClassFilter />
      <GcfFilter />
      <ChemOntClassFilter />
      <AccessionsFilter />
      <LengthFilter />
      <DomainsFilter />
      <SequenceFilter />
      <ChemicalStructureFilter />

      <LoadAssetChip />

      <Button
        variant="ghost"
        size="sm"
        className="h-8 gap-1 px-2 text-xs text-muted-foreground"
        onClick={resetAll}
      >
        <RotateCcw className="h-3 w-3" />
        Reset filters
      </Button>
    </div>
  );
}
