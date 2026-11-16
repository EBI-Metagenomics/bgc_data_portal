import { create } from "zustand";

export type DomainLogic = "and" | "or";

interface QueryState {
  /** Free-text domain accessions (InterPro entries or signature accs) for the
   *  Boolean (AND/OR) query — comma/whitespace separated, ``-``/``!`` prefix
   *  excludes. Applied independently of (and intersected with) the
   *  architecture query. */
  domainText: string;
  /** AND-mode containment threshold (0–1): min fraction of the include tokens
   *  that must be present. Default 1.0 (all). */
  domainThreshold: number;
  /** Combinator for the Boolean text query. */
  domainLogic: DomainLogic;
  /** Free-text comma/space-separated domain accessions for the architecture
   *  query. Ordering is meaningful — adjacency pairs are derived from this
   *  sequence. Applied independently of (and intersected with) the Boolean
   *  query. */
  domainArchitectureText: string;
  /** Domain-set share in the composite score (0..1). Adjacency share
   *  is ``1 - architectureWeight``. */
  architectureWeight: number;
  /** Minimum composite similarity (0..1) an iBGC must reach to be returned by
   *  the architecture query. Default 0.25. */
  architectureThreshold: number;
  sequenceQuery: string;
  sequenceMinBitscore: number;
  sequenceMinPident: number;
  sequenceMinQcov: number;

  setDomainText: (v: string) => void;
  setDomainThreshold: (v: number) => void;
  setDomainLogic: (logic: DomainLogic) => void;
  setDomainArchitectureText: (v: string) => void;
  setArchitectureWeight: (v: number) => void;
  setArchitectureThreshold: (v: number) => void;
  setSequenceQuery: (v: string) => void;
  setSequenceMinBitscore: (v: number) => void;
  setSequenceMinPident: (v: number) => void;
  setSequenceMinQcov: (v: number) => void;
  clearQuery: () => void;
}

export const useQueryStore = create<QueryState>((set) => ({
  domainText: "",
  domainThreshold: 1.0,
  domainLogic: "and",
  domainArchitectureText: "",
  architectureWeight: 0.5,
  architectureThreshold: 0.25,
  sequenceQuery: "",
  sequenceMinBitscore: 30,
  sequenceMinPident: 70,
  sequenceMinQcov: 70,

  setDomainText: (v) => set({ domainText: v }),
  setDomainThreshold: (v) => set({ domainThreshold: v }),
  setDomainLogic: (logic) => set({ domainLogic: logic }),
  setDomainArchitectureText: (v) => set({ domainArchitectureText: v }),
  setArchitectureWeight: (v) => set({ architectureWeight: v }),
  setArchitectureThreshold: (v) => set({ architectureThreshold: v }),
  setSequenceQuery: (v) => set({ sequenceQuery: v }),
  setSequenceMinBitscore: (v) => set({ sequenceMinBitscore: v }),
  setSequenceMinPident: (v) => set({ sequenceMinPident: v }),
  setSequenceMinQcov: (v) => set({ sequenceMinQcov: v }),
  clearQuery: () =>
    set({
      domainText: "",
      domainThreshold: 1.0,
      domainLogic: "and",
      domainArchitectureText: "",
      architectureWeight: 0.5,
      architectureThreshold: 0.25,
      sequenceQuery: "",
      sequenceMinBitscore: 30,
      sequenceMinPident: 70,
      sequenceMinQcov: 70,
    }),
}));
