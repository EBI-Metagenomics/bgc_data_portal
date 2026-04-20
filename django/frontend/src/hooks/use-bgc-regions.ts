import { useQuery } from "@tanstack/react-query";
import { fetchBgcRegions } from "@/api/bgcs";

export function useBgcRegions(bgcIds: number[]) {
  const ids = [...bgcIds].sort((a, b) => a - b);
  return useQuery({
    queryKey: ["bgc-regions", ids],
    queryFn: () => fetchBgcRegions(ids),
    enabled: ids.length > 0,
  });
}
