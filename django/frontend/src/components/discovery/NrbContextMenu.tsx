import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import { useDiscoveryStore } from "@/stores/discovery-store";
import { useShortlistStore } from "@/stores/shortlist-store";
import { toast } from "sonner";
import { Pin, Search, Plus, RefreshCw } from "lucide-react";

interface Props {
  nrbId: number;
  nrbLabel: string;
  children: React.ReactNode;
}

/**
 * Shared right-click menu for the Results card across all three tabs
 * (roster row, variables-map point, UMAP point).
 *
 * Items (locked by design round 2):
 *   - Set as reference NRB   → pins to the top-right detail card
 *   - Find similar NRBs       → seeds a composite-Dice similarity query
 *   - Add to BGC shortlist    → appends to the shortlist (up to 100)
 *   - Clear & add             → replaces the shortlist with just this NRB
 */
export function NrbContextMenu({ nrbId, nrbLabel, children }: Props) {
  const setReferenceNrbId = useDiscoveryStore((s) => s.setReferenceNrbId);
  const addBgc = useShortlistStore((s) => s.addBgc);
  const replaceBgcs = useShortlistStore((s) => s.replaceBgcs);

  const onSetRef = () => {
    setReferenceNrbId(nrbId);
    toast.success(`Pinned ${nrbLabel} as reference`);
  };

  const onFindSimilar = () => {
    // The similar-NRB seed lives in the discovery store via ref pinning so
    // the right-side detail card and any future "results overlay" can read
    // the same source. The actual query is fired by useSimilarNrbQuery.
    setReferenceNrbId(nrbId);
    toast.info(`Finding NRBs similar to ${nrbLabel}…`);
  };

  const onAddToShortlist = () => {
    const ok = addBgc({ id: nrbId, label: nrbLabel });
    if (ok) toast.success(`Added ${nrbLabel} to shortlist`);
    else toast.warning("Shortlist is at the 100 cap");
  };

  const onClearAndAdd = () => {
    replaceBgcs({ id: nrbId, label: nrbLabel });
    toast.success(`Shortlist replaced with ${nrbLabel}`);
  };

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>{children}</ContextMenuTrigger>
      <ContextMenuContent>
        <ContextMenuItem onClick={onSetRef}>
          <Pin className="mr-2 h-4 w-4" />
          Set as reference NRB
        </ContextMenuItem>
        <ContextMenuItem onClick={onFindSimilar}>
          <Search className="mr-2 h-4 w-4" />
          Find similar NRBs
        </ContextMenuItem>
        <ContextMenuSeparator />
        <ContextMenuItem onClick={onAddToShortlist}>
          <Plus className="mr-2 h-4 w-4" />
          Add to shortlist
        </ContextMenuItem>
        <ContextMenuItem onClick={onClearAndAdd}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Clear shortlist & add
        </ContextMenuItem>
      </ContextMenuContent>
    </ContextMenu>
  );
}
