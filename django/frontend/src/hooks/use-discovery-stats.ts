import { useQuery } from "@tanstack/react-query";
import { fetchDiscoveryStats } from "@/api/discovery-stats";

export function useDiscoveryStats() {
  return useQuery({
    queryKey: ["discovery-stats"],
    queryFn: fetchDiscoveryStats,
    staleTime: 5 * 60_000,
  });
}
