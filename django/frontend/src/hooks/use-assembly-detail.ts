import { useQuery } from "@tanstack/react-query";
import { fetchAssemblyDetail } from "@/api/assemblies";

export function useAssemblyDetail(assemblyId: number | null) {
  return useQuery({
    queryKey: ["assembly-detail", assemblyId],
    queryFn: () => fetchAssemblyDetail(assemblyId!),
    enabled: assemblyId !== null,
  });
}
