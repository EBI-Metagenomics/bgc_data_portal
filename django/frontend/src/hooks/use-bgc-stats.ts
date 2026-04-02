import { useQuery } from "@tanstack/react-query";
import { fetchBgcStats } from "@/api/bgcs";
import { useSelectionStore } from "@/stores/selection-store";
import { useShortlistStore } from "@/stores/shortlist-store";

export function useBgcStats(options?: {
  assemblyIdOverride?: number;
  bgcIds?: number[];
}) {
  const { assemblyIdOverride, bgcIds } = options ?? {};
  const activeAssemblyId = useSelectionStore((s) => s.activeAssemblyId);
  const assemblyShortlist = useShortlistStore((s) => s.assemblies);

  const hasBgcIds = bgcIds != null && bgcIds.length > 0;

  const assemblyIds = assemblyIdOverride
    ? [assemblyIdOverride]
    : assemblyShortlist.length > 0
      ? assemblyShortlist.map((g) => g.id)
      : activeAssemblyId
        ? [activeAssemblyId]
        : [];

  const bgcIdsStr = hasBgcIds ? bgcIds.join(",") : undefined;
  const assemblyIdsStr =
    !hasBgcIds && assemblyIds.length > 0 ? assemblyIds.join(",") : undefined;

  const enabled = hasBgcIds || assemblyIds.length > 0;

  return useQuery({
    queryKey: ["bgc-stats", bgcIdsStr ?? assemblyIdsStr],
    queryFn: () =>
      fetchBgcStats({
        bgc_ids: bgcIdsStr,
        assembly_ids: bgcIdsStr ? undefined : assemblyIdsStr,
      }),
    enabled,
    staleTime: 30_000,
  });
}
