import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useDiscoveryStore } from "@/stores/discovery-store";
import { ChevronDown, ChevronUp, Dna } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Collapsible bottom-right panel that mirrors the CDS selected in either
 * detail card. Currently a stub container; the existing `CdsProteinInfo`
 * component will be moved here in a follow-up so the panel does the
 * full Pfam annotation rendering across CDS clicks.
 */
export function ProteinInfoPanel() {
  const [expanded, setExpanded] = useState(false);
  const selectedCdsId = useDiscoveryStore((s) => s.selectedCdsId);

  return (
    <Card className="flex h-full flex-col overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((s) => !s)}
        className="flex w-full items-center justify-between border-b px-3 py-2 text-sm hover:bg-muted/40"
      >
        <span className="inline-flex items-center gap-2 font-semibold">
          <Dna className="h-4 w-4" />
          Protein Information
          {selectedCdsId !== null && (
            <span className="font-mono text-xs text-muted-foreground">
              · CDS #{selectedCdsId}
            </span>
          )}
        </span>
        {expanded ? (
          <ChevronUp className="h-4 w-4" />
        ) : (
          <ChevronDown className="h-4 w-4" />
        )}
      </button>
      <div
        className={cn(
          "min-h-0 flex-1 overflow-auto p-3 text-sm text-muted-foreground",
          !expanded && "hidden",
        )}
      >
        {selectedCdsId === null ? (
          <span>
            Click a CDS in either detail card to load its Pfam annotations
            here.
          </span>
        ) : (
          <span>
            Pfam annotation rendering wires up next; selected CDS is{" "}
            <span className="font-mono">{selectedCdsId}</span>.
          </span>
        )}
      </div>
    </Card>
  );
}
