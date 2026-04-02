import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import { useShortlistStore } from "@/stores/shortlist-store";
import { useModeStore } from "@/stores/mode-store";
import { useAssessStore } from "@/stores/assess-store";
import { Plus, Replace, Microscope } from "lucide-react";
import { toast } from "sonner";
import type { ReactNode } from "react";

interface AssemblyContextMenuProps {
  children: ReactNode;
  assemblyId: number;
  label: string;
}

export function AssemblyContextMenu({
  children,
  assemblyId,
  label,
}: AssemblyContextMenuProps) {
  const addAssembly = useShortlistStore((s) => s.addAssembly);
  const replaceAssemblies = useShortlistStore((s) => s.replaceAssemblies);
  const setMode = useModeStore((s) => s.setMode);
  const startAssessment = useAssessStore((s) => s.startAssessment);

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>{children}</ContextMenuTrigger>
      <ContextMenuContent>
        <ContextMenuItem
          onClick={() => {
            const ok = addAssembly({ id: assemblyId, label });
            if (!ok) toast.error("Shortlist full (max 20)");
          }}
        >
          <Plus className="mr-2 h-4 w-4" />
          Add to shortlist
        </ContextMenuItem>
        <ContextMenuItem
          onClick={() => replaceAssemblies({ id: assemblyId, label })}
        >
          <Replace className="mr-2 h-4 w-4" />
          Clear shortlist and add
        </ContextMenuItem>
        <ContextMenuItem
          onClick={() => {
            startAssessment("assembly", assemblyId, label);
            setMode("assess");
          }}
        >
          <Microscope className="mr-2 h-4 w-4" />
          Evaluate Assembly
        </ContextMenuItem>
      </ContextMenuContent>
    </ContextMenu>
  );
}
