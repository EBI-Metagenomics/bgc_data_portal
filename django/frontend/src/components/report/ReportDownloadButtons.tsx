import { Button } from "@/components/ui/button";
import { Download, FileArchive, FileJson, FileSpreadsheet, Printer } from "lucide-react";
import { toast } from "sonner";

interface Props {
  /** Stable identifier for the report (used in download filename). */
  token: string;
  /** Optional human label, e.g. number of NRBs. */
  label?: string;
}

const basePath =
  (typeof document !== "undefined" &&
    document.querySelector('meta[name="base-path"]')?.getAttribute("content")) ||
  "";
const REPORT_API = `${basePath}/api/dashboard/report`;

/**
 * Save as HTML + Print (Save as PDF).
 *
 * Save as HTML: clones the `[data-report-root]` subtree, copies stylesheets
 * with their `<style>`/`<link>` tags so the offline page renders close to
 * the live page, wraps it in a minimal document, and triggers a Blob
 * download. Print: triggers `window.print()` and relies on the page's
 * `@media print` stylesheet.
 */
export function ReportDownloadButtons({ token, label }: Props) {
  const onPrint = () => {
    window.print();
  };

  const onDownloadHtml = () => {
    const root = document.querySelector<HTMLElement>("[data-report-root]");
    if (!root) {
      toast.error("Report root not found");
      return;
    }
    const styles = Array.from(
      document.querySelectorAll<HTMLLinkElement | HTMLStyleElement>(
        'link[rel="stylesheet"], style',
      ),
    )
      .map((el) => el.outerHTML)
      .join("\n");
    const title = `BGC Shortlist Report${label ? ` — ${label}` : ""}`;
    const html = `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>${title}</title>
${styles}
<style>
  body { background: white; padding: 24px; }
  [data-print-hide] { display: none !important; }
</style>
</head>
<body>
${root.outerHTML}
</body>
</html>`;
    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `bgc-report-${token.slice(0, 8)}.html`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    toast.success("Report HTML downloaded");
  };

  return (
    <div className="flex flex-wrap items-center gap-2" data-print-hide>
      <Button variant="outline" size="sm" asChild>
        <a href={`${REPORT_API}/${token}/export.json`} download>
          <FileJson className="mr-1 h-4 w-4" />
          JSON (analyst)
        </a>
      </Button>
      <Button variant="outline" size="sm" asChild>
        <a href={`${REPORT_API}/${token}/export.gbk.zip`} download>
          <FileArchive className="mr-1 h-4 w-4" />
          GBKs (zip)
        </a>
      </Button>
      <Button variant="outline" size="sm" asChild>
        <a href={`${REPORT_API}/${token}/export.assemblies.tsv`} download>
          <FileSpreadsheet className="mr-1 h-4 w-4" />
          Assemblies (TSV)
        </a>
      </Button>
      <Button variant="outline" size="sm" onClick={onDownloadHtml}>
        <Download className="mr-1 h-4 w-4" />
        Save as HTML
      </Button>
      <Button variant="outline" size="sm" onClick={onPrint}>
        <Printer className="mr-1 h-4 w-4" />
        Print / PDF
      </Button>
    </div>
  );
}
