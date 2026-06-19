import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchIbgcDetail, fetchIbgcScatter, toMapSortBy } from "@/api/ibgcs";
import {
  appliedFiltersToApiParams,
  isAppliedFiltersEmpty,
  useDiscoveryStore,
} from "@/stores/discovery-store";
import { useIbgcIdsetParam } from "@/hooks/use-ibgc-idset-param";
import type {
  CriterionColumn,
  CriterionScore,
  IbgcDetail,
  IbgcScatterAxis,
  IbgcScatterPoint,
} from "@/api/types";
import { EmptyScopeMessage } from "./EmptyScopeMessage";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2 } from "lucide-react";
import { IbgcScatterPlot } from "./IbgcScatterPlot";

const STABLE_AXES: { value: IbgcScatterAxis; label: string }[] = [
  { value: "novelty_score", label: "Novelty" },
  { value: "domain_novelty", label: "Domain novelty" },
  { value: "size_kb", label: "Size (kb)" },
  { value: "n_cds", label: "# CDS" },
];

/** Legacy query axes whose values come from the single-similarity store maps
 *  (similar-iBGC / filter-only paths, which don't go through the combined
 *  query). Combined-query axes use ``score:<cid>[:metric]`` instead. */
const LEGACY_QUERY_AXES = new Set<IbgcScatterAxis>([
  "similarity_score",
  "best_pident",
  "best_qcoverage",
]);

/** A "query axis" is resolved client-side from the store score maps rather than
 *  the ``/ibgcs/scatter/`` endpoint: a per-criterion ``score:*`` axis or a
 *  legacy single-similarity axis. */
function isQueryAxis(axis: IbgcScatterAxis): boolean {
  return axis.startsWith("score:") || LEGACY_QUERY_AXES.has(axis);
}

function metricValue(sc: CriterionScore | undefined, key: string): number | null {
  if (!sc) return null;
  switch (key) {
    case "value":
      return sc.value;
    case "pident":
      return sc.pident;
    case "qcoverage":
      return sc.qcoverage;
    default:
      return null;
  }
}

/** Resolve a ``score:<cid>[:metric]`` axis for one iBGC from the combined-query
 *  per-criterion score maps. */
function criterionAxisValue(
  axis: string,
  id: number,
  scoresByCriterion: Record<string, Record<number, CriterionScore>> | null,
): number | null {
  const parts = axis.split(":"); // score:<cid>[:<metric>]
  const cid = parts[1];
  const metric = parts[2] ?? "value";
  if (!cid) return null;
  return metricValue(scoresByCriterion?.[cid]?.[id], metric);
}

/** Build the X/Y axis options. With a combined query active, each criterion
 *  contributes one plottable axis per metric (keyed ``score:<cid>[:metric]``);
 *  otherwise the legacy single-similarity axes back the similar-iBGC path. */
function buildAxisOptions(
  useCombined: boolean,
  criteria: CriterionColumn[] | null,
  searchSource: string | null,
): { value: IbgcScatterAxis; label: string }[] {
  const opts = [...STABLE_AXES];
  if (useCombined && criteria) {
    for (const c of criteria) {
      const multi = c.metrics.length > 1;
      for (const m of c.metrics) {
        if (!m.sortable) continue;
        const value = (
          m.key === "value" ? `score:${c.id}` : `score:${c.id}:${m.key}`
        ) as IbgcScatterAxis;
        opts.push({ value, label: multi ? `${c.label} · ${m.label}` : c.label });
      }
    }
    return opts;
  }
  opts.push({
    value: "similarity_score",
    label:
      searchSource === "sequence"
        ? "Bitscore"
        : searchSource === "domain"
          ? "Domain match (Dice)"
          : "Query similarity",
  });
  if (searchSource === "sequence") {
    opts.push({ value: "best_pident", label: "Identity %" });
    opts.push({ value: "best_qcoverage", label: "Query coverage %" });
  }
  return opts;
}

export function VariablesMapTab() {
  const xAxis = useDiscoveryStore((s) => s.variablesAxisX);
  const yAxis = useDiscoveryStore((s) => s.variablesAxisY);
  const setAxes = useDiscoveryStore((s) => s.setVariablesAxes);
  const resultIbgcIds = useDiscoveryStore((s) => s.resultIbgcIds);
  const resultSimilarityById = useDiscoveryStore(
    (s) => s.resultSimilarityById,
  );
  const resultPidentById = useDiscoveryStore((s) => s.resultPidentById);
  const resultQcoverageById = useDiscoveryStore(
    (s) => s.resultQcoverageById,
  );
  const resultCriteria = useDiscoveryStore((s) => s.resultCriteria);
  const resultScoresByCriterion = useDiscoveryStore(
    (s) => s.resultScoresByCriterion,
  );
  const searchSource = useDiscoveryStore((s) => s.searchSource);
  const applied = useDiscoveryStore((s) => s.appliedFilters);
  const referenceIbgcId = useDiscoveryStore((s) => s.referenceIbgcId);

  const useCombined = (resultCriteria?.length ?? 0) > 0;
  const axisOptions = buildAxisOptions(useCombined, resultCriteria, searchSource);
  const axisLabel = (axis: IbgcScatterAxis): string =>
    axisOptions.find((o) => o.value === axis)?.label ?? axis;

  // When the active criteria change, a previously-selected ``score:*`` axis can
  // reference a criterion that no longer exists — reset it to a stable axis so
  // the map doesn't get stuck plotting nothing. Keyed on the criteria id set so
  // this only fires when the result's columns actually change.
  const criteriaKey = (resultCriteria ?? []).map((c) => c.id).join(",");
  useEffect(() => {
    const valid = new Set(axisOptions.map((o) => o.value));
    const stale = (a: IbgcScatterAxis) => a.startsWith("score:") && !valid.has(a);
    if (stale(xAxis) || stale(yAxis)) {
      setAxes(
        stale(xAxis) ? "novelty_score" : xAxis,
        stale(yAxis) ? "domain_novelty" : yAxis,
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [criteriaKey]);

  const xIsQuery = isQueryAxis(xAxis);
  const yIsQuery = isQueryAxis(yAxis);
  const anyStableAxis = !xIsQuery || !yIsQuery;
  const anyQueryAxis = xIsQuery || yIsQuery;
  // Need scored results to plot a query axis: per-criterion scores for combined
  // queries, or the single-similarity map for the legacy similar-iBGC path.
  const haveQueryScores = useCombined
    ? resultScoresByCriterion != null
    : resultSimilarityById != null;
  const queryAxesUnplottable = anyQueryAxis && !haveQueryScores;

  const assetToken = useDiscoveryStore((s) => s.assetToken);
  // Sample the same top-5k the roster shows (server caps both at 5k). The sort
  // selects *which* points; the x/y axes only decide where they're plotted.
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

  // When at least one axis is stable, fetch ``/ibgcs/scatter/`` for it. If
  // only one axis is stable, request it on both x and y so we get the
  // value back regardless of which slot it ends up in.
  const scatterX: IbgcScatterAxis = xIsQuery
    ? yIsQuery
      ? "novelty_score"
      : yAxis
    : xAxis;
  const scatterY: IbgcScatterAxis = yIsQuery
    ? xIsQuery
      ? "novelty_score"
      : xAxis
    : yAxis;

  const { data: scatterData, isLoading, isError, error } = useQuery({
    queryKey: ["ibgc-scatter", scatterX, scatterY, filterParams, sortBy, order],
    queryFn: () =>
      fetchIbgcScatter({
        x_axis: scatterX,
        y_axis: scatterY,
        sort_by: toMapSortBy(sortBy),
        order,
        ...filterParams,
      }),
    enabled: anyStableAxis && hasActiveScope && idsetReady,
  });

  // ── Reference iBGC detail ────────────────────────────────────────────
  // The scatter endpoint drops iBGCs with NULL axis values (e.g.
  // domain_novelty is NULL for singleton GCFs) and also honours the
  // `ibgc_ids` allow-list from the active query. Either of those can hide
  // the pinned reference. We refetch its detail and inject it manually so
  // the reference halo is always rendered.
  const { data: refDetail } = useQuery({
    queryKey: [
      "ibgc-detail",
      referenceIbgcId,
      referenceIbgcId !== null && referenceIbgcId < 0 ? assetToken : null,
    ],
    queryFn: () => fetchIbgcDetail(referenceIbgcId as number, assetToken),
    enabled: referenceIbgcId !== null && hasActiveScope,
  });

  const points = useMemo(() => {
    if (queryAxesUnplottable) return [];

    // Index scatter points by id and remember which slot held what so the
    // resolver below can pluck the right scalar back out.
    const stableById = new Map<number, IbgcScatterPoint>();
    if (scatterData) {
      for (const p of scatterData) stableById.set(p.id, p);
    }

    function resolveAxis(axis: IbgcScatterAxis, id: number): number | null {
      if (axis.startsWith("score:")) {
        return criterionAxisValue(axis, id, resultScoresByCriterion);
      }
      if (axis === "similarity_score") {
        return resultSimilarityById?.[id] ?? null;
      }
      if (axis === "best_pident") {
        return resultPidentById?.[id] ?? null;
      }
      if (axis === "best_qcoverage") {
        return resultQcoverageById?.[id] ?? null;
      }
      const sp = stableById.get(id);
      if (!sp) return null;
      if (axis === scatterX) return sp.x;
      if (axis === scatterY) return sp.y;
      return null;
    }

    // Candidate ids: active-query allow-list when present, otherwise the
    // full scatter response.
    const candidateIds = resultIbgcIds ?? Array.from(stableById.keys());

    type PlotPoint = {
      id: number;
      x: number;
      y: number;
      is_partial: boolean;
      is_validated: boolean;
      is_type_strain: boolean;
      umap_projected: boolean;
      is_asset: boolean;
      classification_path?: string | null;
      novelty_score?: number | null;
      domain_novelty?: number | null;
      similarity_score?: number | null;
    };

    const base: PlotPoint[] = [];
    for (const id of candidateIds) {
      const x = resolveAxis(xAxis, id);
      const y = resolveAxis(yAxis, id);
      if (x == null || y == null) continue;
      const sp = stableById.get(id);
      base.push({
        id,
        x,
        y,
        is_partial: sp?.is_partial ?? false,
        is_validated: sp?.is_validated ?? false,
        is_type_strain: sp?.is_type_strain ?? false,
        umap_projected: sp?.umap_projected ?? false,
        is_asset: sp?.is_asset ?? id < 0,
        classification_path: sp?.classification_path,
        novelty_score: sp?.novelty_score,
        domain_novelty: sp?.domain_novelty,
        similarity_score: resultSimilarityById?.[id] ?? null,
      });
    }

    // Inject the pinned reference iBGC if it was dropped by the scatter
    // endpoint (NULL axis value or outside the query allow-list).
    if (
      referenceIbgcId != null &&
      refDetail &&
      refDetail.id === referenceIbgcId &&
      !base.some((p) => p.id === referenceIbgcId)
    ) {
      const x = axisValueFromDetail(
        refDetail,
        xAxis,
        resultSimilarityById,
        resultPidentById,
        resultQcoverageById,
        resultScoresByCriterion,
      );
      const y = axisValueFromDetail(
        refDetail,
        yAxis,
        resultSimilarityById,
        resultPidentById,
        resultQcoverageById,
        resultScoresByCriterion,
      );
      if (x != null && y != null) {
        base.push({
          id: refDetail.id,
          x,
          y,
          is_partial: refDetail.is_partial,
          is_validated: refDetail.is_validated,
          is_type_strain: refDetail.is_type_strain,
          umap_projected: refDetail.umap_projected,
          is_asset: refDetail.id < 0,
          classification_path: refDetail.classification_path,
          novelty_score: refDetail.novelty_score,
          domain_novelty: refDetail.domain_novelty,
          similarity_score: resultSimilarityById?.[refDetail.id] ?? null,
        });
      }
    }

    return base;
  }, [
    scatterData,
    resultIbgcIds,
    resultSimilarityById,
    resultPidentById,
    resultQcoverageById,
    resultScoresByCriterion,
    xAxis,
    yAxis,
    scatterX,
    scatterY,
    referenceIbgcId,
    refDetail,
    queryAxesUnplottable,
  ]);

  if (!hasActiveScope) {
    return (
      <div className="flex h-full flex-col p-3">
        <div className="flex flex-1 items-stretch overflow-hidden rounded border bg-card">
          <EmptyScopeMessage surface="Variables map" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col p-3">
      <div className="flex items-center gap-2 pb-2 text-xs">
        <span className="text-muted-foreground">X:</span>
        <Select
          value={xAxis}
          onValueChange={(v) => setAxes(v as IbgcScatterAxis, yAxis)}
        >
          <SelectTrigger className="h-8 w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {axisOptions.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="ml-3 text-muted-foreground">Y:</span>
        <Select
          value={yAxis}
          onValueChange={(v) => setAxes(xAxis, v as IbgcScatterAxis)}
        >
          <SelectTrigger className="h-8 w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {axisOptions.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {queryAxesUnplottable && (
          <span className="ml-2 text-amber-600">
            Run a query to populate this axis.
          </span>
        )}
      </div>

      <div className="flex flex-1 items-stretch overflow-hidden rounded border bg-card">
        {isLoading && anyStableAxis ? (
          <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
            <Loader2 className="mr-2 inline h-4 w-4 animate-spin" />
            Loading…
          </div>
        ) : isError && anyStableAxis ? (
          <div className="flex flex-1 items-center justify-center text-sm text-destructive">
            {(error as Error)?.message ?? "Failed to load scatter data"}
          </div>
        ) : (
          <IbgcScatterPlot
            points={points}
            xLabel={axisLabel(xAxis)}
            yLabel={axisLabel(yAxis)}
          />
        )}
      </div>
    </div>
  );
}

function axisValueFromDetail(
  d: IbgcDetail,
  axis: IbgcScatterAxis,
  resultSimilarityById: Record<number, number> | null,
  resultPidentById: Record<number, number> | null,
  resultQcoverageById: Record<number, number> | null,
  resultScoresByCriterion: Record<string, Record<number, CriterionScore>> | null,
): number | null {
  // Per-criterion axes resolve from the combined-query score maps (keyed by id),
  // independent of IbgcDetail.
  if (axis.startsWith("score:")) {
    return criterionAxisValue(axis, d.id, resultScoresByCriterion);
  }
  // IbgcDetail does not carry `n_cds`; if that axis is selected and the
  // reference is missing from the scatter response there is nothing
  // meaningful to inject — skip the halo rather than guess a coordinate.
  switch (axis) {
    case "novelty_score":
      return d.novelty_score ?? null;
    case "domain_novelty":
      return d.domain_novelty ?? null;
    case "size_kb":
      return d.size_kb ?? null;
    case "similarity_score":
      return resultSimilarityById?.[d.id] ?? null;
    case "best_pident":
      return resultPidentById?.[d.id] ?? null;
    case "best_qcoverage":
      return resultQcoverageById?.[d.id] ?? null;
    case "n_cds":
      return null;
    default:
      return null;
  }
}
