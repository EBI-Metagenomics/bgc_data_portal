import { useQuery } from "@tanstack/react-query";
import { fetchGenomeBgcs } from "@/api/genomes";

export function useBgcRoster(genomeId: number | null) {
  return useQuery({
    queryKey: ["bgc-roster", genomeId],
    queryFn: () => fetchGenomeBgcs(genomeId!),
    enabled: genomeId !== null,
  });
}
