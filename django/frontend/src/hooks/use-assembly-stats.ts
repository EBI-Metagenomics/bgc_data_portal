import { useQuery } from "@tanstack/react-query";
import { fetchAssemblyStats, type AssemblyStatsParams } from "@/api/assemblies";
import { classifyAccession } from "@/lib/accession";
import { useFilterStore } from "@/stores/filter-store";

export function useAssemblyStats(assemblyIds?: string, enabled: boolean = true) {
  const filters = useFilterStore();

  // Route the single smart accession field to the legacy split params the
  // assembly endpoints expect (see use-assembly-roster for the rationale).
  const acc = filters.accession.trim();
  const accIsAssembly = acc !== "" && classifyAccession(acc) === "assembly";

  const params: AssemblyStatsParams = {
    search: filters.search || undefined,
    source_names: filters.sourceNames.length ? filters.sourceNames.join(",") : undefined,
    detector_tools: filters.detectorTools.length ? filters.detectorTools.join(",") : undefined,
    taxonomy_path: filters.taxonomyPath || undefined,
    assembly_type: filters.assemblyType || undefined,
    bgc_class: filters.bgcClass || undefined,
    biome_lineage: filters.biomeLineage || undefined,
    bgc_accession: acc && !accIsAssembly ? acc : undefined,
    assembly_accession: accIsAssembly ? acc : undefined,
    assembly_ids: assemblyIds,
  };

  return useQuery({
    queryKey: ["assembly-stats", params],
    queryFn: () => fetchAssemblyStats(params),
    staleTime: 30_000,
    enabled,
  });
}
