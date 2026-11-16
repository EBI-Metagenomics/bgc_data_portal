import { useQuery } from "@tanstack/react-query";
import { fetchTaxonomyTree, fetchBgcClasses, fetchNpcTree } from "@/api/filters";

export function useTaxonomyTree() {
  return useQuery({
    queryKey: ["filters", "taxonomy"],
    queryFn: fetchTaxonomyTree,
    staleTime: 5 * 60 * 1000,
  });
}

export function useBgcClasses() {
  return useQuery({
    queryKey: ["filters", "bgc-classes"],
    queryFn: fetchBgcClasses,
    staleTime: 5 * 60 * 1000,
  });
}

export function useNpcTree() {
  return useQuery({
    queryKey: ["filters", "npc-tree"],
    queryFn: fetchNpcTree,
    staleTime: 5 * 60 * 1000,
  });
}
