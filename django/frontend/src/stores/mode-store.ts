import { create } from "zustand";

export type DashboardMode = "explore" | "query";

interface ModeState {
  mode: DashboardMode;
  setMode: (mode: DashboardMode) => void;
}

export const useModeStore = create<ModeState>((set) => ({
  mode: "explore",
  setMode: (mode) => set({ mode }),
}));
