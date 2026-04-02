import { create } from "zustand";
import { persist } from "zustand/middleware";

const MAX_SHORTLIST = 20;

interface ShortlistItem {
  id: number;
  label: string;
}

interface ShortlistState {
  assemblies: ShortlistItem[];
  bgcs: ShortlistItem[];

  addAssembly: (item: ShortlistItem) => boolean;
  removeAssembly: (id: number) => void;
  clearAssemblies: () => void;
  replaceAssemblies: (item: ShortlistItem) => void;

  addBgc: (item: ShortlistItem) => boolean;
  removeBgc: (id: number) => void;
  clearBgcs: () => void;
  replaceBgcs: (item: ShortlistItem) => void;
}

export const useShortlistStore = create<ShortlistState>()(
  persist(
    (set, get) => ({
      assemblies: [],
      bgcs: [],

      addAssembly: (item) => {
        const current = get().assemblies;
        if (current.length >= MAX_SHORTLIST) return false;
        if (current.some((g) => g.id === item.id)) return true;
        set({ assemblies: [...current, item] });
        return true;
      },
      removeAssembly: (id) =>
        set((s) => ({ assemblies: s.assemblies.filter((g) => g.id !== id) })),
      clearAssemblies: () => set({ assemblies: [] }),
      replaceAssemblies: (item) => set({ assemblies: [item] }),

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
