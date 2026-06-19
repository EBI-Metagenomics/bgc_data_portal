import { apiGet, apiGetWithHeaders, apiPost } from "./client";
import type {
  IbgcCountResponse,
  IbgcDetail,
  IbgcIdSetResponse,
  IbgcIdsResponse,
  IbgcRegionData,
  IbgcScatterAxis,
  IbgcScatterPoint,
  IbgcUmapPoint,
  PaginatedIbgcRosterResponse,
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
  /** Token for a server-cached allow-list (alternative to ``ibgc_ids`` for
   *  large result sets — see {@link mintIbgcIdset}). */
  ibgc_ids_token?: string;
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
export function fetchIbgcCount(
  params: IbgcFilterParams & { ibgc_ids?: string; ibgc_ids_token?: string } = {},
) {
  return apiGet<IbgcCountResponse>(
    "/ibgcs/count/",
    params as Record<string, string | number | boolean | undefined>,
  );
}

/** Stash a Run Query result allow-list server-side and get back a short token.
 *  The dashboard references that token via ``ibgc_ids_token`` on the roster /
 *  map / count GETs so a multi-thousand-id allow-list never has to ride in the
 *  URL (which would overflow the HTTP request line → 414). Order is preserved
 *  so ``sort_by=similarity`` keeps the caller's best-first rank. */
export function mintIbgcIdset(ibgcIds: number[]) {
  return apiPost<IbgcIdSetResponse>("/ibgcs/idset/", { ibgc_ids: ibgcIds });
}

export interface IbgcIdsParams extends IbgcFilterParams {
  sort_by?: IbgcRosterParams["sort_by"];
  order?: "asc" | "desc";
  ibgc_ids?: string;
  ibgc_ids_token?: string;
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

/** Coerce a roster sort key to a valid map-sampling sort column. The roster's
 *  client-only metrics (``pident`` / ``qcov``) and combined-query per-criterion
 *  keys (``score:*``) aren't map sort columns; the allow-list is fully plotted
 *  so order is moot — fold them to ``similarity``. */
export function toMapSortBy(sortBy: string): IbgcMapSortBy {
  switch (sortBy) {
    case "novelty_score":
    case "domain_novelty":
    case "size_kb":
    case "id":
    case "similarity":
      return sortBy;
    default:
      return "similarity";
  }
}

export interface IbgcUmapParams extends IbgcFilterParams {
  max_points?: number;
  /** Pass the roster's active sort so the map samples the same top iBGCs. */
  sort_by?: IbgcMapSortBy;
  order?: "asc" | "desc";
  /** Comma-separated iBGC ids — restricts the UMAP to this allow-list. */
  ibgc_ids?: string;
  /** Token for a server-cached allow-list (alternative to ``ibgc_ids``). */
  ibgc_ids_token?: string;
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
  /** Token for a server-cached allow-list (alternative to ``ibgc_ids``). */
  ibgc_ids_token?: string;
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

