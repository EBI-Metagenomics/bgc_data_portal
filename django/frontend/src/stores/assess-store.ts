import { create } from "zustand";
import type {
  BgcAssessmentResult,
  GenomeAssessmentResult,
} from "@/api/types";

export type AssessAssetType = "genome" | "bgc";

interface AssessState {
  assetType: AssessAssetType | null;
  assetId: number | null;
  assetLabel: string;
  taskId: string | null;
  status: "idle" | "pending" | "success" | "error";
  result: GenomeAssessmentResult | BgcAssessmentResult | null;

  startAssessment: (type: AssessAssetType, id: number, label: string) => void;
  setTaskId: (taskId: string) => void;
  setResult: (result: GenomeAssessmentResult | BgcAssessmentResult) => void;
  setStatus: (status: "idle" | "pending" | "success" | "error") => void;
  clearAssessment: () => void;
}

export const useAssessStore = create<AssessState>((set) => ({
  assetType: null,
  assetId: null,
  assetLabel: "",
  taskId: null,
  status: "idle",
  result: null,

  startAssessment: (type, id, label) =>
    set({
      assetType: type,
      assetId: id,
      assetLabel: label,
      taskId: null,
      status: "idle",
      result: null,
    }),

  setTaskId: (taskId) => set({ taskId, status: "pending" }),
  setResult: (result) => set({ result, status: "success" }),
  setStatus: (status) => set({ status }),

  clearAssessment: () =>
    set({
      assetType: null,
      assetId: null,
      assetLabel: "",
      taskId: null,
      status: "idle",
      result: null,
    }),
}));
