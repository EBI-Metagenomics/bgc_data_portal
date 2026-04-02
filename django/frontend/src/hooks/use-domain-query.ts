import { useQuery } from "@tanstack/react-query";
import { postDomainQuery } from "@/api/queries";
import { useQueryStore } from "@/stores/query-store";
import { useQueryWeightStore } from "@/stores/query-weight-store";
import { useFilterStore } from "@/stores/filter-store";
import { useState, useEffect } from "react";

export function useDomainQuery() {
  const [page, setPage] = useState(1);
  const [enabled, setEnabled] = useState(false);
  const conditions = useQueryStore((s) => s.domainConditions);
  const logic = useQueryStore((s) => s.logic);
  const setResultBgcIds = useQueryStore((s) => s.setResultBgcIds);
  const weights = useQueryWeightStore();
  const filters = useFilterStore();

  const hasConditions = conditions.length > 0;

  const query = useQuery({
    queryKey: ["domain-query", conditions, logic, weights, filters, page],
    queryFn: () =>
      postDomainQuery(
        { domains: conditions, logic },
        {
          page,
          page_size: 50,
          w_similarity: weights.w_similarity,
          w_novelty: weights.w_novelty,
          w_completeness: weights.w_completeness,
          w_domain_novelty: weights.w_domain_novelty,
          search: filters.search || undefined,
          type_strain_only: filters.typeStrainOnly || undefined,
          taxonomy_path: filters.taxonomyPath || undefined,
          assembly_type: filters.assemblyType || undefined,
          bgc_class: filters.bgcClass || undefined,
          biome_lineage: filters.biomeLineage || undefined,
          assembly_accession: filters.assemblyAccession || undefined,
          bgc_accession: filters.bgcAccession || undefined,
        }
      ),
    enabled,
  });

  // Store result IDs for assembly aggregation
  useEffect(() => {
    if (query.data) {
      setResultBgcIds(query.data.items.map((r) => r.id));
    }
  }, [query.data, setResultBgcIds]);

  return {
    ...query,
    page,
    setPage,
    runQuery: () => setEnabled(true),
    hasConditions,
  };
}
