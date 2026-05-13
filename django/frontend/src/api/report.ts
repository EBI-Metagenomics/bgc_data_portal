import { apiGet, apiPost } from "./client";
import type { ReportPayload, ReportSnapshotResponse } from "./types";

/**
 * Materialise a shortlist Report and obtain its token. The same shortlist
 * always resolves to the same token, so re-opening the report tab is cheap.
 */
export function postReportSnapshot(nrbIds: number[]) {
  return apiPost<ReportSnapshotResponse>("/report/snapshot/", {
    nrb_ids: nrbIds,
  });
}

/**
 * Fetch the cached payload for a Report token. 404 means the cache entry
 * has expired and the client should re-POST the snapshot.
 */
export function fetchReport(token: string) {
  return apiGet<ReportPayload>(`/report/${token}/`);
}
