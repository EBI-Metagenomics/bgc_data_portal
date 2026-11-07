import { apiGet } from "./client";
import type {
  BgcClassOption,
  NpcTreeNode,
  PaginatedGcfResponse,
  PaginatedSourceResponse,
  PaginatedDetectorResponse,
  TaxonomyNode,
} from "./types";

export function fetchTaxonomyTree() {
  return apiGet<TaxonomyNode[]>("/filters/taxonomy/");
}

export function fetchBgcClasses() {
  return apiGet<BgcClassOption[]>("/filters/bgc-classes/");
}

export function fetchNpcTree() {
  return apiGet<NpcTreeNode[]>("/filters/npc-tree/");
}

export interface GcfSearchParams {
  search?: string;
  level?: number;
  page?: number;
  page_size?: number;
}

export function fetchGcfs(params: GcfSearchParams = {}) {
  return apiGet<PaginatedGcfResponse, GcfSearchParams>(
    "/filters/gcfs/",
    params,
  );
}

export interface SourceSearchParams {
  search?: string;
  page?: number;
  page_size?: number;
}

export function fetchSources(params: SourceSearchParams = {}) {
  return apiGet<PaginatedSourceResponse, SourceSearchParams>(
    "/filters/sources/",
    params,
  );
}

export interface DetectorSearchParams {
  search?: string;
  page?: number;
  page_size?: number;
}

export function fetchDetectors(params: DetectorSearchParams = {}) {
  return apiGet<PaginatedDetectorResponse, DetectorSearchParams>(
    "/filters/detectors/",
    params,
  );
}
