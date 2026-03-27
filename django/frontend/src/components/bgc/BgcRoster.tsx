import { useBgcRoster } from "@/hooks/use-bgc-roster";
import { useSelectionStore } from "@/stores/selection-store";
import { useShortlistStore } from "@/stores/shortlist-store";
import { useModeStore } from "@/stores/mode-store";
import { BgcContextMenu } from "./BgcContextMenu";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

export function BgcRoster() {
  const mode = useModeStore((s) => s.mode);
  const activeGenomeId = useSelectionStore((s) => s.activeGenomeId);
  const activeBgcId = useSelectionStore((s) => s.activeBgcId);
  const setActiveBgcId = useSelectionStore((s) => s.setActiveBgcId);
  const genomeShortlist = useShortlistStore((s) => s.genomes);

  // In explore mode, show BGCs from active genome or first shortlisted genome
  const sourceGenomeId =
    mode === "explore"
      ? activeGenomeId ?? genomeShortlist[0]?.id ?? null
      : activeGenomeId;

  const { data: bgcs, isLoading } = useBgcRoster(sourceGenomeId);

  if (!sourceGenomeId) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Select a genome to view its BGCs
      </p>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-8 w-full" />
        ))}
      </div>
    );
  }

  return (
    <div className="overflow-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="text-xs">Accession</TableHead>
            <TableHead className="text-xs">Class</TableHead>
            <TableHead className="text-xs text-right">Size (kb)</TableHead>
            <TableHead className="text-xs text-right">Novelty</TableHead>
            <TableHead className="text-xs text-right">Dom. Nov.</TableHead>
            <TableHead className="text-xs text-center">Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(bgcs ?? []).map((bgc) => (
            <BgcContextMenu
              key={bgc.id}
              bgcId={bgc.id}
              label={bgc.accession}
            >
              <TableRow
                className={cn(
                  "cursor-pointer",
                  activeBgcId === bgc.id && "bg-primary/5"
                )}
                onClick={() => setActiveBgcId(bgc.id)}
              >
                <TableCell className="font-mono text-xs">
                  {bgc.accession}
                </TableCell>
                <TableCell className="text-xs">
                  {bgc.classification_l1}
                  {bgc.classification_l2 && (
                    <span className="text-muted-foreground">
                      {" / "}
                      {bgc.classification_l2}
                    </span>
                  )}
                </TableCell>
                <TableCell className="text-right font-mono text-xs">
                  {bgc.size_kb.toFixed(1)}
                </TableCell>
                <TableCell className="text-right font-mono text-xs">
                  {bgc.novelty_score.toFixed(2)}
                </TableCell>
                <TableCell className="text-right font-mono text-xs">
                  {bgc.domain_novelty.toFixed(2)}
                </TableCell>
                <TableCell className="text-center">
                  {bgc.is_partial ? (
                    <Badge variant="outline" className="text-[10px]">
                      partial
                    </Badge>
                  ) : (
                    <Badge
                      variant="secondary"
                      className="text-[10px] bg-green-100 text-green-700"
                    >
                      complete
                    </Badge>
                  )}
                </TableCell>
              </TableRow>
            </BgcContextMenu>
          ))}
          {(bgcs ?? []).length === 0 && (
            <TableRow>
              <TableCell
                colSpan={6}
                className="py-8 text-center text-sm text-muted-foreground"
              >
                No BGCs found for this genome
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
