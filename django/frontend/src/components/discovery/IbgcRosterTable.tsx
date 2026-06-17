import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchIbgcIds, fetchIbgcRoster } from "@/api/ibgcs";
import type { IbgcRosterParams } from "@/api/ibgcs";
import type { IbgcRosterItem } from "@/api/types";
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
} from "@/stores/discovery-store";
import { MAX_SHORTLIST, useShortlistStore } from "@/stores/shortlist-store";
import { IbgcContextMenu } from "./IbgcContextMenu";
import { EmptyScopeMessage } from "./EmptyScopeMessage";

// Display label for the server/client query-result cap (DASHBOARD_RESULT_CAP
// / QUERY_RESULT_CAP = 5000). Used only in the "results capped" banner.
const QUERY_RESULT_CAP_LABEL = "5,000";

type SortKey =
  | "novelty_score"
  | "domain_novelty"
  | "size_kb"
  | "id"
  | "similarity"
  | "pident"
  | "qcov";

type ColumnKey =
  | SortKey
  | "label"
  | "bgc_class"
  | "tools"
  | "assembly"
  | "collection"
  | "similarity"
  | "best_hit";

const BASE_TAIL_COLUMNS: { key: ColumnKey; label: string }[] = [
  { key: "bgc_class", label: "Class" },
  { key: "size_kb", label: "Size (kb)" },
  { key: "novelty_score", label: "Novelty" },
  { key: "domain_novelty", label: "Dom. nov." },
  { key: "tools", label: "Sources" },
  { key: "assembly", label: "Assembly" },
  { key: "collection", label: "Collection" },
];

function columnsFor(searchSource: string | null) {
  // Sequence-search swaps the Sim. column for a Bitscore column and adds
  // Identity %, Query cov. % and Best hit columns from the winning CDS.
  // Bitscore/Identity %/Query cov. % all sort via the same client-side
  // mechanism: the roster reorders the result allow-list (``ibgc_ids``) by
  // the chosen metric and the server's ``sort_by=similarity`` preserves that
  // order (asc flips it). Default stays bitscore.
  if (searchSource === "sequence") {
    return [
      { key: "label" as ColumnKey, label: "iBGC" },
      { key: "similarity" as ColumnKey, label: "Bitscore" },
      { key: "pident" as ColumnKey, label: "Identity %" },
      { key: "qcov" as ColumnKey, label: "Query cov. %" },
      { key: "best_hit" as ColumnKey, label: "Best hit" },
      ...BASE_TAIL_COLUMNS,
    ];
  }
  return [
    { key: "label" as ColumnKey, label: "iBGC" },
    { key: "similarity" as ColumnKey, label: "Sim." },
    ...BASE_TAIL_COLUMNS,
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

  // When a Find-Similar-iBGCs or Sequence query lands, the result allow-list
  // is in score-descending order (Dice / bitscore); default the roster sort
  // to "similarity" so the table mirrors that rank. The user can still click
  // any other column header to override. We trigger off ``searchSource`` so
  // the same logic covers any score-emitting source.
  useEffect(() => {
    if (searchSource === "similar_ibgc" || searchSource === "sequence") {
      setRosterSort("similarity", "desc");
    }
  }, [searchSource, setRosterSort]);
  const resultSimilarityById = useDiscoveryStore(
    (s) => s.resultSimilarityById,
  );
  const resultBestHitProteinById = useDiscoveryStore(
    (s) => s.resultBestHitProteinById,
  );
  const resultPidentById = useDiscoveryStore((s) => s.resultPidentById);
  const resultQcoverageById = useDiscoveryStore((s) => s.resultQcoverageById);
  const resultTotalMatched = useDiscoveryStore((s) => s.resultTotalMatched);
  const resultCapped = useDiscoveryStore((s) => s.resultCapped);
  const applied = useDiscoveryStore((s) => s.appliedFilters);
  const assetToken = useDiscoveryStore((s) => s.assetToken);

  const COLUMNS = columnsFor(searchSource);

  const filterParams = appliedFiltersToApiParams(
    applied,
    resultIbgcIds,
    assetToken,
  );

  // Bitscore/Identity %/Query cov. % are per-hit query metrics, not server
  // columns. For these we rank the result allow-list client-side by the
  // chosen metric map and send sort_by="similarity" — the server orders rows
  // by their position in the (DESC-ranked) ``ibgc_ids`` list, and flips it for
  // order="asc". Stored-column sorts (novelty/size/…) pass straight through.
  const METRIC_MAPS: Record<string, Record<number, number> | null> = {
    similarity: resultSimilarityById,
    pident: resultPidentById,
    qcov: resultQcoverageById,
  };
  const isMetricSort =
    sortBy === "similarity" || sortBy === "pident" || sortBy === "qcov";
  const effectiveSortBy: IbgcRosterParams["sort_by"] = isMetricSort
    ? "similarity"
    : (sortBy as IbgcRosterParams["sort_by"]);
  if (isMetricSort && resultIbgcIds && resultIbgcIds.length > 0) {
    const scoreMap = METRIC_MAPS[sortBy] ?? {};
    const ordered = [...resultIbgcIds].sort(
      (a, b) => (scoreMap?.[b] ?? -Infinity) - (scoreMap?.[a] ?? -Infinity),
    );
    filterParams.ibgc_ids = ordered.join(",");
  }
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
    queryKey: [
      "ibgc-roster",
      page,
      pageSize,
      sortBy,
      order,
      filterParams,
    ],
    queryFn: () =>
      fetchIbgcRoster({
        page,
        page_size: pageSize,
        sort_by: effectiveSortBy,
        order,
        ...filterParams,
      }),
    enabled: hasActiveScope,
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

  const toggleSort = (key: SortKey) => {
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
              {COLUMNS.map((col) => {
                const sortable = (
                  [
                    "size_kb",
                    "novelty_score",
                    "domain_novelty",
                    "similarity",
                    "pident",
                    "qcov",
                  ] as readonly string[]
                ).includes(col.key);
                return (
                  <TableHead
                    key={col.key}
                    className={
                      sortable
                        ? "cursor-pointer select-none whitespace-nowrap"
                        : "whitespace-nowrap"
                    }
                    onClick={
                      sortable
                        ? () => toggleSort(col.key as SortKey)
                        : undefined
                    }
                  >
                    {col.label}
                    {sortable && sortBy === col.key && (
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
                <TableCell colSpan={COLUMNS.length} className="text-center py-8">
                  <Loader2 className="inline h-4 w-4 animate-spin" /> Loading…
                </TableCell>
              </TableRow>
            )}
            {isError && (
              <TableRow>
                <TableCell
                  colSpan={COLUMNS.length}
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
                  searchSource={searchSource}
                  similarityOverride={
                    resultSimilarityById?.[ibgc.id] ?? null
                  }
                  bestHitProteinOverride={
                    resultBestHitProteinById?.[ibgc.id] ?? null
                  }
                  pidentOverride={resultPidentById?.[ibgc.id] ?? null}
                  qcoverageOverride={resultQcoverageById?.[ibgc.id] ?? null}
                  onSelect={() => setCompareIbgcId(ibgc.id)}
                />
              ))}
            {!isLoading && items.length === 0 && (
              <TableRow>
                <TableCell
                  colSpan={COLUMNS.length}
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
  searchSource: string | null;
  /** Bitscore / Dice score from the active query, overlaid on the row
   *  because ``/ibgcs/roster/`` doesn't carry per-query metrics. */
  similarityOverride: number | null;
  bestHitProteinOverride: string | null;
  /** % identity / query coverage (0–100) of the winning CDS — sequence
   *  search only; overlaid for the same reason as similarityOverride. */
  pidentOverride: number | null;
  qcoverageOverride: number | null;
  onSelect: () => void;
}

function IbgcRosterRow({
  ibgc,
  selected,
  searchSource,
  similarityOverride,
  bestHitProteinOverride,
  pidentOverride,
  qcoverageOverride,
  onSelect,
}: IbgcRosterRowProps) {
  const isSeq = searchSource === "sequence";
  const similarity = similarityOverride ?? ibgc.similarity_score;
  const bestHit = bestHitProteinOverride ?? ibgc.best_hit_protein_id;
  const pident = pidentOverride ?? ibgc.best_pident;
  const qcoverage = qcoverageOverride ?? ibgc.best_qcoverage;
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
        {isSeq ? (
          <>
            <TableCell className="font-mono">
              {similarity != null ? similarity.toFixed(1) : "—"}
            </TableCell>
            <TableCell className="font-mono">
              {pident != null ? pident.toFixed(1) : "—"}
            </TableCell>
            <TableCell className="font-mono">
              {qcoverage != null ? qcoverage.toFixed(1) : "—"}
            </TableCell>
            <TableCell className="font-mono text-xs">
              {bestHit ?? "—"}
            </TableCell>
          </>
        ) : (
          <TableCell className="font-mono">
            {similarity != null ? similarity.toFixed(3) : "—"}
          </TableCell>
        )}
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
