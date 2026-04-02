import { create } from "zustand";

interface SelectionState {
  selectedAssemblyIds: number[];
  activeAssemblyId: number | null;
  selectedBgcId: number | null;
  activeBgcId: number | null;

  setSelectedAssemblyIds: (ids: number[]) => void;
  toggleAssemblyId: (id: number) => void;
  setActiveAssemblyId: (id: number | null) => void;
  setSelectedBgcId: (id: number | null) => void;
  setActiveBgcId: (id: number | null) => void;
  clearSelections: () => void;
}

export const useSelectionStore = create<SelectionState>((set) => ({
  selectedAssemblyIds: [],
  activeAssemblyId: null,
  selectedBgcId: null,
  activeBgcId: null,

  setSelectedAssemblyIds: (ids) => set({ selectedAssemblyIds: ids }),
  toggleAssemblyId: (id) =>
    set((state) => {
      const ids = state.selectedAssemblyIds.includes(id)
        ? state.selectedAssemblyIds.filter((x) => x !== id)
        : [...state.selectedAssemblyIds, id];
      return { selectedAssemblyIds: ids };
    }),
  setActiveAssemblyId: (id) => set({ activeAssemblyId: id }),
  setSelectedBgcId: (id) => set({ selectedBgcId: id }),
  setActiveBgcId: (id) => set({ activeBgcId: id }),
  clearSelections: () =>
    set({
      selectedAssemblyIds: [],
      activeAssemblyId: null,
      selectedBgcId: null,
      activeBgcId: null,
    }),
}));
