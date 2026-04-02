import { create } from "zustand";
import { ASSEMBLY_WEIGHT_DEFAULTS, type AssemblyWeightParams } from "@/api/types";

interface AssemblyWeightState extends AssemblyWeightParams {
  setWeight: (key: keyof AssemblyWeightParams, value: number) => void;
  resetDefaults: () => void;
}

export const useAssemblyWeightStore = create<AssemblyWeightState>((set) => ({
  ...ASSEMBLY_WEIGHT_DEFAULTS,
  setWeight: (key, value) => set({ [key]: value }),
  resetDefaults: () => set(ASSEMBLY_WEIGHT_DEFAULTS),
}));
