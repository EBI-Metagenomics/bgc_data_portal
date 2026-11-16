import { create } from "zustand";

/**
 * The filter-chip values. This object is the single source of truth for the
 * filter surface: ``FilterValues`` / ``FILTER_VALUE_KEYS`` are derived from it
 * and drive the applied-filter snapshot (``discovery-store``) and the URL sync
 * (``use-url-sync``), so adding a chip here is enough for both.
 */
export const INITIAL_FILTER_VALUES = {
  sourceNames: [] as string[],
  detectorTools: [] as string[],
  taxonomyPath: "",
  assemblyType: "",
  bgcClass: "",
  gcfPath: "",
  /** Selected NPClassifier term ids (pathway / superclass / class); the
   *  backend also matches descendants of each selected term. */
  npcTerms: [] as string[],
  /** Only labels the detector called confidently (curated labels always are). */
  npcConfidentOnly: true,
  /** Organism free-text search (API param ``organism``). */
  search: "",
  /** Free-text term searched against the iBGC's domain annotations
   *  (domain name / description / InterPro description). Populated by the
   *  landing-page keyword-search fallback. */
  domainText: "",
  biomeLineage: "",
  /** Single smart accession field — accepts assembly, contig, BGC, iBGC /
   *  region or protein accessions; the backend auto-detects the kind. */
  accession: "",
  assemblyIds: "",
  // iBGC length bounds in kilobases. ``null`` = unbounded on that side.
  minLengthKb: null as number | null,
  maxLengthKb: null as number | null,
};

export type FilterValues = typeof INITIAL_FILTER_VALUES;

export const FILTER_VALUE_KEYS = Object.keys(
  INITIAL_FILTER_VALUES,
) as (keyof FilterValues)[];

export interface FilterActions {
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

export type FilterState = FilterValues & FilterActions;

export const useFilterStore = create<FilterState>((set) => ({
  ...INITIAL_FILTER_VALUES,

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
  clearFilters: () => set(INITIAL_FILTER_VALUES),
}));
