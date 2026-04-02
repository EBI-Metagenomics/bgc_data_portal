import { useQuery } from "@tanstack/react-query";
import { fetchAssemblyScatter, type AssemblyScatterParams } from "@/api/assemblies";
import { useFilterStore } from "@/stores/filter-store";

export function useAssemblyScatter(xAxis: string, yAxis: string) {
  const filters = useFilterStore();

  const params: AssemblyScatterParams = {
    x_axis: xAxis,
    y_axis: yAxis,
    type_strain_only: filters.typeStrainOnly || undefined,
    taxonomy_path: filters.taxonomyPath || undefined,
    assembly_type: filters.assemblyType || undefined,
    bgc_class: filters.bgcClass || undefined,
  };

  return useQuery({
    queryKey: ["assembly-scatter", params],
    queryFn: () => fetchAssemblyScatter(params),
    enabled: filters.exploreQueryTriggered,
  });
}
