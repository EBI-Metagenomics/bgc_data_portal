import { apiGet } from "./client";
import type { BgcDetail, BgcScatterPoint } from "./types";

export function fetchBgcDetail(bgcId: number) {
  return apiGet<BgcDetail>(`/bgcs/${bgcId}/`);
}

export interface BgcScatterParams {
  include_mibig?: boolean;
  bgc_class?: string;
  assembly_ids?: string;
  max_points?: number;
}

export function fetchBgcScatter(params: BgcScatterParams = {}) {
  return apiGet<BgcScatterPoint[]>("/bgc-scatter/", params as Record<string, string | number | boolean | undefined>);
}
