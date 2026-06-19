import { apiGet, apiPost } from "./client";
import type {
  CombinedQueryAccepted,
  CombinedQueryRequest,
  CombinedRosterResponse,
  CombinedScoresResponse,
  PaginatedAssemblyAggregationResponse,
} from "./types";

// Composite-Dice "find similar iBGCs" lives in `src/api/ibgcs.ts` →
// `postSimilarIbgcQuery`. All other scoring searches (domain, architecture,
// sequence, chemical) are now driven through the combined query below.

// ── Combined multi-criterion query ──────────────────────────────────────────
// One async query carrying several scoring criteria. Returns 202 + a task_id;
// poll the status endpoint (paginated roster with per-criterion score columns)
// or the scores endpoint (full capped payload + ibgc_ids_token for the maps).

/** Dispatch a combined multi-criterion query → 202 + task_id. */
export function postCombinedQuery(body: CombinedQueryRequest) {
  return apiPost<CombinedQueryAccepted>("/query/combined/", body);
}

export interface CombinedStatusParams {
  page?: number;
  page_size?: number;
  /** ``score:<criterionId>[:<metricKey>]`` or an iBGC column (``novelty_score``,
   *  ``size_kb``, ``bgc_class``, …). Empty = primary criterion. */
  sort_by?: string;
  order?: "asc" | "desc";
}

/** Poll a combined query → paginated roster with per-criterion score columns. */
export function fetchCombinedQueryStatus(
  taskId: string,
  params: CombinedStatusParams = {},
) {
  return apiGet<CombinedRosterResponse>(
    `/query/combined/status/${taskId}/`,
    params as Record<string, string | number | boolean | undefined>,
  );
}

/** Poll a combined query → full capped scores payload (+ ibgc_ids_token). */
export function fetchCombinedQueryScores(taskId: string) {
  return apiGet<CombinedScoresResponse>(
    `/query/combined/status/${taskId}/scores/`,
  );
}

export interface AssemblyAggregationParams {
  bgc_ids: string;
  page?: number;
  page_size?: number;
  sort_by?: string;
  order?: "asc" | "desc";
}

export function fetchQueryResultAssemblies(params: AssemblyAggregationParams) {
  return apiGet<PaginatedAssemblyAggregationResponse>(
    "/query-results/assemblies/",
    params as unknown as Record<string, string | number | boolean | undefined>
  );
}
