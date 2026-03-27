import { useQuery } from "@tanstack/react-query";
import { postSimilarBgcQuery } from "@/api/queries";
import { useQueryStore } from "@/stores/query-store";
import { useQueryWeightStore } from "@/stores/query-weight-store";
import { useState, useEffect } from "react";

export function useSimilarBgcQuery() {
  const [page, setPage] = useState(1);
  const sourceId = useQueryStore((s) => s.similarBgcSourceId);
  const setResultBgcIds = useQueryStore((s) => s.setResultBgcIds);
  const weights = useQueryWeightStore();

  const query = useQuery({
    queryKey: ["similar-bgc-query", sourceId, weights, page],
    queryFn: () =>
      postSimilarBgcQuery(sourceId!, {
        page,
        page_size: 50,
        w_similarity: weights.w_similarity,
        w_novelty: weights.w_novelty,
        w_completeness: weights.w_completeness,
        w_domain_novelty: weights.w_domain_novelty,
      }),
    enabled: sourceId !== null,
  });

  useEffect(() => {
    if (query.data) {
      setResultBgcIds(query.data.items.map((r) => r.id));
    }
  }, [query.data, setResultBgcIds]);

  return { ...query, page, setPage };
}
