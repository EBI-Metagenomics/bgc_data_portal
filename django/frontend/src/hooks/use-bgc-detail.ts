import { useQuery } from "@tanstack/react-query";
import { fetchBgcDetail } from "@/api/bgcs";

export function useBgcDetail(bgcId: number | null) {
  return useQuery({
    queryKey: ["bgc-detail", bgcId],
    queryFn: () => fetchBgcDetail(bgcId!),
    enabled: bgcId !== null,
  });
}
