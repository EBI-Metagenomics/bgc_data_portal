import { apiGet } from "./client";
import type {
  BgcClassOption,
  NpClassLevel,
  PaginatedDomainResponse,
  TaxonomyNode,
} from "./types";

export function fetchTaxonomyTree() {
  return apiGet<TaxonomyNode[]>("/filters/taxonomy/");
}

export function fetchBgcClasses() {
  return apiGet<BgcClassOption[]>("/filters/bgc-classes/");
}

export function fetchNpClasses() {
  return apiGet<NpClassLevel[]>("/filters/np-classes/");
}

export interface DomainSearchParams {
  search?: string;
  page?: number;
  page_size?: number;
}

export function fetchDomains(params: DomainSearchParams = {}) {
  return apiGet<PaginatedDomainResponse>(
    "/filters/domains/",
    params as Record<string, string | number | boolean | undefined>
  );
}
