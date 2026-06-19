import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchIbgcIds, fetchIbgcRoster } from "@/api/ibgcs";
import type { IbgcRosterParams } from "@/api/ibgcs";
import type { CriterionColumn, CriterionScore, IbgcRosterItem } from "@/api/types";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, Loader2, Plus } from "lucide-react";
import { toast } from "sonner";
import {
  appliedFiltersToApiParams,
  isAppliedFiltersEmpty,
  useDiscoveryStore,
  type RosterSortKey,
} from "@/stores/discovery-store";
import { useIbgcIdsetParam } from "@/hooks/use-ibgc-idset-param";
import { MAX_SHORTLIST, useShortlistStore } from "@/stores/shortlist-store";
import { IbgcContextMenu } from "./IbgcContextMenu";
import { EmptyScopeMessage } from "./EmptyScopeMessage";

// Display label for the server/client query-result cap (DASHBOARD_RESULT_CAP
// / QUERY_RESULT_CAP = 5000). Used only in the "results capped" banner.
const QUERY_RESULT_CAP_LABEL = "5,000";

/** A header cell: ``sortKey`` set → clickable, drives the store's roster sort. */
interface HeaderCol {
  key: string;
  label: string;
  sortKey?: RosterSortKey;
}

/** A score column contributed by a criterion (combined query) or the legacy
 *  single-similarity path. ``read`` extracts the cell content for an iBGC. */
interface ScoreCol extends HeaderCol {
  read: (ibgc: IbgcRosterItem) => ReactNode;
}

const TAIL_COLUMNS: HeaderCol[] = [
  { key: "bgc_class", label: "Class" },
  { key: "size_kb", label: "Size (kb)", sortKey: "size_kb" },
  { key: "novelty_score", label: "Novelty", sortKey: "novelty_score" },
  { key: "domain_novelty", label: "Dom. nov.", sortKey: "domain_novelty" },
  { key: "tools", label: "Sources" },
  { key: "assembly", label: "Assembly" },
  { key: "collection", label: "Collection" },
];

const fixed1 = (v: number) => v.toFixed(1);
const fixed3 = (v: number) => v.toFixed(3);

/** Cell formatter for a criterion metric: bitscore/identity/coverage read more
 *  naturally at 1 dp; Dice / ChemOnt / match-fraction scores at 3 dp. */
function fmtFor(type: string, metricKey: string): (v: number) => string {
  if (metricKey === "pident" || metricKey === "qcoverage") return fixed1;
  if (type === "sequence" && metricKey === "value") return fixed1; // bitscore
  return fixed3;
}

function metricValue(
  sc: CriterionScore | undefined,
  key: string,
): number | null {
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

/**
 * Build one (or more) sortable score column per criterion. A criterion with a
 * single metric uses its own label as the header; multi-metric criteria
 * (sequence: bitscore/identity/coverage) use the metric labels and append a
 * non-sortable "Best hit" column. Cells read from ``scoresByCriterion``.
 */
function buildCriterionScoreCols(
  criteria: CriterionColumn[],
  scoresByCriterion: Record<string, Record<number, CriterionScore>> | null,
): ScoreCol[] {
  const cols: ScoreCol[] = [];
  for (const c of criteria) {
    const multi = c.metrics.length > 1;
    for (const m of c.metrics) {
      const fmt = fmtFor(c.type, m.key);
      cols.push({
        key: `${c.id}:${m.key}`,
        label: multi ? m.label : c.label,
        sortKey: m.sortable
          ? m.key === "value"
            ? (`score:${c.id}` as RosterSortKey)
            : (`score:${c.id}:${m.key}` as RosterSortKey)
          : undefined,
        read: (ibgc) => {
          const v = metricValue(scoresByCriterion?.[c.id]?.[ibgc.id], m.key);
          return v != null ? fmt(v) : "—";
        },
      });
    }
    if (c.type === "sequence") {
      cols.push({
        key: `${c.id}:best_hit`,
        label: "Best hit",
        read: (ibgc) =>
          scoresByCriterion?.[c.id]?.[ibgc.id]?.best_hit_protein_id ?? "—",
      });
    }
  }
  return cols;
}

/** Legacy score columns for non-combined sources (similar-iBGC, filter-only).
 *  Reads the single similarity + sequence sub-metric maps overlaid on rows. */
function buildLegacyScoreCols(
  searchSource: string | null,
  similarityById: Record<number, number> | null,
  pidentById: Record<number, number> | null,
  qcoverageById: Record<number, number> | null,
  bestHitById: Record<number, string> | null,
): ScoreCol[] {
  const sim = (ibgc: IbgcRosterItem) =>
    similarityById?.[ibgc.id] ?? ibgc.similarity_score;
  if (searchSource === "sequence") {
    return [
      {
        key: "l-bitscore",
        label: "Bitscore",
        sortKey: "similarity",
        read: (ibgc) => {
          const v = sim(ibgc);
          return v != null ? v.toFixed(1) : "—";
        },
      },
      {
        key: "l-pident",
        label: "Identity %",
        sortKey: "pident",
        read: (ibgc) => {
          const v = pidentById?.[ibgc.id] ?? ibgc.best_pident;
          return v != null ? v.toFixed(1) : "—";
        },
      },
      {
        key: "l-qcov",
        label: "Query cov. %",
        sortKey: "qcov",
        read: (ibgc) => {
          const v = qcoverageById?.[ibgc.id] ?? ibgc.best_qcoverage;
          return v != null ? v.toFixed(1) : "—";
        },
      },
      {
        key: "l-best-hit",
        label: "Best hit",
        read: (ibgc) => bestHitById?.[ibgc.id] ?? ibgc.best_hit_protein_id ?? "—",
      },
    ];
  }
  return [
    {
      key: "l-sim",
      label: "Sim.",
      sortKey: "similarity",
      read: (ibgc) => {
        const v = sim(ibgc);
        return v != null ? v.toFixed(3) : "—";
      },
    },
  ];
}

function fmtScore(v: number | null): string {
  return v == null ? "—" : v.toFixed(3);
}

export function IbgcRosterTable() {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  // Roster sort lives in the discovery store so the UMAP/Variables maps can
  // sample their top-5k by the same order (see store ``rosterSortBy``).
  const sortBy = useDiscoveryStore((s) => s.rosterSortBy);
  const order = useDiscoveryStore((s) => s.rosterOrder);
  const setRosterSort = useDiscoveryStore((s) => s.setRosterSort);

  const setCompareIbgcId = useDiscoveryStore((s) => s.setCompareIbgcId);
  const compareIbgcId = useDiscoveryStore((s) => s.compareIbgcId);
  const resultIbgcIds = useDiscoveryStore((s) => s.resultIbgcIds);
  const searchSource = useDiscoveryStore((s) => s.searchSource);
  const resultCriteria = useDiscoveryStore((s) => s.resultCriteria);
  const resultScoresByCriterion = useDiscoveryStore(
    (s) => s.resultScoresByCriterion,
  );

  const resultSimilarityById = useDiscoveryStore((s) => s.resultSimilarityById);
  const resultBestHitProteinById = useDiscoveryStore(
    (s) => s.resultBestHitProteinById,
  );
  const resultPidentById = useDiscoveryStore((s) => s.resultPidentById);
  const resultQcoverageById = useDiscoveryStore((s) => s.resultQcoverageById);
  const resultTotalMatched = useDiscoveryStore((s) => s.resultTotalMatched);
  const resultCapped = useDiscoveryStore((s) => s.resultCapped);
  const applied = useDiscoveryStore((s) => s.appliedFilters);
  const assetToken = useDiscoveryStore((s) => s.assetToken);

  const useCombined = (resultCriteria?.length ?? 0) > 0;
  const primaryCid = resultCriteria?.[0]?.id ?? null;

  // When a scored query lands, default the roster sort to its primary metric
  // so the table mirrors the result's best-first rank. Combined queries sort
  // by the primary criterion (``score:<id>``); the legacy similar-iBGC path
  // sorts by its single similarity column. The user can still click any header.
  useEffect(() => {
    if (primaryCid) {
      setRosterSort(`score:${primaryCid}`, "desc");
    } else if (searchSource === "similar_ibgc") {
      setRosterSort("similarity", "desc");
    }
  }, [primaryCid, searchSource, setRosterSort]);

  const scoreCols = useMemo(
    () =>
      useCombined
        ? buildCriterionScoreCols(resultCriteria!, resultScoresByCriterion)
        : buildLegacyScoreCols(
            searchSource,
            resultSimilarityById,
            resultPidentById,
            resultQcoverageById,
            resultBestHitProteinById,
          ),
    [
      useCombined,
      resultCriteria,
      resultScoresByCriterion,
      searchSource,
      resultSimilarityById,
      resultPidentById,
      resultQcoverageById,
      resultBestHitProteinById,
    ],
  );

  const columns: HeaderCol[] = useMemo(
    () => [{ key: "label", label: "iBGC" }, ...scoreCols, ...TAIL_COLUMNS],
    [scoreCols],
  );

  // Per-criterion / per-hit scores are not server columns. For these we rank
  // the result allow-list client-side by the chosen metric and send
  // sort_by="similarity" — the server orders rows by their position in the
  // (DESC-ranked) allow-list, and flips it for order="asc". Stored-column sorts
  // (novelty/size/…) pass straight through.
  const isMetricSort =
    sortBy.startsWith("score:") ||
    sortBy === "similarity" ||
    sortBy === "pident" ||
    sortBy === "qcov";
  const effectiveSortBy: IbgcRosterParams["sort_by"] = isMetricSort
    ? "similarity"
    : (sortBy as IbgcRosterParams["sort_by"]);

  // Score for the active metric sort — combined per-criterion key
  // (``score:<cid>[:metric]``) or a legacy single-metric map.
  const scoreForSort = useMemo(() => {
    return (id: number): number => {
      if (sortBy.startsWith("score:")) {
        const parts = sortBy.split(":"); // score:<cid>[:<metric>]
        const cid = parts[1];
        const metric = parts[2] ?? "value";
        if (!cid) return -Infinity;
        return metricValue(resultScoresByCriterion?.[cid]?.[id], metric) ?? -Infinity;
      }
      const map =
        sortBy === "pident"
          ? resultPidentById
          : sortBy === "qcov"
            ? resultQcoverageById
            : resultSimilarityById;
      return map?.[id] ?? -Infinity;
    };
  }, [
    sortBy,
    resultScoresByCriterion,
    resultPidentById,
    resultQcoverageById,
    resultSimilarityById,
  ]);

  // The allow-list scoping the request: re-ranked by the active metric for
  // metric sorts (so the server's array_position order mirrors the table),
  // otherwise the canonical best-first order. ``useIbgcIdsetParam`` turns it
  // into an inline CSV (small sets) or a server-cached token (large sets).
  const scopedIds = useMemo(() => {
    if (!resultIbgcIds || resultIbgcIds.length === 0) return resultIbgcIds;
    if (!isMetricSort) return resultIbgcIds;
    return [...resultIbgcIds].sort((a, b) => scoreForSort(b) - scoreForSort(a));
  }, [resultIbgcIds, isMetricSort, scoreForSort]);

  const { param: idsetParam, ready: idsetReady } = useIbgcIdsetParam(scopedIds);
  const filterParams = {
    ...appliedFiltersToApiParams(applied, assetToken),
    ...idsetParam,
  };
  const hasActiveScope =
    !isAppliedFiltersEmpty(applied) ||
    resultIbgcIds !== null ||
    assetToken !== null;

  // Reset to page 1 whenever the applied filter set or result allow-list
  // changes — otherwise a deep-page user could see an empty page after
  // narrowing filters.
  const filterKey = JSON.stringify(filterParams);
  useEffect(() => {
    setPage(1);
  }, [filterKey]);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["ibgc-roster", page, pageSize, sortBy, order, filterParams],
    queryFn: () =>
      fetchIbgcRoster({
        page,
        page_size: pageSize,
        sort_by: effectiveSortBy,
        order,
        ...filterParams,
      }),
    enabled: hasActiveScope && idsetReady,
  });

  const items = data?.items ?? [];
  const pagination = data?.pagination;

  const addBgcsBulk = useShortlistStore((s) => s.addBgcsBulk);
  const shortlistCount = useShortlistStore((s) => s.bgcs.length);
  const [isAddingAll, setIsAddingAll] = useState(false);

  const onAddAllToShortlist = async () => {
    if (isAddingAll) return;
    if (shortlistCount >= MAX_SHORTLIST) {
      toast.warning(`Shortlist is at the ${MAX_SHORTLIST} cap`);
      return;
    }
    setIsAddingAll(true);
    const toastId = toast.loading("Collecting iBGCs…");
    try {
      const resp = await fetchIbgcIds({
        sort_by: effectiveSortBy,
        order,
        ...filterParams,
      });
      if (resp.ids.length === 0) {
        toast.message("No iBGCs to add", { id: toastId });
        return;
      }
      const items = resp.ids.map((id) => ({ id, label: `iBGC-${id}` }));
      const { added, skipped } = addBgcsBulk(items);
      // ``skipped`` already includes capacity overflow within the returned
      // id batch; if the backend itself truncated the result set, prefix a
      // hint so the user knows the filter actually matched more.
      const truncatedNote = resp.truncated
        ? ` (filter matched ${resp.total_count.toLocaleString()} — only the top ${resp.ids.length.toLocaleString()} were considered)`
        : "";
      if (added === 0) {
        toast.warning(`Shortlist is at the ${MAX_SHORTLIST} cap`, { id: toastId });
      } else if (skipped > 0) {
        toast.success(
          `Added ${added} iBGCs; ${skipped} skipped — shortlist full${truncatedNote}`,
          { id: toastId },
        );
      } else {
        toast.success(`Added ${added} iBGCs to shortlist${truncatedNote}`, {
          id: toastId,
        });
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Add all failed: ${msg}`, { id: toastId });
    } finally {
      setIsAddingAll(false);
    }
  };

  const toggleSort = (key: RosterSortKey) => {
    if (key === sortBy) {
      setRosterSort(sortBy, order === "desc" ? "asc" : "desc");
    } else {
      setRosterSort(key, "desc");
    }
    setPage(1);
  };

  if (!hasActiveScope) {
    return (
      <div className="flex h-full flex-col" data-testid="ibgc-roster">
        <EmptyScopeMessage surface="iBGC roster" />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col" data-testid="ibgc-roster">
      {resultCapped && (
        <div
          className="border-b bg-amber-50 px-3 py-1.5 text-xs text-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
          data-testid="roster-cap-banner"
        >
          {resultTotalMatched != null
            ? `Showing the top ${(resultIbgcIds?.length ?? 0).toLocaleString()} of ${resultTotalMatched.toLocaleString()} matching iBGCs (ranked by score). Refine your query or filters to narrow the results.`
            : `Showing the top ${(resultIbgcIds?.length ?? 0).toLocaleString()} matching iBGCs — some query inputs were capped at ${QUERY_RESULT_CAP_LABEL}.`}
        </div>
      )}
      <Table containerClassName="flex-1 min-h-0">
        <TableHeader className="sticky top-0 bg-card z-10">
          <TableRow>
            {columns.map((col) => {
              const sortable = col.sortKey !== undefined;
              return (
                <TableHead
                  key={col.key}
                  className={
                    sortable
                      ? "cursor-pointer select-none whitespace-nowrap"
                      : "whitespace-nowrap"
                  }
                  onClick={
                    sortable ? () => toggleSort(col.sortKey!) : undefined
                  }
                >
                  {col.label}
                  {sortable && sortBy === col.sortKey && (
                    <span className="ml-1 text-xs">
                      {order === "desc" ? "▼" : "▲"}
                    </span>
                  )}
                </TableHead>
              );
            })}
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading && (
            <TableRow>
              <TableCell colSpan={columns.length} className="text-center py-8">
                <Loader2 className="inline h-4 w-4 animate-spin" /> Loading…
              </TableCell>
            </TableRow>
          )}
          {isError && (
            <TableRow>
              <TableCell
                colSpan={columns.length}
                className="text-center py-8 text-destructive"
              >
                Failed to load iBGCs.
              </TableCell>
            </TableRow>
          )}
          {!isLoading &&
            items.map((ibgc) => (
              <IbgcRosterRow
                key={ibgc.id}
                ibgc={ibgc}
                selected={compareIbgcId === ibgc.id}
                scoreCols={scoreCols}
                onSelect={() => setCompareIbgcId(ibgc.id)}
              />
            ))}
          {!isLoading && items.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={columns.length}
                className="text-center py-8 text-muted-foreground"
              >
                No iBGCs found.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      <Pagination
        page={page}
        totalPages={pagination?.total_pages ?? 1}
        totalCount={pagination?.total_count ?? 0}
        onChange={setPage}
        onAddAllToShortlist={onAddAllToShortlist}
        addAllDisabled={
          isLoading ||
          isAddingAll ||
          (pagination?.total_count ?? 0) === 0 ||
          shortlistCount >= MAX_SHORTLIST
        }
        addAllBusy={isAddingAll}
      />
    </div>
  );
}

interface IbgcRosterRowProps {
  ibgc: IbgcRosterItem;
  selected: boolean;
  /** Score columns to render between the iBGC label and the tail columns —
   *  one (or more) per active criterion, or the legacy single-similarity set. */
  scoreCols: ScoreCol[];
  onSelect: () => void;
}

function IbgcRosterRow({
  ibgc,
  selected,
  scoreCols,
  onSelect,
}: IbgcRosterRowProps) {
  return (
    <IbgcContextMenu
      ibgcId={ibgc.id}
      ibgcLabel={ibgc.accession || ibgc.label}
      isPartial={ibgc.umap_projected}
      isAsset={ibgc.is_asset}
    >
      <TableRow
        onClick={onSelect}
        data-testid="ibgc-roster-row"
        data-ibgc-id={ibgc.id}
        data-is-asset={ibgc.is_asset || undefined}
        className={
          "cursor-pointer " +
          (ibgc.is_asset
            ? "bg-amber-50 dark:bg-amber-950/30 hover:bg-amber-100 dark:hover:bg-amber-950/50 "
            : "") +
          (selected ? "bg-accent" : "hover:bg-muted/40")
        }
      >
        <TableCell className="font-mono text-xs">
          {ibgc.accession || ibgc.label}
          {ibgc.is_asset && (
            <Badge
              className="ml-2 h-4 px-1 text-[10px] text-white border-transparent"
              style={{ backgroundColor: "#b45309" }}
              data-testid="asset-submitted-badge"
            >
              SUBMITTED
            </Badge>
          )}
          {ibgc.is_validated && (
            <Badge variant="default" className="ml-2 h-4 px-1 text-[10px]">
              Validated
            </Badge>
          )}
          {ibgc.is_type_strain && (
            <Badge
              className="ml-2 h-4 px-1 text-[10px] text-white border-transparent"
              style={{ backgroundColor: "#018786" }}
            >
              Type Strain
            </Badge>
          )}
          {ibgc.is_partial && (
            <Badge
              variant="outline"
              className="ml-2 h-4 px-1 text-[10px] border-amber-300 bg-amber-100 text-amber-900 dark:border-amber-700/60 dark:bg-amber-950/40 dark:text-amber-200"
            >
              Partial
            </Badge>
          )}
        </TableCell>
        {scoreCols.map((col) => (
          <TableCell key={col.key} className="font-mono text-xs">
            {col.read(ibgc)}
          </TableCell>
        ))}
        <TableCell className="text-xs">{ibgc.bgc_class || "—"}</TableCell>
        <TableCell>{ibgc.size_kb.toFixed(1)}</TableCell>
        <TableCell>{fmtScore(ibgc.novelty_score)}</TableCell>
        <TableCell>{fmtScore(ibgc.domain_novelty)}</TableCell>
        <TableCell className="text-xs text-muted-foreground">
          {ibgc.source_tools.join(", ")}
        </TableCell>
        <TableCell className="text-xs">
          {ibgc.parent_assembly_accession ?? "—"}
        </TableCell>
        <TableCell className="text-xs text-muted-foreground">
          {ibgc.parent_assembly_collection ?? "—"}
        </TableCell>
      </TableRow>
    </IbgcContextMenu>
  );
}

interface PaginationProps {
  page: number;
  totalPages: number;
  totalCount: number;
  onChange: (page: number) => void;
  onAddAllToShortlist: () => void;
  addAllDisabled: boolean;
  addAllBusy: boolean;
}

function Pagination({
  page,
  totalPages,
  totalCount,
  onChange,
  onAddAllToShortlist,
  addAllDisabled,
  addAllBusy,
}: PaginationProps) {
  return (
    <div className="flex items-center justify-between border-t px-3 py-1.5 text-xs">
      <span className="text-muted-foreground">
        {totalCount.toLocaleString()} iBGCs · page {page}/{totalPages}
      </span>
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          className="h-7 gap-1 px-2 text-xs"
          disabled={addAllDisabled}
          onClick={onAddAllToShortlist}
          data-testid="add-all-to-shortlist"
        >
          {addAllBusy ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Plus className="h-3 w-3" />
          )}
          Add all to shortlist
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          disabled={page >= totalPages}
          onClick={() => onChange(page + 1)}
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
