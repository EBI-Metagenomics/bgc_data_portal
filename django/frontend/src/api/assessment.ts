import { apiGet, apiPost, downloadBlob } from "./client";
import type {
  AssessmentAccepted,
  AssessmentStatusResponse,
  GenomeWeightParams,
} from "./types";

export async function postGenomeAssessment(
  assemblyId: number,
  weights: GenomeWeightParams
): Promise<AssessmentAccepted> {
  return apiPost<AssessmentAccepted>(
    `/assess/genome/${assemblyId}/`,
    weights
  );
}

export async function postBgcAssessment(
  bgcId: number
): Promise<AssessmentAccepted> {
  return apiPost<AssessmentAccepted>(`/assess/bgc/${bgcId}/`, {});
}

export async function fetchAssessmentStatus(
  taskId: string
): Promise<AssessmentStatusResponse> {
  return apiGet<AssessmentStatusResponse>(`/assess/status/${taskId}/`);
}

export async function fetchSimilarGenomes(
  assemblyId: number
): Promise<number[]> {
  return apiGet<number[]>(`/assess/genome/${assemblyId}/similar-genomes/`);
}

export async function exportAssessmentJson(taskId: string): Promise<void> {
  const response = await fetch(
    `${document.querySelector('meta[name="base-path"]')?.getAttribute("content") ?? ""}/api/dashboard/assess/export/${taskId}/`
  );
  if (!response.ok) throw new Error("Export failed");
  const blob = await response.blob();
  downloadBlob(blob, `assessment_${taskId.slice(0, 8)}.json`);
}
