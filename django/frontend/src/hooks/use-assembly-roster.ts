import { useQuery } from "@tanstack/react-query";
import { fetchAssemblyRoster, type AssemblyRosterParams } from "@/api/assemblies";
import { classifyAccession } from "@/lib/accession";
import { useFilterStore } from "@/stores/filter-store";
import { useState } from "react";

export function useAssemblyRoster() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [sortBy, setSortBy] = useState("bgc_novelty_score");
  const [order, setOrder] = useState<"asc" | "desc">("desc");

  const filters = useFilterStore();

  // The assembly-side endpoints still take the legacy split accession params.
  // Route the single smart field: assembly-looking accessions go to
  // ``assembly_accession``; everything else falls through to the MGYB-aware
  // ``bgc_accession`` slot (which also substring-matches).
  const acc = filters.accession.trim();
  const accIsAssembly = acc !== "" && classifyAccession(acc) === "assembly";

  const params: AssemblyRosterParams = {
    page,
    page_size: pageSize,
    sort_by: sortBy,
    order,
    search: filters.search || undefined,
    source_names: filters.sourceNames.length ? filters.sourceNames.join(",") : undefined,
    detector_tools: filters.detectorTools.length ? filters.detectorTools.join(",") : undefined,
    taxonomy_path: filters.taxonomyPath || undefined,
    assembly_type: filters.assemblyType || undefined,
    bgc_class: filters.bgcClass || undefined,
    biome_lineage: filters.biomeLineage || undefined,
    bgc_accession: acc && !accIsAssembly ? acc : undefined,
    assembly_accession: accIsAssembly ? acc : undefined,
    assembly_ids: filters.assemblyIds || undefined,
  };

  const query = useQuery({
    queryKey: ["assembly-roster", params],
    queryFn: () => fetchAssemblyRoster(params),
    enabled: filters.exploreQueryTriggered,
  });

  return {
    ...query,
    page,
    setPage,
    pageSize,
    setPageSize,
    sortBy,
    setSortBy,
    order,
    setOrder,
  };
}
