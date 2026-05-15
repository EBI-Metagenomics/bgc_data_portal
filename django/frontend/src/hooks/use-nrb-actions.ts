import { useDiscoveryStore } from "@/stores/discovery-store";
import { useShortlistStore } from "@/stores/shortlist-store";
import { toast } from "sonner";
import { Pin, Search, Plus, RefreshCw } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NrbActionItem {
  key: "set-ref" | "find-similar" | "add-shortlist" | "clear-add-shortlist";
  label: string;
  icon: LucideIcon;
  onClick: () => void;
  /** When true the item should render before this entry. */
  separatorBefore?: boolean;
  /** Item is rendered greyed-out and is non-interactive. */
  disabled?: boolean;
  /** Tooltip / hint shown alongside a disabled item (right-aligned). */
  disabledHint?: string;
}

interface UseNrbActionsOptions {
  /** When set to "reference", "Set as reference NRB" is shown disabled
   *  because this NRB is already pinned in the reference slot. */
  variant?: "reference" | "compare";
}

export function useNrbActions(
  nrbId: number,
  nrbLabel: string,
  options: UseNrbActionsOptions = {},
): NrbActionItem[] {
  const setReferenceNrbId = useDiscoveryStore((s) => s.setReferenceNrbId);
  const addBgc = useShortlistStore((s) => s.addBgc);
  const replaceBgcs = useShortlistStore((s) => s.replaceBgcs);

  const isReference = options.variant === "reference";

  const onSetRef = () => {
    setReferenceNrbId(nrbId);
    toast.success(`Pinned ${nrbLabel} as reference`);
  };

  const onFindSimilar = () => {
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

  return [
    {
      key: "set-ref",
      label: "Set as reference NRB",
      icon: Pin,
      onClick: onSetRef,
      disabled: isReference,
      disabledHint: isReference ? "Already pinned" : undefined,
    },
    {
      key: "find-similar",
      label: "Find similar NRBs",
      icon: Search,
      onClick: onFindSimilar,
    },
    {
      key: "add-shortlist",
      label: "Add to shortlist",
      icon: Plus,
      onClick: onAddToShortlist,
      separatorBefore: true,
    },
    {
      key: "clear-add-shortlist",
      label: "Clear shortlist & add",
      icon: RefreshCw,
      onClick: onClearAndAdd,
    },
  ];
}
