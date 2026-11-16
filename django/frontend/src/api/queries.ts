import { apiGet, apiPost } from "./client";
import type {
  CombinedQueryAccepted,
  CombinedQueryRequest,
  CombinedScoresResponse,
} from "./types";

// Composite-similarity "find similar iBGCs" lives in `src/api/ibgcs.ts` →
// `postSimilarIbgcQuery`. All other scoring searches (domain, architecture,
// sequence) are now driven through the combined query below.

// ── Combined multi-criterion query ──────────────────────────────────────────
// One async query carrying several scoring criteria. Returns 202 + a task_id;
// the frontend polls the scores endpoint (full capped payload + ibgc_ids_token
// for the maps). The backend also exposes a paginated roster at
// ``/query/combined/status/{task_id}/`` which the frontend does not use.

/** Dispatch a combined multi-criterion query → 202 + task_id. */
export function postCombinedQuery(body: CombinedQueryRequest) {
  return apiPost<CombinedQueryAccepted>("/query/combined/", body);
}

/** Poll a combined query → full capped scores payload (+ ibgc_ids_token). */
export function fetchCombinedQueryScores(taskId: string) {
  return apiGet<CombinedScoresResponse>(
    `/query/combined/status/${taskId}/scores/`,
  );
}
