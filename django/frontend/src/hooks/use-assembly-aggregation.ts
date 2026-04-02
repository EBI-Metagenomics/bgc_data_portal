import { useQuery } from "@tanstack/react-query";
import { fetchQueryResultAssemblies } from "@/api/queries";
import { useQueryStore } from "@/stores/query-store";
import { useState } from "react";

export function useAssemblyAggregation() {
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState("max_relevance");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const resultBgcIds = useQueryStore((s) => s.resultBgcIds);

  const hasResults = resultBgcIds.length > 0;

  const query = useQuery({
    queryKey: ["assembly-aggregation", resultBgcIds, page, sortBy, order],
    queryFn: () =>
      fetchQueryResultAssemblies({
        bgc_ids: resultBgcIds.join(","),
        page,
        page_size: 25,
        sort_by: sortBy,
        order,
      }),
    enabled: hasResults,
  });

  return { ...query, page, setPage, sortBy, setSortBy, order, setOrder, hasResults };
}
