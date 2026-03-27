import { create } from "zustand";
import { QUERY_WEIGHT_DEFAULTS, type QueryWeightParams } from "@/api/types";

interface QueryWeightState extends QueryWeightParams {
  setWeight: (key: keyof QueryWeightParams, value: number) => void;
  resetDefaults: () => void;
}

export const useQueryWeightStore = create<QueryWeightState>((set) => ({
  ...QUERY_WEIGHT_DEFAULTS,
  setWeight: (key, value) => set({ [key]: value }),
  resetDefaults: () => set(QUERY_WEIGHT_DEFAULTS),
}));
