import { useQuery } from "@tanstack/react-query";
import { fetchAssemblyScatter, type AssemblyScatterParams } from "@/api/assemblies";
import { useFilterStore } from "@/stores/filter-store";
import { useAssemblyWeightStore } from "@/stores/assembly-weight-store";

export function useAssemblyScatter(xAxis: string, yAxis: string) {
  const filters = useFilterStore();
  const weights = useAssemblyWeightStore();

  const params: AssemblyScatterParams = {
    x_axis: xAxis,
    y_axis: yAxis,
    type_strain_only: filters.typeStrainOnly || undefined,
    taxonomy_path: filters.taxonomyPath || undefined,
    assembly_type: filters.assemblyType || undefined,
    bgc_class: filters.bgcClass || undefined,
    w_diversity: weights.w_diversity,
    w_novelty: weights.w_novelty,
    w_density: weights.w_density,
  };

  return useQuery({
    queryKey: ["assembly-scatter", params],
    queryFn: () => fetchAssemblyScatter(params),
  });
}
