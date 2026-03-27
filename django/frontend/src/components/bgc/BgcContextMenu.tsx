import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import { useShortlistStore } from "@/stores/shortlist-store";
import { useModeStore } from "@/stores/mode-store";
import { useQueryStore } from "@/stores/query-store";
import { useSelectionStore } from "@/stores/selection-store";
import { Plus, Replace, Search } from "lucide-react";
import { toast } from "sonner";
import type { ReactNode } from "react";

interface BgcContextMenuProps {
  children: ReactNode;
  bgcId: number;
  label: string;
}

export function BgcContextMenu({ children, bgcId, label }: BgcContextMenuProps) {
  const addBgc = useShortlistStore((s) => s.addBgc);
  const replaceBgcs = useShortlistStore((s) => s.replaceBgcs);
  const setMode = useModeStore((s) => s.setMode);
  const setSimilarBgcSourceId = useQueryStore((s) => s.setSimilarBgcSourceId);
  const setActiveBgcId = useSelectionStore((s) => s.setActiveBgcId);

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>{children}</ContextMenuTrigger>
      <ContextMenuContent>
        <ContextMenuItem
          onClick={() => {
            const ok = addBgc({ id: bgcId, label });
            if (!ok) toast.error("Shortlist full (max 20)");
          }}
        >
          <Plus className="mr-2 h-4 w-4" />
          Add to BGC shortlist
        </ContextMenuItem>
        <ContextMenuItem onClick={() => replaceBgcs({ id: bgcId, label })}>
          <Replace className="mr-2 h-4 w-4" />
          Clear shortlist and add
        </ContextMenuItem>
        <ContextMenuItem
          onClick={() => {
            setSimilarBgcSourceId(bgcId);
            setActiveBgcId(bgcId);
            setMode("query");
          }}
        >
          <Search className="mr-2 h-4 w-4" />
          Find similar BGCs
        </ContextMenuItem>
      </ContextMenuContent>
    </ContextMenu>
  );
}
