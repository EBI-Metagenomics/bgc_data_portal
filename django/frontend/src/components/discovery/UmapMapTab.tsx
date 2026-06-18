import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchIbgcUmap } from "@/api/ibgcs";
import { Loader2 } from "lucide-react";
import {
  appliedFiltersToApiParams,
  isAppliedFiltersEmpty,
  useDiscoveryStore,
} from "@/stores/discovery-store";
import { useIbgcIdsetParam } from "@/hooks/use-ibgc-idset-param";
import { IbgcScatterPlot } from "./IbgcScatterPlot";
import { EmptyScopeMessage } from "./EmptyScopeMessage";

export function UmapMapTab() {
  const resultIbgcIds = useDiscoveryStore((s) => s.resultIbgcIds);
  const resultSimilarityById = useDiscoveryStore(
    (s) => s.resultSimilarityById,
  );
  const applied = useDiscoveryStore((s) => s.appliedFilters);
  const assetToken = useDiscoveryStore((s) => s.assetToken);
  // Sample the same top-5k the roster shows (server caps both at 5k).
  const sortBy = useDiscoveryStore((s) => s.rosterSortBy);
  const order = useDiscoveryStore((s) => s.rosterOrder);

  const { param: idsetParam, ready: idsetReady } =
    useIbgcIdsetParam(resultIbgcIds);
  const filterParams = {
    ...appliedFiltersToApiParams(applied, assetToken),
    ...idsetParam,
  };
  const hasActiveScope =
    !isAppliedFiltersEmpty(applied) ||
    resultIbgcIds !== null ||
    assetToken !== null;

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["ibgc-umap", filterParams, sortBy, order],
    queryFn: () =>
      fetchIbgcUmap({
        include_partials: true,
        // pident/qcov are client-only roster metrics, not map sort columns;
        // the allow-list is fully plotted so order is moot — fold to similarity.
        sort_by: sortBy === "pident" || sortBy === "qcov" ? "similarity" : sortBy,
        order,
        ...filterParams,
      }),
    enabled: hasActiveScope && idsetReady,
  });

  const points = useMemo(() => {
    if (!data) return [];
    return data.map((p) => ({
      id: p.id,
      x: p.umap_x,
      y: p.umap_y,
      is_partial: p.is_partial,
      is_validated: p.is_validated,
      is_type_strain: p.is_type_strain,
      umap_projected: p.umap_projected,
      is_asset: p.is_asset ?? false,
      classification_path: p.classification_path,
      novelty_score: p.novelty_score,
      label: p.label,
      similarity_score: resultSimilarityById?.[p.id] ?? null,
    }));
  }, [data, resultSimilarityById]);

  if (!hasActiveScope) {
    return (
      <div className="flex h-full flex-col p-3">
        <div className="flex flex-1 items-stretch overflow-hidden rounded border bg-card">
          <EmptyScopeMessage surface="UMAP map" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col p-3">
      <div className="flex flex-1 items-stretch overflow-hidden rounded border bg-card">
        {isLoading ? (
          <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
            <Loader2 className="mr-2 inline h-4 w-4 animate-spin" />
            Loading UMAP…
          </div>
        ) : isError ? (
          <div className="flex flex-1 items-center justify-center text-sm text-destructive">
            {(error as Error)?.message ?? "Failed to load UMAP"}
          </div>
        ) : (
          <IbgcScatterPlot
            points={points}
            xLabel="UMAP 1"
            yLabel="UMAP 2"
          />
        )}
      </div>
    </div>
  );
}
