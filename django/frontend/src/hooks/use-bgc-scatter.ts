import { useQuery } from "@tanstack/react-query";
import { fetchBgcScatter, type BgcScatterParams } from "@/api/bgcs";
import { useFilterStore } from "@/stores/filter-store";

export function useBgcScatter(options: {
  xAxis?: string;
  yAxis?: string;
  assemblyIds?: number[];
  bgcIds?: number[];
  includeMibig?: boolean;
  enabled?: boolean;
}) {
  const {
    xAxis,
    yAxis,
    assemblyIds,
    bgcIds,
    includeMibig = true,
    enabled = true,
  } = options;

  const bgcClass = useFilterStore((s) => s.bgcClass);

  const params: BgcScatterParams = {
    include_mibig: includeMibig,
    bgc_class: bgcClass || undefined,
    assembly_ids: assemblyIds?.join(",") || undefined,
    bgc_ids: bgcIds?.join(",") || undefined,
    xAxis,
    yAxis,
  };

  return useQuery({
    queryKey: ["bgc-scatter", params],
    queryFn: () => fetchBgcScatter(params),
    enabled,
  });
}
