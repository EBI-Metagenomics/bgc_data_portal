import { useQuery } from "@tanstack/react-query";
import { fetchAssemblyScatter, type AssemblyScatterParams } from "@/api/assemblies";
import { useAssemblyWeightStore } from "@/stores/assembly-weight-store";

export function useQueryAssemblyScatter(
  xAxis: string,
  yAxis: string,
  assemblyIds: number[]
) {
  const weights = useAssemblyWeightStore();

  const params: AssemblyScatterParams = {
    x_axis: xAxis,
    y_axis: yAxis,
    assembly_ids: assemblyIds.length > 0 ? assemblyIds.join(",") : undefined,
    w_diversity: weights.w_diversity,
    w_novelty: weights.w_novelty,
    w_density: weights.w_density,
  };

  return useQuery({
    queryKey: ["query-assembly-scatter", params],
    queryFn: () => fetchAssemblyScatter(params),
    enabled: assemblyIds.length > 0,
  });
}
