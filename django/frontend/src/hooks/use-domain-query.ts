import { useQuery } from "@tanstack/react-query";
import { postDomainQuery } from "@/api/queries";
import { useQueryStore } from "@/stores/query-store";
import { useQueryWeightStore } from "@/stores/query-weight-store";
import { useState, useEffect } from "react";

export function useDomainQuery() {
  const [page, setPage] = useState(1);
  const [enabled, setEnabled] = useState(false);
  const conditions = useQueryStore((s) => s.domainConditions);
  const logic = useQueryStore((s) => s.logic);
  const setResultBgcIds = useQueryStore((s) => s.setResultBgcIds);
  const weights = useQueryWeightStore();

  const hasConditions = conditions.length > 0;

  const query = useQuery({
    queryKey: ["domain-query", conditions, logic, weights, page],
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
        }
      ),
    enabled: enabled && hasConditions,
  });

  // Store result IDs for genome aggregation
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
