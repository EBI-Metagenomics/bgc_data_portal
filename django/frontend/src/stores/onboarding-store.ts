import { create } from "zustand";

const STORAGE_KEY = "bgc-discovery-welcome-seen";

interface OnboardingState {
  showWelcome: boolean;
  tourActive: boolean;
  openWelcome: () => void;
  dismissWelcome: () => void;
  startTour: () => void;
  endTour: () => void;
}

export const useOnboardingStore = create<OnboardingState>((set) => ({
  showWelcome: localStorage.getItem(STORAGE_KEY) !== "true",
  tourActive: false,

  openWelcome: () => set({ showWelcome: true }),

  dismissWelcome: () => {
    localStorage.setItem(STORAGE_KEY, "true");
    set({ showWelcome: false });
  },

  startTour: () => {
    localStorage.setItem(STORAGE_KEY, "true");
    set({ showWelcome: false, tourActive: true });
  },

  endTour: () => set({ tourActive: false }),
}));
