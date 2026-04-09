import { useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useChemOntClasses } from "@/hooks/use-filter-data";
import { useFilterStore } from "@/stores/filter-store";
import type { ChemOntClassNode } from "@/api/types";

function ChemOntNode({
  node,
  depth,
  selected,
  onToggle,
}: {
  node: ChemOntClassNode;
  depth: number;
  selected: string[];
  onToggle: (chemontId: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const hasChildren = node.children.length > 0;
  const isChecked = selected.includes(node.chemont_id);

  return (
    <div>
      <div
        className="flex items-center gap-1 py-0.5"
        style={{ paddingLeft: `${depth * 12 + 4}px` }}
      >
        {hasChildren && (
          <button
            className="p-0.5"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
          </button>
        )}
        {!hasChildren && <span className="w-4" />}
        <Checkbox
          id={`chemont-${node.chemont_id}`}
          checked={isChecked}
          onCheckedChange={() => onToggle(node.chemont_id)}
          className="h-3.5 w-3.5"
        />
        <label
          htmlFor={`chemont-${node.chemont_id}`}
          className="flex-1 cursor-pointer truncate text-xs"
          title={node.chemont_id}
        >
          {node.name}
        </label>
        <Badge variant="secondary" className="text-[10px] px-1">
          {node.count}
        </Badge>
      </div>
      {expanded &&
        node.children.map((child) => (
          <ChemOntNode
            key={child.chemont_id}
            node={child}
            depth={depth + 1}
            selected={selected}
            onToggle={onToggle}
          />
        ))}
    </div>
  );
}

export function ChemOntClassFilter() {
  const { data: chemontClasses, isLoading } = useChemOntClasses();
  const chemontIds = useFilterStore((s) => s.chemontIds);
  const setChemontIds = useFilterStore((s) => s.setChemontIds);

  function handleToggle(chemontId: string) {
    const next = chemontIds.includes(chemontId)
      ? chemontIds.filter((id) => id !== chemontId)
      : [...chemontIds, chemontId];
    setChemontIds(next);
  }

  if (isLoading) {
    return <Skeleton className="h-20 w-full" />;
  }

  return (
    <div className="space-y-2">
      <span className="text-sm font-medium">ChemOnt Chemical Class</span>
      <div className="max-h-48 overflow-auto">
        {(chemontClasses ?? []).map((node) => (
          <ChemOntNode
            key={node.chemont_id}
            node={node}
            depth={0}
            selected={chemontIds}
            onToggle={handleToggle}
          />
        ))}
      </div>
    </div>
  );
}
