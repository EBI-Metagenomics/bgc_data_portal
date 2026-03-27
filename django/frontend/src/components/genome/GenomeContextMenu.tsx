import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import { useShortlistStore } from "@/stores/shortlist-store";
import { Plus, Replace } from "lucide-react";
import { toast } from "sonner";
import type { ReactNode } from "react";

interface GenomeContextMenuProps {
  children: ReactNode;
  genomeId: number;
  label: string;
}

export function GenomeContextMenu({
  children,
  genomeId,
  label,
}: GenomeContextMenuProps) {
  const addGenome = useShortlistStore((s) => s.addGenome);
  const replaceGenomes = useShortlistStore((s) => s.replaceGenomes);

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>{children}</ContextMenuTrigger>
      <ContextMenuContent>
        <ContextMenuItem
          onClick={() => {
            const ok = addGenome({ id: genomeId, label });
            if (!ok) toast.error("Shortlist full (max 20)");
          }}
        >
          <Plus className="mr-2 h-4 w-4" />
          Add to shortlist
        </ContextMenuItem>
        <ContextMenuItem
          onClick={() => replaceGenomes({ id: genomeId, label })}
        >
          <Replace className="mr-2 h-4 w-4" />
          Clear shortlist and add
        </ContextMenuItem>
      </ContextMenuContent>
    </ContextMenu>
  );
}
