import { apiGet, apiPost } from "./client";
import type {
  DomainQueryRequest,
  PaginatedAssemblyAggregationResponse,
  PaginatedQueryResultResponse,
} from "./types";

export interface DomainQueryParams {
  page?: number;
  page_size?: number;
  sort_by?: string;
  order?: "asc" | "desc";
  search?: string;
  source_names?: string;
  detector_tools?: string;
  taxonomy_path?: string;
  assembly_type?: string;
  bgc_class?: string;
  biome_lineage?: string;
  assembly_accession?: string;
  bgc_accession?: string;
}

export function postDomainQuery(
  body: DomainQueryRequest,
  params: DomainQueryParams = {}
) {
  const queryString = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) queryString.set(key, String(value));
  }
  const qs = queryString.toString();
  return apiPost<PaginatedQueryResultResponse>(
    `/query/domain/${qs ? `?${qs}` : ""}`,
    body
  );
}

// Composite-Dice "find similar iBGCs" replaces the retired embedding-based
// similar-BGC endpoint. See `src/api/ibgcs.ts` → `postSimilarIbgcQuery`.

export interface ChemicalQueryRequest {
  smiles: string;
  similarity_threshold: number;
}

export interface ChemicalQueryAccepted {
  task_id: string;
}

/**
 * Dispatch a ChemOnt chemical-similarity search. The query SMILES is
 * classified into ChemOnt terms via ClassyFire (cached by InChIKey) and
 * scored against each iBGC's annotations. Returns ``202`` + a ``task_id``;
 * poll ``fetchIbgcChemicalQueryStatus`` for the iBGC roster.
 */
export function postChemicalQuery(body: ChemicalQueryRequest) {
  return apiPost<ChemicalQueryAccepted>("/query/chemical/", body);
}

export interface SequenceQueryRequest {
  sequence: string;
  min_bitscore: number;
  min_pident: number;
  min_qcov: number;
}

export interface SequenceQueryAccepted {
  task_id: string;
}

export function postSequenceQuery(body: SequenceQueryRequest) {
  return apiPost<SequenceQueryAccepted>("/query/sequence/", body);
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
