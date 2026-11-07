import { create } from "zustand";
import { persist } from "zustand/middleware";

// Cap matches backend `MAX_SHORTLIST` in services/report.py; sized so a
// single "Add all to shortlist" action can fill the shortlist from a
// filtered roster in one shot.
export const MAX_SHORTLIST = 1000;

interface ShortlistItem {
  id: number;
  label: string;
}

interface ShortlistState {
  // ── BGC / iBGC shortlist (primary unit in v2) ────────────────────────────
  bgcs: ShortlistItem[];

  addBgc: (item: ShortlistItem) => boolean;
  /** Bulk add. Items already on the shortlist are silently kept; items
   *  beyond MAX_SHORTLIST are dropped. Returns counts so the caller can
   *  surface "added X, Y skipped" toasts. */
  addBgcsBulk: (items: ShortlistItem[]) => { added: number; skipped: number };
  removeBgc: (id: number) => void;
  clearBgcs: () => void;
  replaceBgcs: (item: ShortlistItem) => void;
}

export const useShortlistStore = create<ShortlistState>()(
  persist(
    (set, get) => ({
      bgcs: [],

      addBgc: (item) => {
        const current = get().bgcs;
        if (current.length >= MAX_SHORTLIST) return false;
        if (current.some((b) => b.id === item.id)) return true;
        set({ bgcs: [...current, item] });
        return true;
      },
      addBgcsBulk: (items) => {
        const current = get().bgcs;
        const seen = new Set(current.map((b) => b.id));
        const remaining = Math.max(0, MAX_SHORTLIST - current.length);
        const accepted: ShortlistItem[] = [];
        let skipped = 0;
        for (const item of items) {
          if (seen.has(item.id)) continue;
          if (accepted.length >= remaining) {
            skipped += 1;
            continue;
          }
          accepted.push(item);
          seen.add(item.id);
        }
        if (accepted.length > 0) {
          set({ bgcs: [...current, ...accepted] });
        }
        return { added: accepted.length, skipped };
      },
      removeBgc: (id) =>
        set((s) => ({ bgcs: s.bgcs.filter((b) => b.id !== id) })),
      clearBgcs: () => set({ bgcs: [] }),
      replaceBgcs: (item) => set({ bgcs: [item] }),
    }),
    {
      name: "discovery-shortlists",
      // v1: dropped the retired assembly shortlist (``assemblies``) that the
      // old sidebar trays persisted. ``migrate`` strips it from any v0 blob
      // still in localStorage so it is not re-hydrated as unknown state.
      version: 1,
      migrate: (persisted, version) => {
        const state = (persisted ?? {}) as Record<string, unknown>;
        if (version < 1) {
          const { assemblies: _dropped, ...rest } = state;
          return rest as unknown as ShortlistState;
        }
        return state as unknown as ShortlistState;
      },
    }
  )
);
