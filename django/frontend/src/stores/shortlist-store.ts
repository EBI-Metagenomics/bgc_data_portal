import { create } from "zustand";
import { persist } from "zustand/middleware";

const MAX_SHORTLIST = 20;

interface ShortlistItem {
  id: number;
  label: string;
}

interface ShortlistState {
  genomes: ShortlistItem[];
  bgcs: ShortlistItem[];

  addGenome: (item: ShortlistItem) => boolean;
  removeGenome: (id: number) => void;
  clearGenomes: () => void;
  replaceGenomes: (item: ShortlistItem) => void;

  addBgc: (item: ShortlistItem) => boolean;
  removeBgc: (id: number) => void;
  clearBgcs: () => void;
  replaceBgcs: (item: ShortlistItem) => void;
}

export const useShortlistStore = create<ShortlistState>()(
  persist(
    (set, get) => ({
      genomes: [],
      bgcs: [],

      addGenome: (item) => {
        const current = get().genomes;
        if (current.length >= MAX_SHORTLIST) return false;
        if (current.some((g) => g.id === item.id)) return true;
        set({ genomes: [...current, item] });
        return true;
      },
      removeGenome: (id) =>
        set((s) => ({ genomes: s.genomes.filter((g) => g.id !== id) })),
      clearGenomes: () => set({ genomes: [] }),
      replaceGenomes: (item) => set({ genomes: [item] }),

      addBgc: (item) => {
        const current = get().bgcs;
        if (current.length >= MAX_SHORTLIST) return false;
        if (current.some((b) => b.id === item.id)) return true;
        set({ bgcs: [...current, item] });
        return true;
      },
      removeBgc: (id) =>
        set((s) => ({ bgcs: s.bgcs.filter((b) => b.id !== id) })),
      clearBgcs: () => set({ bgcs: [] }),
      replaceBgcs: (item) => set({ bgcs: [item] }),
    }),
    { name: "discovery-shortlists" }
  )
);
