import { useShortlistStore } from "@/stores/shortlist-store";
import { useModeStore } from "@/stores/mode-store";
import { exportBgcShortlist } from "@/api/exports";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { X, Download, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export function BgcShortlistTray() {
  const bgcs = useShortlistStore((s) => s.bgcs);
  const removeBgc = useShortlistStore((s) => s.removeBgc);
  const clearBgcs = useShortlistStore((s) => s.clearBgcs);
  const mode = useModeStore((s) => s.mode);

  const handleExport = async () => {
    if (bgcs.length === 0) {
      toast.error("No BGCs in shortlist");
      return;
    }
    try {
      await exportBgcShortlist(bgcs.map((b) => b.id));
      toast.success("GBK downloaded");
    } catch {
      toast.error("Export failed");
    }
  };

  return (
    <div
      className={cn(
        "rounded-lg border p-3",
        mode === "query" ? "border-query/30 bg-query/5" : "border-border"
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h4 className="text-xs font-semibold">BGC Shortlist</h4>
          <Badge variant="secondary" className="text-[10px]">
            {bgcs.length}/20
          </Badge>
          {mode === "query" && (
            <Badge variant="outline" className="text-[10px] text-query">
              active
            </Badge>
          )}
        </div>
        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-6 gap-1 text-xs"
            onClick={handleExport}
            disabled={bgcs.length === 0}
          >
            <Download className="h-3 w-3" />
            GBK
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs"
            onClick={clearBgcs}
            disabled={bgcs.length === 0}
          >
            <Trash2 className="h-3 w-3" />
          </Button>
        </div>
      </div>
      {bgcs.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {bgcs.map((b) => (
            <Badge key={b.id} variant="secondary" className="gap-1 font-mono text-xs">
              {b.label}
              <button onClick={() => removeBgc(b.id)}>
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
