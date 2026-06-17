import { apiGet, apiGetWithHeaders, apiPost } from "./client";
import type {
  IbgcCountResponse,
  IbgcDetail,
  IbgcIdsResponse,
  IbgcRegionData,
  IbgcScatterAxis,
  IbgcScatterPoint,
  IbgcUmapPoint,
  PaginatedIbgcRosterResponse,
  QueryScoresResponse,
} from "./types";

export interface IbgcFilterParams {
  include_partials?: boolean;
  validated_only?: boolean;
  min_length_kb?: number;
  max_length_kb?: number;
  min_novelty?: number;
  max_novelty?: number;
  min_domain_novelty?: number;
  max_domain_novelty?: number;
  detector_tools?: string;
  /** @deprecated use detector_tools — kept for backward compat */
  source_tools?: string;
  source_names?: string;
  assembly_type?: string;
  leaf_path_prefix?: string;
  bgc_class?: string;
  chemont_ids?: string;
  /** CSV of selected NP-class names (any of L1/L2/L3). */
  np_classes?: string;
  /** Single smart accession field — backend auto-detects assembly / contig /
   *  BGC / iBGC / region / protein. */
  accession?: string;
  /** @deprecated split BGC-only accession field, kept for saved deep links */
  bgc_accession?: string;
  /** @deprecated split assembly-only accession field, kept for saved deep links */
  assembly_accession?: string;
  assembly_ids?: string;
  organism?: string;
  biome_lineage?: string;
  taxonomy_path?: string;
}

export interface IbgcRosterParams extends IbgcFilterParams {
  sort_by?:
    | "novelty_score"
    | "domain_novelty"
    | "size_kb"
    | "classification_path"
    | "id"
    | "similarity";
  order?: "asc" | "desc";
  page?: number;
  page_size?: number;
  /** Comma-separated iBGC ids — restricts the roster to this allow-list. */
  ibgc_ids?: string;
}

export function fetchIbgcRoster(params: IbgcRosterParams = {}) {
  return apiGet<PaginatedIbgcRosterResponse>(
    "/ibgcs/roster/",
    params as Record<string, string | number | boolean | undefined>,
  );
}

/** Cheap COUNT over the iBGC filter surface. Fired before the heavier
 *  roster/UMAP/scatter calls to drive the empty-state guard and the
 *  "Showing X of Y, sampled" banner. */
export function fetchIbgcCount(params: IbgcFilterParams & { ibgc_ids?: string } = {}) {
  return apiGet<IbgcCountResponse>(
    "/ibgcs/count/",
    params as Record<string, string | number | boolean | undefined>,
  );
}

export interface IbgcIdsParams extends IbgcFilterParams {
  sort_by?: IbgcRosterParams["sort_by"];
  order?: "asc" | "desc";
  ibgc_ids?: string;
  asset_token?: string;
}

/** Bulk iBGC ids matching the active filter surface — capped at 1000
 *  server-side. Powers the roster's "Add all to shortlist" button so we
 *  don't have to walk roster pages just to gather ids. */
export function fetchIbgcIds(params: IbgcIdsParams = {}) {
  return apiGet<IbgcIdsResponse>(
    "/ibgcs/ids/",
    params as Record<string, string | number | boolean | undefined>,
  );
}

// ── iBGC-collapsed query endpoints ─────────────────────────────────────────

export interface DomainCondition {
  acc: string;
  required: boolean;
}

export interface DomainQueryRequest {
  domains: DomainCondition[];
  logic: "and" | "or";
}

export interface IbgcDomainQueryParams extends IbgcFilterParams {
  sort_by?:
    | "novelty_score"
    | "domain_novelty"
    | "size_kb"
    | "classification_path"
    | "similarity_score"
    | "id";
  order?: "asc" | "desc";
  page?: number;
  page_size?: number;
}

export function postIbgcDomainQuery(
  body: DomainQueryRequest,
  params: IbgcDomainQueryParams = {},
) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  }
  const path = qs.toString()
    ? `/query/ibgc-domain/?${qs.toString()}`
    : "/query/ibgc-domain/";
  return apiPost<PaginatedIbgcRosterResponse>(path, body);
}

export interface IbgcSequenceStatusParams extends IbgcDomainQueryParams {
  // same shape as the domain-query params
}

export function fetchIbgcSequenceQueryStatus(
  taskId: string,
  params: IbgcSequenceStatusParams = {},
) {
  return apiGet<PaginatedIbgcRosterResponse>(
    `/query/ibgc-sequence/status/${taskId}/`,
    params as Record<string, string | number | boolean | undefined>,
  );
}

/** Poll a chemical (ChemOnt/ClassyFire) search task → iBGC roster. */
export function fetchIbgcChemicalQueryStatus(
  taskId: string,
  params: IbgcSequenceStatusParams = {},
) {
  return apiGet<PaginatedIbgcRosterResponse>(
    `/query/chemical/status/${taskId}/`,
    params as Record<string, string | number | boolean | undefined>,
  );
}

// ── Compact, capped query "scores" endpoints ────────────────────────────────
// These return up to `max_results` (server-bounded by DASHBOARD_RESULT_CAP)
// ranked {id, similarity_score, best_pident, best_qcoverage, best_hit_protein}
// rows plus the true `total_matched`. The dashboard builds its result
// allow-list + metric maps from these; the full roster rows are fetched
// separately via /ibgcs/roster/?ibgc_ids=…

/** Poll a sequence-search task → compact, bitscore-ranked scores (≤ max). */
export function fetchIbgcSequenceQueryScores(taskId: string, maxResults?: number) {
  return apiGet<QueryScoresResponse>(
    `/query/ibgc-sequence/status/${taskId}/scores/`,
    maxResults !== undefined ? { max_results: maxResults } : {},
  );
}

/** Poll a chemical-search task → compact, similarity-ranked scores (≤ max). */
export function fetchIbgcChemicalQueryScores(taskId: string, maxResults?: number) {
  return apiGet<QueryScoresResponse>(
    `/query/chemical/status/${taskId}/scores/`,
    maxResults !== undefined ? { max_results: maxResults } : {},
  );
}

/** Domain query → compact scores (≤ max). Domain match is binary (score 1.0). */
export function postIbgcDomainQueryScores(
  body: DomainQueryRequest,
  maxResults?: number,
) {
  const qs = new URLSearchParams();
  if (maxResults !== undefined) qs.set("max_results", String(maxResults));
  const path = qs.toString()
    ? `/query/ibgc-domain/scores/?${qs.toString()}`
    : "/query/ibgc-domain/scores/";
  return apiPost<QueryScoresResponse>(path, body);
}

export function fetchIbgcDetail(ibgcId: number, assetToken?: string | null) {
  // Negative ids belong to ephemeral asset uploads — the backend resolves
  // them through the ``X-Asset-Token`` header so the URL path stays clean.
  if (ibgcId < 0 && assetToken) {
    return apiGetWithHeaders<IbgcDetail>(
      `/ibgcs/${ibgcId}/`,
      { "X-Asset-Token": assetToken },
    );
  }
  return apiGet<IbgcDetail>(`/ibgcs/${ibgcId}/`);
}

/**
 * Merged region payload for an iBGC — the union of every CDS overlapping the
 * iBGC's genomic span, each carrying ``claimed_by_tools`` attribution. This
 * is the single round-trip that backs the region plot (replaces the old
 * per-representative-prediction ``/bgcs/{id}/region/`` call).
 */
export function fetchIbgcRegion(ibgcId: number, assetToken?: string | null) {
  if (ibgcId < 0 && assetToken) {
    return apiGetWithHeaders<IbgcRegionData>(
      `/ibgcs/${ibgcId}/region/`,
      { "X-Asset-Token": assetToken },
    );
  }
  return apiGet<IbgcRegionData>(`/ibgcs/${ibgcId}/region/`);
}

/** Sort keys for the maps' top-``max_points`` sampling — a subset of the
 *  roster's keys, matching the backend ``_apply_ibgc_sort`` helper. */
export type IbgcMapSortBy =
  | "novelty_score"
  | "domain_novelty"
  | "size_kb"
  | "id"
  | "similarity";

export interface IbgcUmapParams extends IbgcFilterParams {
  max_points?: number;
  /** Pass the roster's active sort so the map samples the same top iBGCs. */
  sort_by?: IbgcMapSortBy;
  order?: "asc" | "desc";
  /** Comma-separated iBGC ids — restricts the UMAP to this allow-list. */
  ibgc_ids?: string;
}

export function fetchIbgcUmap(params: IbgcUmapParams = {}) {
  return apiGet<IbgcUmapPoint[]>(
    "/ibgcs/umap/",
    params as Record<string, string | number | boolean | undefined>,
  );
}

export interface IbgcScatterParams extends IbgcFilterParams {
  x_axis?: IbgcScatterAxis;
  y_axis?: IbgcScatterAxis;
  max_points?: number;
  /** Sampling sort (which points), independent of the x/y plot axes. Pass the
   *  roster's active sort so the map shows the same top iBGCs. */
  sort_by?: IbgcMapSortBy;
  order?: "asc" | "desc";
  /** Comma-separated iBGC ids — restricts the scatter to this allow-list. */
  ibgc_ids?: string;
}

export function fetchIbgcScatter(params: IbgcScatterParams = {}) {
  return apiGet<IbgcScatterPoint[]>(
    "/ibgcs/scatter/",
    params as Record<string, string | number | boolean | undefined>,
  );
}

export interface SimilarIbgcRequest {
  ibgc_id: number;
  k?: number;
}

export function postSimilarIbgcQuery(
  body: SimilarIbgcRequest,
  page = 1,
  pageSize = 25,
) {
  const qs = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  return apiPost<PaginatedIbgcRosterResponse>(
    `/query/similar-ibgc/?${qs.toString()}`,
    body,
  );
}

export interface IbgcArchitectureResponse {
  id: number;
  label: string;
  ordered_accs: string[];
}

/** Pooled positional domain accessions for clipboard / copy actions. */
export function fetchIbgcArchitecture(
  ibgcId: number,
  assetToken?: string | null,
) {
  if (ibgcId < 0 && assetToken) {
    return apiGetWithHeaders<IbgcArchitectureResponse>(
      `/ibgcs/${ibgcId}/architecture/`,
      { "X-Asset-Token": assetToken },
    );
  }
  return apiGet<IbgcArchitectureResponse>(`/ibgcs/${ibgcId}/architecture/`);
}

export interface IbgcArchitectureQueryRequest {
  architecture: string[];
  weight: number;
  k?: number;
}

export function postIbgcArchitectureQuery(
  body: IbgcArchitectureQueryRequest,
  page = 1,
  pageSize = 25,
) {
  const qs = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  return apiPost<PaginatedIbgcRosterResponse>(
    `/query/ibgc-architecture/?${qs.toString()}`,
    body,
  );
}

/** Architecture query → compact, composite-Dice-ranked scores (≤ max). */
export function postIbgcArchitectureQueryScores(
  body: IbgcArchitectureQueryRequest,
  maxResults?: number,
) {
  const qs = new URLSearchParams();
  if (maxResults !== undefined) qs.set("max_results", String(maxResults));
  const path = qs.toString()
    ? `/query/ibgc-architecture/scores/?${qs.toString()}`
    : "/query/ibgc-architecture/scores/";
  return apiPost<QueryScoresResponse>(path, body);
}
