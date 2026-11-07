import { create } from "zustand";

interface FilterState {
  sourceNames: string[];
  detectorTools: string[];
  taxonomyPath: string;
  assemblyType: string;
  bgcClass: string;
  gcfPath: string;
  /** Selected NPClassifier term ids (pathway / superclass / class); the
   *  backend also matches descendants of each selected term. */
  npcTerms: string[];
  /** Only labels the detector called confidently (curated labels always are). */
  npcConfidentOnly: boolean;
  search: string;
  /** Free-text term searched against the iBGC's domain annotations
   *  (domain name / description / InterPro description). Populated by the
   *  landing-page keyword-search fallback. */
  domainText: string;
  biomeLineage: string;
  /** Single smart accession field — accepts assembly, contig, BGC, iBGC /
   *  region or protein accessions; the backend auto-detects the kind. */
  accession: string;
  assemblyIds: string;
  // iBGC length bounds in kilobases. ``null`` = unbounded on that side.
  minLengthKb: number | null;
  maxLengthKb: number | null;

  setSourceNames: (v: string[]) => void;
  setDetectorTools: (v: string[]) => void;
  setTaxonomyPath: (value: string) => void;
  setAssemblyType: (v: string) => void;
  setBgcClass: (v: string) => void;
  setGcfPath: (v: string) => void;
  setNpcTerms: (v: string[]) => void;
  setNpcConfidentOnly: (v: boolean) => void;
  setSearch: (v: string) => void;
  setDomainText: (v: string) => void;
  setBiomeLineage: (v: string) => void;
  setAccession: (v: string) => void;
  setAssemblyIds: (v: string) => void;
  setLengthRangeKb: (min: number | null, max: number | null) => void;
  clearFilters: () => void;
}

const initialState = {
  sourceNames: [] as string[],
  detectorTools: [] as string[],
  taxonomyPath: "",
  assemblyType: "",
  bgcClass: "",
  gcfPath: "",
  npcTerms: [] as string[],
  npcConfidentOnly: true,
  search: "",
  domainText: "",
  biomeLineage: "",
  accession: "",
  assemblyIds: "",
  minLengthKb: null as number | null,
  maxLengthKb: null as number | null,
};

export const useFilterStore = create<FilterState>((set) => ({
  ...initialState,

  setSourceNames: (v) => set({ sourceNames: v }),

  setDetectorTools: (v) => set({ detectorTools: v }),

  setTaxonomyPath: (value) => set({ taxonomyPath: value }),

  setAssemblyType: (v) => set({ assemblyType: v }),

  setBgcClass: (v) => set({ bgcClass: v }),
  setGcfPath: (v) => set({ gcfPath: v }),
  setNpcTerms: (v) => set({ npcTerms: v }),
  setNpcConfidentOnly: (v) => set({ npcConfidentOnly: v }),
  setSearch: (v) => set({ search: v }),
  setDomainText: (v) => set({ domainText: v }),
  setBiomeLineage: (v) => set({ biomeLineage: v }),
  setAccession: (v) => set({ accession: v }),
  setAssemblyIds: (v) => set({ assemblyIds: v }),
  setLengthRangeKb: (min, max) =>
    set({ minLengthKb: min, maxLengthKb: max }),
  clearFilters: () => set(initialState),
}));
