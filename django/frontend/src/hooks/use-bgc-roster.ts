import { useQuery } from "@tanstack/react-query";
import { fetchBgcRoster, type BgcRosterParams } from "@/api/bgcs";
import { useSelectionStore } from "@/stores/selection-store";
import { useShortlistStore } from "@/stores/shortlist-store";
import { useState } from "react";

export function useBgcRoster(assemblyIdOverride?: number) {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [sortBy, setSortBy] = useState("novelty_score");
  const [order, setOrder] = useState<"asc" | "desc">("desc");

  const activeAssemblyId = useSelectionStore((s) => s.activeAssemblyId);
  const assemblyShortlist = useShortlistStore((s) => s.assemblies);

  // When an override is provided, use it directly (e.g. assess mode)
  const assemblyIds = assemblyIdOverride
    ? [assemblyIdOverride]
    : assemblyShortlist.length > 0
      ? assemblyShortlist.map((g) => g.id)
      : activeAssemblyId
        ? [activeAssemblyId]
        : [];

  const params: BgcRosterParams = {
    assembly_ids: assemblyIds.length > 0 ? assemblyIds.join(",") : undefined,
    sort_by: sortBy,
    order,
    page,
    page_size: pageSize,
  };

  const enabled = assemblyIds.length > 0;

  const query = useQuery({
    queryKey: ["bgc-roster", params],
    queryFn: () => fetchBgcRoster(params),
    enabled,
  });

  return {
    ...query,
    page,
    setPage,
    sortBy,
    setSortBy,
    order,
    setOrder,
  };
}
