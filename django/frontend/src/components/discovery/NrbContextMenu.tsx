import { Fragment } from "react";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import { useNrbActions } from "@/hooks/use-nrb-actions";

interface Props {
  nrbId: number;
  nrbLabel: string;
  children: React.ReactNode;
}

/**
 * Shared right-click menu for the Results card across all three tabs
 * (roster row, variables-map point, UMAP point). The action set is owned by
 * the ``useNrbActions`` hook; this component is just the right-click shell.
 */
export function NrbContextMenu({ nrbId, nrbLabel, children }: Props) {
  const items = useNrbActions(nrbId, nrbLabel);

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>{children}</ContextMenuTrigger>
      <ContextMenuContent>
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <Fragment key={item.key}>
              {item.separatorBefore && <ContextMenuSeparator />}
              <ContextMenuItem
                onClick={item.onClick}
                disabled={item.disabled}
              >
                <Icon className="mr-2 h-4 w-4" />
                {item.label}
              </ContextMenuItem>
            </Fragment>
          );
        })}
      </ContextMenuContent>
    </ContextMenu>
  );
}
