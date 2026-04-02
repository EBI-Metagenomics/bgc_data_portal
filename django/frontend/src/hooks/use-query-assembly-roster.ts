import { useQuery } from "@tanstack/react-query";
import { fetchAssemblyRoster, type AssemblyRosterParams } from "@/api/assemblies";
import { useState } from "react";

export function useQueryAssemblyRoster(assemblyIds: number[]) {
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState("bgc_novelty_score");
  const [order, setOrder] = useState<"asc" | "desc">("desc");

  const params: AssemblyRosterParams = {
    page,
    page_size: 25,
    sort_by: sortBy,
    order,
    assembly_ids: assemblyIds.length > 0 ? assemblyIds.join(",") : undefined,
  };

  const enabled = assemblyIds.length > 0;

  const query = useQuery({
    queryKey: ["query-assembly-roster", params],
    queryFn: () => fetchAssemblyRoster(params),
    enabled,
  });

  return { ...query, page, setPage, sortBy, setSortBy, order, setOrder };
}
