import { create } from "zustand";

interface SelectionState {
  selectedGenomeIds: number[];
  activeGenomeId: number | null;
  selectedBgcId: number | null;
  activeBgcId: number | null;

  setSelectedGenomeIds: (ids: number[]) => void;
  toggleGenomeId: (id: number) => void;
  setActiveGenomeId: (id: number | null) => void;
  setSelectedBgcId: (id: number | null) => void;
  setActiveBgcId: (id: number | null) => void;
  clearSelections: () => void;
}

export const useSelectionStore = create<SelectionState>((set) => ({
  selectedGenomeIds: [],
  activeGenomeId: null,
  selectedBgcId: null,
  activeBgcId: null,

  setSelectedGenomeIds: (ids) => set({ selectedGenomeIds: ids }),
  toggleGenomeId: (id) =>
    set((state) => {
      const ids = state.selectedGenomeIds.includes(id)
        ? state.selectedGenomeIds.filter((x) => x !== id)
        : [...state.selectedGenomeIds, id];
      return { selectedGenomeIds: ids };
    }),
  setActiveGenomeId: (id) => set({ activeGenomeId: id }),
  setSelectedBgcId: (id) => set({ selectedBgcId: id }),
  setActiveBgcId: (id) => set({ activeBgcId: id }),
  clearSelections: () =>
    set({
      selectedGenomeIds: [],
      activeGenomeId: null,
      selectedBgcId: null,
      activeBgcId: null,
    }),
}));
