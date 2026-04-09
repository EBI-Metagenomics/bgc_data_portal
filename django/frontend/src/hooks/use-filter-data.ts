import { useQuery } from "@tanstack/react-query";
import { fetchTaxonomyTree, fetchBgcClasses, fetchNpClasses, fetchChemOntClasses } from "@/api/filters";

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

export function useNpClasses() {
  return useQuery({
    queryKey: ["filters", "np-classes"],
    queryFn: fetchNpClasses,
    staleTime: 5 * 60 * 1000,
  });
}

export function useChemOntClasses() {
  return useQuery({
    queryKey: ["filters", "chemont-classes"],
    queryFn: fetchChemOntClasses,
    staleTime: 5 * 60 * 1000,
  });
}
