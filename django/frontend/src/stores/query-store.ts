import { create } from "zustand";
import type { QueryResultBgc } from "@/api/types";

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
  similarBgcSourceId: number | null;
  resultBgcIds: number[];
  resultBgcData: QueryResultBgc[];
  sequenceQuery: string;
  sequenceMinBitscore: number;
  sequenceMinPident: number;
  sequenceMinQcov: number;
  sequenceTaskId: string | null;
  domainQueryTriggered: boolean;
  sequenceQueryTriggered: boolean;

  // Per-query result storage for intersection
  domainResultData: QueryResultBgc[];
  sequenceResultData: QueryResultBgc[];

  setDomainText: (v: string) => void;
  setDomainThreshold: (v: number) => void;
  setDomainLogic: (logic: DomainLogic) => void;
  setDomainArchitectureText: (v: string) => void;
  setArchitectureWeight: (v: number) => void;
  setArchitectureThreshold: (v: number) => void;
  setSimilarBgcSourceId: (id: number | null) => void;
  setResultBgcIds: (ids: number[]) => void;
  setResultBgcData: (data: QueryResultBgc[]) => void;
  setSequenceQuery: (v: string) => void;
  setSequenceMinBitscore: (v: number) => void;
  setSequenceMinPident: (v: number) => void;
  setSequenceMinQcov: (v: number) => void;
  setSequenceTaskId: (id: string | null) => void;
  setDomainQueryTriggered: (v: boolean) => void;
  setSequenceQueryTriggered: (v: boolean) => void;
  setDomainResultData: (data: QueryResultBgc[]) => void;
  setSequenceResultData: (data: QueryResultBgc[]) => void;
  computeIntersection: () => void;
  clearQuery: () => void;
}

function intersectResults(
  datasets: QueryResultBgc[][],
): { ids: number[]; data: QueryResultBgc[] } {
  if (datasets.length === 0) return { ids: [], data: [] };
  if (datasets.length === 1) {
    return { ids: datasets[0]!.map((r) => r.id), data: datasets[0]! };
  }

  // Find IDs present in ALL datasets
  const idSets = datasets.map((d) => new Set(d.map((r) => r.id)));
  const commonIds = [...idSets[0]!].filter((id) =>
    idSets.every((s) => s.has(id))
  );

  // Use the last dataset's entries for similarity_score (sequence > domain priority)
  const lastDataset = datasets[datasets.length - 1]!;
  const lastMap = new Map(lastDataset.map((r) => [r.id, r]));
  const data = commonIds
    .map((id) => lastMap.get(id))
    .filter((r): r is QueryResultBgc => r !== undefined);

  return { ids: commonIds, data };
}

export const useQueryStore = create<QueryState>((set, get) => ({
  domainText: "",
  domainThreshold: 1.0,
  domainLogic: "and",
  domainArchitectureText: "",
  architectureWeight: 0.5,
  architectureThreshold: 0.25,
  similarBgcSourceId: null,
  resultBgcIds: [],
  resultBgcData: [],
  sequenceQuery: "",
  sequenceMinBitscore: 30,
  sequenceMinPident: 70,
  sequenceMinQcov: 70,
  sequenceTaskId: null,
  domainQueryTriggered: false,
  sequenceQueryTriggered: false,
  domainResultData: [],
  sequenceResultData: [],

  setDomainText: (v) => set({ domainText: v }),
  setDomainThreshold: (v) => set({ domainThreshold: v }),
  setDomainLogic: (logic) => set({ domainLogic: logic }),
  setDomainArchitectureText: (v) => set({ domainArchitectureText: v }),
  setArchitectureWeight: (v) => set({ architectureWeight: v }),
  setArchitectureThreshold: (v) => set({ architectureThreshold: v }),
  setSimilarBgcSourceId: (id) => set({ similarBgcSourceId: id }),
  setResultBgcIds: (ids) => set({ resultBgcIds: ids }),
  setResultBgcData: (data) => set({ resultBgcData: data }),
  setSequenceQuery: (v) => set({ sequenceQuery: v }),
  setSequenceMinBitscore: (v) => set({ sequenceMinBitscore: v }),
  setSequenceMinPident: (v) => set({ sequenceMinPident: v }),
  setSequenceMinQcov: (v) => set({ sequenceMinQcov: v }),
  setSequenceTaskId: (id) => set({ sequenceTaskId: id }),
  setDomainQueryTriggered: (v) => set({ domainQueryTriggered: v }),
  setSequenceQueryTriggered: (v) => set({ sequenceQueryTriggered: v }),
  setDomainResultData: (data) => set({ domainResultData: data }),
  setSequenceResultData: (data) => set({ sequenceResultData: data }),
  computeIntersection: () => {
    const s = get();
    const activeDatasets: QueryResultBgc[][] = [];
    // Collect datasets in priority order (domain, sequence)
    // Sequence data comes last so its similarity_score wins in intersection
    if (s.domainResultData.length > 0) activeDatasets.push(s.domainResultData);
    if (s.sequenceResultData.length > 0)
      activeDatasets.push(s.sequenceResultData);

    const { ids, data } = intersectResults(activeDatasets);
    set({ resultBgcIds: ids, resultBgcData: data });
  },
  clearQuery: () =>
    set({
      domainText: "",
      domainThreshold: 1.0,
      domainLogic: "and",
      domainArchitectureText: "",
      architectureWeight: 0.5,
      architectureThreshold: 0.25,
      similarBgcSourceId: null,
      resultBgcIds: [],
      resultBgcData: [],
      sequenceQuery: "",
      sequenceMinBitscore: 30,
      sequenceMinPident: 70,
      sequenceMinQcov: 70,
      sequenceTaskId: null,
      domainQueryTriggered: false,
      sequenceQueryTriggered: false,
      domainResultData: [],
      sequenceResultData: [],
    }),
}));
