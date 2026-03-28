import { useShortlistStore } from "@/stores/shortlist-store";
import { useModeStore } from "@/stores/mode-store";
import { exportGenomeShortlist } from "@/api/exports";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { X, Download, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export function GenomeShortlistTray() {
  const genomes = useShortlistStore((s) => s.genomes);
  const removeGenome = useShortlistStore((s) => s.removeGenome);
  const clearGenomes = useShortlistStore((s) => s.clearGenomes);
  const mode = useModeStore((s) => s.mode);

  const handleExport = async () => {
    if (genomes.length === 0) {
      toast.error("No genomes in shortlist");
      return;
    }
    try {
      await exportGenomeShortlist(genomes.map((g) => g.id));
      toast.success("CSV downloaded");
    } catch {
      toast.error("Export failed");
    }
  };

  return (
    <div
      className={cn(
        "vf-card vf-card--bordered p-3",
        mode === "explore" ? "border-explore/30 bg-explore/5" : ""
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h4 className="text-xs font-semibold">Genome Shortlist</h4>
          <Badge variant="secondary" className="text-[10px]">
            {genomes.length}/20
          </Badge>
          {mode === "explore" && (
            <Badge variant="outline" className="text-[10px] text-explore">
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
            disabled={genomes.length === 0}
          >
            <Download className="h-3 w-3" />
            CSV
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs"
            onClick={clearGenomes}
            disabled={genomes.length === 0}
          >
            <Trash2 className="h-3 w-3" />
          </Button>
        </div>
      </div>
      {genomes.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {genomes.map((g) => (
            <Badge key={g.id} variant="secondary" className="gap-1 text-xs">
              {g.label}
              <button onClick={() => removeGenome(g.id)}>
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
