import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  FileArchive,
  FileCode2,
  FileJson,
  FileSpreadsheet,
  Loader2,
} from "lucide-react";
import { downloadReportHtml } from "@/lib/report-html-export";
import type { ReportPayload } from "@/api/types";

interface Props {
  /** The full cached report payload (token + all panels). */
  payload: ReportPayload;
  /** Optional human label, e.g. number of iBGCs. */
  label?: string;
}

const basePath =
  (typeof document !== "undefined" &&
    document.querySelector('meta[name="base-path"]')?.getAttribute("content")) ||
  "";
const REPORT_API = `${basePath}/api/discovery/report`;

/**
 * Export buttons for the Shortlist Report. JSON / GBK / iBGC-TSV stream from
 * token-scoped Django endpoints; HTML is assembled client-side into a single
 * self-contained, offline-interactive file.
 */
export function ReportDownloadButtons({ payload }: Props) {
  const token = payload.token;
  const [htmlBusy, setHtmlBusy] = useState(false);

  const onHtml = async () => {
    setHtmlBusy(true);
    try {
      await downloadReportHtml(payload);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("HTML export failed", err);
      alert("Could not generate the HTML report. Please try again.");
    } finally {
      setHtmlBusy(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2" data-print-hide>
      <Button variant="outline" size="sm" asChild>
        <a href={`${REPORT_API}/${token}/export.json`} download>
          <FileJson className="mr-1 h-4 w-4" />
          JSON
        </a>
      </Button>
      <Button variant="outline" size="sm" asChild>
        <a href={`${REPORT_API}/${token}/export.ibgcs.tsv`} download>
          <FileSpreadsheet className="mr-1 h-4 w-4" />
          iBGCs (TSV)
        </a>
      </Button>
      <Button variant="outline" size="sm" asChild>
        <a href={`${REPORT_API}/${token}/export.gbk.zip`} download>
          <FileArchive className="mr-1 h-4 w-4" />
          GBKs (zip)
        </a>
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={onHtml}
        disabled={htmlBusy}
      >
        {htmlBusy ? (
          <Loader2 className="mr-1 h-4 w-4 animate-spin" />
        ) : (
          <FileCode2 className="mr-1 h-4 w-4" />
        )}
        HTML
      </Button>
    </div>
  );
}
