import { useQuery } from "@tanstack/react-query";
import { fetchAssemblyRoster, type AssemblyRosterParams } from "@/api/assemblies";
import { useFilterStore } from "@/stores/filter-store";
import { useAssemblyWeightStore } from "@/stores/assembly-weight-store";
import { useState } from "react";

export function useAssemblyRoster() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [sortBy, setSortBy] = useState("composite_score");
  const [order, setOrder] = useState<"asc" | "desc">("desc");

  const filters = useFilterStore();
  const weights = useAssemblyWeightStore();

  const params: AssemblyRosterParams = {
    page,
    page_size: pageSize,
    sort_by: sortBy,
    order,
    search: filters.search || undefined,
    type_strain_only: filters.typeStrainOnly || undefined,
    taxonomy_path: filters.taxonomyPath || undefined,
    assembly_type: filters.assemblyType || undefined,
    bgc_class: filters.bgcClass || undefined,
    biome_lineage: filters.biomeLineage || undefined,
    bgc_accession: filters.bgcAccession || undefined,
    assembly_accession: filters.assemblyAccession || undefined,
    assembly_ids: filters.assemblyIds || undefined,
    w_diversity: weights.w_diversity,
    w_novelty: weights.w_novelty,
    w_density: weights.w_density,
  };

  const query = useQuery({
    queryKey: ["assembly-roster", params],
    queryFn: () => fetchAssemblyRoster(params),
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
