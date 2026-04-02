import { useQuery } from "@tanstack/react-query";
import { fetchAssemblyScatter, type AssemblyScatterParams } from "@/api/assemblies";

export function useQueryAssemblyScatter(
  xAxis: string,
  yAxis: string,
  assemblyIds: number[]
) {
  const params: AssemblyScatterParams = {
    x_axis: xAxis,
    y_axis: yAxis,
    assembly_ids: assemblyIds.length > 0 ? assemblyIds.join(",") : undefined,
  };

  return useQuery({
    queryKey: ["query-assembly-scatter", params],
    queryFn: () => fetchAssemblyScatter(params),
    enabled: assemblyIds.length > 0,
  });
}
