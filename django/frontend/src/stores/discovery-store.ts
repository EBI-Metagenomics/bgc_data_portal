import { create } from "zustand";
import type { AssetSummary } from "@/api/assets";
import type {
  CriterionColumn,
  CriterionScore,
  IbgcScatterAxis,
  RegionCds,
} from "@/api/types";
import { useFilterStore } from "@/stores/filter-store";

/**
 * Session state for the v2 Discovery dashboard.
 *
 * Persistence is intentionally OFF (per design decision): the reference iBGC
 * + compare slot reset on reload. URL state lives in route params, not here.
 */

export type ResultsTab = "roster" | "variables" | "umap";

/** Sort keys shared by the roster and the UMAP/Variables maps. The maps cap
 *  at 5k points server-side and sample the roster's top rows in this order, so
 *  "what's in the roster is what's in the plots". Mirrors the backend
 *  ``_apply_ibgc_sort`` accepted keys. */
export type RosterSortKey =
  | "novelty_score"
  | "domain_novelty"
  | "size_kb"
  | "id"
  | "similarity"
  // Sequence-search per-hit metrics. These are NOT backend sort columns —
  // the roster ranks the result allow-list client-side by the corresponding
  // metric map and sends sort_by="similarity" (array_position) so the server
  // preserves that order. Selectable only while a sequence result is active.
  | "pident"
  | "qcov"
  // Combined-query per-criterion sort keys: ``score:<criterionId>`` (primary
  // value) or ``score:<criterionId>:<metricKey>`` (e.g. a sequence pident).
  // Resolved by the combined status endpoint against its cached score maps.
  | `score:${string}`;

/** Which advanced-query path produced the current ``resultIbgcIds`` set.
 *  Lets the roster swap the "Sim." column for sequence-search-specific
 *  columns. ``null`` = no advanced query (filter-only run or fresh load). */
export type SearchSource =
  | "sequence"
  | "domain"
  | "domain_architecture"
  | "chemical"
  | "similar_ibgc"
  | null;

interface DiscoveryState {
  // Reference iBGC (top-right detail card, pinned across left-clicks).
  referenceIbgcId: number | null;
  setReferenceIbgcId: (id: number | null) => void;

  // Compare slot iBGC (bottom-right detail card; updated on left-click).
  compareIbgcId: number | null;
  setCompareIbgcId: (id: number | null) => void;

  // Selected CDS feeds the Protein Information panel below the detail
  // stack. We carry the full ``RegionCds`` object so the panel can render
  // Pfam annotations + protein sequence without an extra round-trip.
  selectedCds: RegionCds | null;
  setSelectedCds: (cds: RegionCds | null) => void;

  // Results card tab + axis selectors for the Variables Map.
  activeResultsTab: ResultsTab;
  setActiveResultsTab: (tab: ResultsTab) => void;

  variablesAxisX: IbgcScatterAxis;
  variablesAxisY: IbgcScatterAxis;
  setVariablesAxes: (x: IbgcScatterAxis, y: IbgcScatterAxis) => void;

  // Roster sort — lifted out of <IbgcRosterTable> into the store so the
  // UMAP + Variables maps can sample their top-5k by the SAME order the
  // roster displays (the server caps and sorts all three identically).
  rosterSortBy: RosterSortKey;
  rosterOrder: "asc" | "desc";
  setRosterSort: (sortBy: RosterSortKey, order: "asc" | "desc") => void;

  // Run Query result set — iBGC id allow-list applied by the roster + maps
  // when populated. Null = no active query, show everything.
  resultIbgcIds: number[] | null;
  /** Optional iBGC → similarity-score lookup populated by sequence/domain
   *  queries; used to colour scatter points by score. */
  resultSimilarityById: Record<number, number> | null;
  /** Optional iBGC → best-hit protein_id lookup populated by sequence
   *  protein search; overlaid onto roster rows since the standard
   *  ``/ibgcs/roster/`` endpoint does not carry per-query data. */
  resultBestHitProteinById: Record<number, string> | null;
  /** Percent identity (0–100) of the winning CDS per iBGC; feeds the
   *  Variables Map "Identity" axis. */
  resultPidentById: Record<number, number> | null;
  /** Query coverage (0–100) of the winning CDS per iBGC; feeds the
   *  Variables Map "Query coverage" axis. */
  resultQcoverageById: Record<number, number> | null;
  /** Which advanced-query path produced ``resultIbgcIds``; toggles the
   *  bitscore + best-hit-protein columns in the roster. */
  searchSource: SearchSource;
  /** Full match count before the 5k cap, and whether the result was capped.
   *  Drives the "showing top N of M" banner above the roster. ``null`` when
   *  no scored query is active. */
  resultTotalMatched: number | null;
  resultCapped: boolean;
  setQueryResult: (
    ids: number[] | null,
    similarity?: Record<number, number> | null,
    source?: SearchSource,
    bestHitProtein?: Record<number, string> | null,
    pident?: Record<number, number> | null,
    qcoverage?: Record<number, number> | null,
    totalMatched?: number | null,
    capped?: boolean,
  ) => void;

  // Combined multi-criterion query result. ``resultCriteria`` is the ordered
  // list of criterion-column descriptors (drives the roster's per-criterion
  // columns + the Variables-map axes); ``resultScoresByCriterion`` maps a
  // criterion id → (iBGC id → its score payload). Both null when no combined
  // query is active. The legacy ``result*ById`` maps above are back-filled
  // from the primary criterion so existing views keep working during the
  // migration to per-criterion columns.
  resultCriteria: CriterionColumn[] | null;
  resultScoresByCriterion: Record<string, Record<number, CriterionScore>> | null;
  setCombinedResult: (
    criteria: CriterionColumn[] | null,
    scoresByCriterion: Record<string, Record<number, CriterionScore>> | null,
  ) => void;

  // Snapshot of filter-store values taken when the user last pressed Run
  // Query. The roster/maps key off this — toggling a chip without pressing
  // Run Query does NOT refetch.
  appliedFilters: AppliedIbgcFilters;
  setAppliedFilters: (filters: AppliedIbgcFilters) => void;

  // Ephemeral asset (uploaded TGZ). Single-slot — a new upload replaces
  // the previous token on the server too via DELETE. Survives Run Query
  // resets so the asset iBGCs stay pinned to the dashboard.
  assetToken: string | null;
  assetSummary: AssetSummary | null;
  setAsset: (token: string | null, summary?: AssetSummary | null) => void;

  // Convenience: clear all selections (e.g., on a fresh Run Query).
  clearSelections: () => void;
}

export interface AppliedIbgcFilters {
  sourceNames: string[];
  detectorTools: string[];
  assemblyType: string;
  taxonomyPath: string;
  bgcClass: string;
  gcfPath: string;
  chemontIds: string[];
  // Flattened NP-class names selected across the L1/L2/L3 tree.
  npClasses: string[];
  biomeLineage: string;
  // Single smart accession field (assembly / contig / BGC / iBGC / protein).
  accession: string;
  assemblyIds: string;
  organism: string;
  // Free-text term matched against the iBGC's domain annotations. Drives
  // the landing-page keyword-search fallback (e.g. "Polyketide").
  domainText: string;
  // iBGC length bounds in kilobases. ``null`` = unbounded on that side.
  minLengthKb: number | null;
  maxLengthKb: number | null;
}

export const EMPTY_APPLIED_FILTERS: AppliedIbgcFilters = {
  sourceNames: [],
  detectorTools: [],
  assemblyType: "",
  taxonomyPath: "",
  bgcClass: "",
  gcfPath: "",
  chemontIds: [],
  npClasses: [],
  biomeLineage: "",
  accession: "",
  assemblyIds: "",
  organism: "",
  domainText: "",
  minLengthKb: null,
  maxLengthKb: null,
};

/** True when no filter chip is set in the applied snapshot.
 *  Combined with ``resultIbgcIds == null`` it gates the dashboard's
 *  empty-state CTA so we never fire an unbounded fetch on landing. */
export function isAppliedFiltersEmpty(applied: AppliedIbgcFilters): boolean {
  return (
    applied.sourceNames.length === 0 &&
    applied.detectorTools.length === 0 &&
    applied.chemontIds.length === 0 &&
    applied.npClasses.length === 0 &&
    applied.assemblyType === "" &&
    applied.taxonomyPath === "" &&
    applied.bgcClass === "" &&
    applied.gcfPath === "" &&
    applied.biomeLineage === "" &&
    applied.accession === "" &&
    applied.assemblyIds === "" &&
    applied.organism === "" &&
    applied.domainText === "" &&
    applied.minLengthKb == null &&
    applied.maxLengthKb == null
  );
}

/**
 * Build the iBGC API query-string surface from an applied-filter snapshot.
 * Empty values are dropped so the resulting object only carries active params
 * (cleaner cache keys and URLs).
 *
 * The Run Query result allow-list is NOT folded in here — it is resolved
 * separately by ``useIbgcIdsetParam`` (CSV for small sets, a server-cached
 * ``ibgc_ids_token`` for large ones) and merged by each consumer, so a
 * multi-thousand-id result never overflows the GET request line.
 *
 * Used by ``IbgcRosterTable``, the UMAP hook, the Variables-Map scatter hook
 * and the count hook so all four stay in lockstep with the same filter
 * contract.
 */
export function appliedFiltersToApiParams(
  applied: AppliedIbgcFilters,
  assetToken: string | null = null,
): Record<string, string> {
  const params: Record<string, string> = {};
  if (applied.sourceNames.length > 0) {
    params.source_names = applied.sourceNames.join(",");
  }
  if (applied.detectorTools.length > 0) {
    params.detector_tools = applied.detectorTools.join(",");
  }
  if (applied.assemblyType) params.assembly_type = applied.assemblyType;
  if (applied.taxonomyPath) params.taxonomy_path = applied.taxonomyPath;
  if (applied.bgcClass) params.bgc_class = applied.bgcClass;
  if (applied.gcfPath) params.leaf_path_prefix = applied.gcfPath;
  if (applied.chemontIds.length > 0) {
    params.chemont_ids = applied.chemontIds.join(",");
  }
  if (applied.npClasses.length > 0) {
    params.np_classes = applied.npClasses.join(",");
  }
  if (applied.biomeLineage) params.biome_lineage = applied.biomeLineage;
  if (applied.accession) params.accession = applied.accession;
  if (applied.assemblyIds) params.assembly_ids = applied.assemblyIds;
  if (applied.organism) params.organism = applied.organism;
  if (applied.domainText) params.domain_text = applied.domainText;
  if (applied.minLengthKb != null) {
    params.min_length_kb = String(applied.minLengthKb);
  }
  if (applied.maxLengthKb != null) {
    params.max_length_kb = String(applied.maxLengthKb);
  }
  if (assetToken) {
    params.asset_token = assetToken;
  }
  return params;
}

/**
 * Snapshot the live filter-chip store into an ``AppliedIbgcFilters`` object.
 *
 * Single source of truth for the filterStore → appliedFilters mapping so the
 * Run Query button (``use-run-ibgc-query``) and the landing-page keyword
 * redirect (``use-url-sync`` auto-run) stay in lockstep. Every chip in
 * ``FilterPanel`` must be represented here, otherwise its value is silently
 * discarded when a query runs.
 */
export function snapshotFiltersToApplied(): AppliedIbgcFilters {
  const f = useFilterStore.getState();
  return {
    sourceNames: f.sourceNames,
    detectorTools: f.detectorTools,
    assemblyType: f.assemblyType,
    taxonomyPath: f.taxonomyPath,
    bgcClass: f.bgcClass,
    gcfPath: f.gcfPath,
    chemontIds: f.chemontIds,
    npClasses: [...f.npClassL1, ...f.npClassL2, ...f.npClassL3],
    biomeLineage: f.biomeLineage,
    accession: f.accession,
    assemblyIds: f.assemblyIds,
    organism: f.search,
    domainText: f.domainText,
    minLengthKb: f.minLengthKb,
    maxLengthKb: f.maxLengthKb,
  };
}

export const useDiscoveryStore = create<DiscoveryState>((set) => ({
  referenceIbgcId: null,
  setReferenceIbgcId: (id) => set({ referenceIbgcId: id }),

  compareIbgcId: null,
  setCompareIbgcId: (id) => set({ compareIbgcId: id }),

  selectedCds: null,
  setSelectedCds: (cds) => set({ selectedCds: cds }),

  activeResultsTab: "roster",
  setActiveResultsTab: (tab) => set({ activeResultsTab: tab }),

  variablesAxisX: "novelty_score",
  variablesAxisY: "domain_novelty",
  setVariablesAxes: (x, y) => set({ variablesAxisX: x, variablesAxisY: y }),

  rosterSortBy: "novelty_score",
  rosterOrder: "desc",
  setRosterSort: (rosterSortBy, rosterOrder) =>
    set({ rosterSortBy, rosterOrder }),

  resultIbgcIds: null,
  resultSimilarityById: null,
  resultBestHitProteinById: null,
  resultPidentById: null,
  resultQcoverageById: null,
  searchSource: null,
  resultTotalMatched: null,
  resultCapped: false,
  setQueryResult: (
    ids,
    similarity = null,
    source = null,
    bestHitProtein = null,
    pident = null,
    qcoverage = null,
    totalMatched = null,
    capped = false,
  ) =>
    set({
      resultIbgcIds: ids,
      resultSimilarityById: similarity,
      resultBestHitProteinById: bestHitProtein,
      resultPidentById: pident,
      resultQcoverageById: qcoverage,
      searchSource: source,
      resultTotalMatched: totalMatched,
      resultCapped: capped,
      // A fresh query resets compare/protein selections.
      compareIbgcId: null,
      selectedCds: null,
    }),

  resultCriteria: null,
  resultScoresByCriterion: null,
  setCombinedResult: (criteria, scoresByCriterion) =>
    set({
      resultCriteria: criteria,
      resultScoresByCriterion: scoresByCriterion,
    }),

  appliedFilters: EMPTY_APPLIED_FILTERS,
  setAppliedFilters: (filters) => set({ appliedFilters: filters }),

  assetToken: null,
  assetSummary: null,
  setAsset: (token, summary = null) =>
    set({ assetToken: token, assetSummary: summary }),

  clearSelections: () =>
    set({
      referenceIbgcId: null,
      compareIbgcId: null,
      selectedCds: null,
      resultIbgcIds: null,
      resultSimilarityById: null,
      resultBestHitProteinById: null,
      resultPidentById: null,
      resultQcoverageById: null,
      resultCriteria: null,
      resultScoresByCriterion: null,
      searchSource: null,
      resultTotalMatched: null,
      resultCapped: false,
      appliedFilters: EMPTY_APPLIED_FILTERS,
      // Note: ``assetToken`` is intentionally preserved across Run Query
      // resets — the asset chip stays pinned until the user evicts it.
    }),
}));
