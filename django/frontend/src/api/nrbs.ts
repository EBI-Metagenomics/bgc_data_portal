import { apiGet, apiPost } from "./client";
import type {
  NrbDetail,
  NrbScatterAxis,
  NrbScatterPoint,
  NrbUmapPoint,
  PaginatedNrbRosterResponse,
} from "./types";

export interface NrbRosterParams {
  sort_by?:
    | "novelty_score"
    | "domain_novelty"
    | "size_kb"
    | "classification_path"
    | "id";
  order?: "asc" | "desc";
  page?: number;
  page_size?: number;
  include_partials?: boolean;
}

export function fetchNrbRoster(params: NrbRosterParams = {}) {
  return apiGet<PaginatedNrbRosterResponse>(
    "/nrbs/roster/",
    params as Record<string, string | number | boolean | undefined>,
  );
}

export function fetchNrbDetail(nrbId: number) {
  return apiGet<NrbDetail>(`/nrbs/${nrbId}/`);
}

export interface NrbUmapParams {
  include_partials?: boolean;
  max_points?: number;
}

export function fetchNrbUmap(params: NrbUmapParams = {}) {
  return apiGet<NrbUmapPoint[]>(
    "/nrbs/umap/",
    params as Record<string, string | number | boolean | undefined>,
  );
}

export interface NrbScatterParams {
  x_axis?: NrbScatterAxis;
  y_axis?: NrbScatterAxis;
  include_partials?: boolean;
  max_points?: number;
}

export function fetchNrbScatter(params: NrbScatterParams = {}) {
  return apiGet<NrbScatterPoint[]>(
    "/nrbs/scatter/",
    params as Record<string, string | number | boolean | undefined>,
  );
}

export interface SimilarNrbRequest {
  nrb_id: number;
  k?: number;
}

export function postSimilarNrbQuery(
  body: SimilarNrbRequest,
  page = 1,
  pageSize = 25,
) {
  const qs = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  return apiPost<PaginatedNrbRosterResponse>(
    `/query/similar-nrb/?${qs.toString()}`,
    body,
  );
}
