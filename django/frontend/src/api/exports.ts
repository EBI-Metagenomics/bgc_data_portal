import { apiPostBlob, downloadBlob } from "./client";
import type { ShortlistExportRequest } from "./types";

export async function exportGenomeShortlist(ids: number[]) {
  const body: ShortlistExportRequest = { ids };
  const blob = await apiPostBlob("/shortlist/genome/export/", body);
  downloadBlob(blob, "genome_shortlist.csv");
}

export async function exportBgcShortlist(ids: number[]) {
  const body: ShortlistExportRequest = { ids };
  const blob = await apiPostBlob("/shortlist/bgc/export/", body);
  downloadBlob(blob, "bgc_shortlist.gbk");
}
