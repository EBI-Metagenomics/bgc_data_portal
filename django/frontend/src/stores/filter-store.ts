import { create } from "zustand";

interface FilterState {
  typeStrainOnly: boolean;
  taxonomyPath: string;
  assemblyType: string;
  bgcClass: string;
  npClassL1: string[];
  npClassL2: string[];
  npClassL3: string[];
  search: string;
  biomeLineage: string;
  bgcAccession: string;
  assemblyAccession: string;
  assemblyIds: string;

  setTypeStrainOnly: (v: boolean) => void;
  setTaxonomyPath: (value: string) => void;
  setAssemblyType: (v: string) => void;
  setBgcClass: (v: string) => void;
  setNpClass: (level: "l1" | "l2" | "l3", values: string[]) => void;
  setSearch: (v: string) => void;
  setBiomeLineage: (v: string) => void;
  setBgcAccession: (v: string) => void;
  setAssemblyAccession: (v: string) => void;
  setAssemblyIds: (v: string) => void;
  clearFilters: () => void;
}

const initialState = {
  typeStrainOnly: false,
  taxonomyPath: "",
  assemblyType: "",
  bgcClass: "",
  npClassL1: [] as string[],
  npClassL2: [] as string[],
  npClassL3: [] as string[],
  search: "",
  biomeLineage: "",
  bgcAccession: "",
  assemblyAccession: "",
  assemblyIds: "",
};

export const useFilterStore = create<FilterState>((set) => ({
  ...initialState,

  setTypeStrainOnly: (v) => set({ typeStrainOnly: v }),

  setTaxonomyPath: (value) => set({ taxonomyPath: value }),

  setAssemblyType: (v) => set({ assemblyType: v }),

  setBgcClass: (v) => set({ bgcClass: v }),
  setNpClass: (level, values) =>
    set(
      level === "l1"
        ? { npClassL1: values }
        : level === "l2"
          ? { npClassL2: values }
          : { npClassL3: values }
    ),
  setSearch: (v) => set({ search: v }),
  setBiomeLineage: (v) => set({ biomeLineage: v }),
  setBgcAccession: (v) => set({ bgcAccession: v }),
  setAssemblyAccession: (v) => set({ assemblyAccession: v }),
  setAssemblyIds: (v) => set({ assemblyIds: v }),
  clearFilters: () => set(initialState),
}));
