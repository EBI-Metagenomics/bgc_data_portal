import { create } from "zustand";
import type { AssetSummary } from "@/api/assets";
import type {
  CriterionColumn,
  CriterionScore,
  IbgcScatterAxis,
  RegionCds,
} from "@/api/types";
import { pick } from "@/lib/utils";
import {
  FILTER_VALUE_KEYS,
  INITIAL_FILTER_VALUES,
  useFilterStore,
  type FilterActions,
  type FilterState,
} from "@/stores/filter-store";

/**
 * Session state for the v2 Discovery dashboard.
 *
 * Persistence is intentionally OFF (per design decision): the reference iBGC
 * + compare slot reset on reload. URL state lives in route params, not here.
 */

export type ResultsTab = "roster" | "variables";

/** Sort keys shared by the roster and the Variables map. The map caps
 *  at 5k points server-side and sample the roster's top rows in this order, so
 *  "what's in the roster is what's in the plots". Mirrors the backend
 *  ``_apply_ibgc_sort`` accepted keys. */
export type RosterSortKey =
  | "novelty_score"
  | "domain_novelty"
  | "size_kb"
  | "id"
  // Server-side "keep the allow-list order" sort (array_position). The roster
  // ranks the result allow-list client-side by the active criterion metric and
  // sends this so the server preserves that order.
  | "similarity"
  // Per-criterion sort keys: ``score:<criterionId>`` (primary value) or
  // ``score:<criterionId>:<metricKey>`` (e.g. a sequence pident). Resolved
  // client-side against ``resultScoresByCriterion``.
  | `score:${string}`;

/** Which advanced-query path produced the current ``resultIbgcIds`` set.
 *  Drives the "Clear …" button label. ``null`` = no advanced query (filter-only
 *  run or fresh load). */
export type SearchSource =
  | "sequence"
  | "domain"
  | "domain_architecture"
  | "similar_ibgc"
  | null;

/** Criterion id → (iBGC id → score payload). */
export type ScoresByCriterion = Record<string, Record<number, CriterionScore>>;

/**
 * A scored query result. Every producer (combined query, find-similar) emits
 * this one shape: an ordered iBGC allow-list plus one score column per
 * criterion. The roster columns and the Variables-map axes are derived from
 * ``criteria`` + ``scoresByCriterion`` alone.
 */
export interface QueryResult {
  /** Best-first ordered allow-list (capped server-side). */
  ids: number[];
  /** Ordered criterion-column descriptors; ``criteria[0]`` is the primary. */
  criteria: CriterionColumn[];
  scoresByCriterion: ScoresByCriterion;
  source: Exclude<SearchSource, null>;
  /** Full match count before the cap (``null`` when unknown) and whether the
   *  allow-list was capped. Drives the "showing top N of M" banner. */
  totalMatched: number | null;
  capped: boolean;
}

/** The criterion whose primary value is surfaced as the single "similarity"
 *  (map hover text): sequence > architecture > domain > similar, else the
 *  first column. */
export function dominantCriterion(
  criteria: CriterionColumn[] | null,
): CriterionColumn | null {
  if (!criteria || criteria.length === 0) return null;
  for (const type of ["sequence", "architecture", "domain", "similar"]) {
    const col = criteria.find((c) => c.type === type);
    if (col) return col;
  }
  return criteria[0] ?? null;
}

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
  // Variables map can sample its top-5k by the SAME order the roster
  // displays (the server caps and sorts both identically).
  rosterSortBy: RosterSortKey;
  rosterOrder: "asc" | "desc";
  setRosterSort: (sortBy: RosterSortKey, order: "asc" | "desc") => void;

  // Scored query result (see ``QueryResult``), spread into individual fields
  // so consumers subscribe to just what they render. All null/empty when no
  // scored query is active (filter-only run or fresh load): the roster + maps
  // then show everything matching ``appliedFilters``.
  resultIbgcIds: number[] | null;
  resultCriteria: CriterionColumn[] | null;
  resultScoresByCriterion: ScoresByCriterion | null;
  searchSource: SearchSource;
  resultTotalMatched: number | null;
  resultCapped: boolean;
  /** Replace the scored result (``null`` clears it). A fresh result also
   *  resets the compare / protein selections. */
  setQueryResult: (result: QueryResult | null) => void;

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

/** The filter-chip values as applied by Run Query — the filter store minus its
 *  actions, so every chip is represented automatically. */
export type AppliedIbgcFilters = Omit<FilterState, keyof FilterActions>;

export const EMPTY_APPLIED_FILTERS: AppliedIbgcFilters = INITIAL_FILTER_VALUES;

/** True when no filter chip is set in the applied snapshot.
 *  Combined with ``resultIbgcIds == null`` it gates the dashboard's
 *  empty-state CTA so we never fire an unbounded fetch on landing. */
export function isAppliedFiltersEmpty(applied: AppliedIbgcFilters): boolean {
  return FILTER_VALUE_KEYS.every((key) => {
    // The confident-only toggle only qualifies ``npcTerms``; on its own it
    // does not narrow anything (see ``appliedFiltersToApiParams``).
    if (key === "npcConfidentOnly") return true;
    const value = applied[key];
    return Array.isArray(value)
      ? value.length === 0
      : value === EMPTY_APPLIED_FILTERS[key];
  });
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
 * Used by ``IbgcRosterTable``, the Variables-Map scatter hook and the count
 * hook so all three stay in lockstep with the same filter contract.
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
  if (applied.npcTerms.length > 0) {
    params.npc_terms = applied.npcTerms.join(",");
    if (!applied.npcConfidentOnly) params.npc_confident = "false";
  }
  if (applied.biomeLineage) params.biome_lineage = applied.biomeLineage;
  if (applied.accession) params.accession = applied.accession;
  if (applied.assemblyIds) params.assembly_ids = applied.assemblyIds;
  if (applied.search) params.organism = applied.search;
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
 * Run Query button (``use-run-ibgc-query``), Find Similar and the landing-page
 * keyword redirect (``use-url-sync`` auto-run) stay in lockstep. Picks every
 * value key of the filter store, so a new chip is carried automatically.
 */
export function snapshotFiltersToApplied(): AppliedIbgcFilters {
  return pick(useFilterStore.getState(), FILTER_VALUE_KEYS);
}

const NO_RESULT = {
  resultIbgcIds: null,
  resultCriteria: null,
  resultScoresByCriterion: null,
  searchSource: null,
  resultTotalMatched: null,
  resultCapped: false,
} as const;

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

  ...NO_RESULT,
  setQueryResult: (result) =>
    set({
      ...(result
        ? {
            resultIbgcIds: result.ids,
            resultCriteria: result.criteria,
            resultScoresByCriterion: result.scoresByCriterion,
            searchSource: result.source,
            resultTotalMatched: result.totalMatched,
            resultCapped: result.capped,
          }
        : NO_RESULT),
      // A fresh query resets compare/protein selections.
      compareIbgcId: null,
      selectedCds: null,
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
      ...NO_RESULT,
      appliedFilters: EMPTY_APPLIED_FILTERS,
      // Note: ``assetToken`` is intentionally preserved across Run Query
      // resets — the asset chip stays pinned until the user evicts it.
    }),
}));
