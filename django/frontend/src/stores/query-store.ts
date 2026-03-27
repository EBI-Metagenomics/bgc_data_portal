import { create } from "zustand";
import type { DomainCondition } from "@/api/types";

interface QueryState {
  domainConditions: DomainCondition[];
  logic: "and" | "or";
  similarBgcSourceId: number | null;
  resultBgcIds: number[];

  addDomainCondition: (condition: DomainCondition) => void;
  removeDomainCondition: (acc: string) => void;
  toggleDomainRequired: (acc: string) => void;
  setLogic: (logic: "and" | "or") => void;
  setSimilarBgcSourceId: (id: number | null) => void;
  setResultBgcIds: (ids: number[]) => void;
  clearQuery: () => void;
}

export const useQueryStore = create<QueryState>((set) => ({
  domainConditions: [],
  logic: "and",
  similarBgcSourceId: null,
  resultBgcIds: [],

  addDomainCondition: (condition) =>
    set((s) => {
      if (s.domainConditions.some((d) => d.acc === condition.acc)) return s;
      return { domainConditions: [...s.domainConditions, condition] };
    }),
  removeDomainCondition: (acc) =>
    set((s) => ({
      domainConditions: s.domainConditions.filter((d) => d.acc !== acc),
    })),
  toggleDomainRequired: (acc) =>
    set((s) => ({
      domainConditions: s.domainConditions.map((d) =>
        d.acc === acc ? { ...d, required: !d.required } : d
      ),
    })),
  setLogic: (logic) => set({ logic }),
  setSimilarBgcSourceId: (id) => set({ similarBgcSourceId: id }),
  setResultBgcIds: (ids) => set({ resultBgcIds: ids }),
  clearQuery: () =>
    set({
      domainConditions: [],
      logic: "and",
      similarBgcSourceId: null,
      resultBgcIds: [],
    }),
}));
