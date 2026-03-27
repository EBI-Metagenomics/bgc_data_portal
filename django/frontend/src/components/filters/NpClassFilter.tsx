import { useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useNpClasses } from "@/hooks/use-filter-data";
import { useFilterStore } from "@/stores/filter-store";
import type { NpClassLevel } from "@/api/types";

function NpNode({
  node,
  depth,
  level,
  selected,
  onToggle,
}: {
  node: NpClassLevel;
  depth: number;
  level: "l1" | "l2" | "l3";
  selected: string[];
  onToggle: (level: "l1" | "l2" | "l3", name: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const hasChildren = node.children.length > 0;
  const isChecked = selected.includes(node.name);
  const childLevel = level === "l1" ? "l2" : "l3";

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
          id={`np-${level}-${node.name}`}
          checked={isChecked}
          onCheckedChange={() => onToggle(level, node.name)}
          className="h-3.5 w-3.5"
        />
        <label
          htmlFor={`np-${level}-${node.name}`}
          className="flex-1 cursor-pointer truncate text-xs"
        >
          {node.name}
        </label>
        <Badge variant="secondary" className="text-[10px] px-1">
          {node.count}
        </Badge>
      </div>
      {expanded &&
        node.children.map((child) => (
          <NpNode
            key={child.name}
            node={child}
            depth={depth + 1}
            level={childLevel as "l2" | "l3"}
            selected={selected}
            onToggle={onToggle}
          />
        ))}
    </div>
  );
}

export function NpClassFilter() {
  const { data: npClasses, isLoading } = useNpClasses();
  const npClassL1 = useFilterStore((s) => s.npClassL1);
  const npClassL2 = useFilterStore((s) => s.npClassL2);
  const npClassL3 = useFilterStore((s) => s.npClassL3);
  const setNpClass = useFilterStore((s) => s.setNpClass);

  function handleToggle(level: "l1" | "l2" | "l3", name: string) {
    const current =
      level === "l1" ? npClassL1 : level === "l2" ? npClassL2 : npClassL3;
    const next = current.includes(name)
      ? current.filter((n) => n !== name)
      : [...current, name];
    setNpClass(level, next);
  }

  if (isLoading) {
    return <Skeleton className="h-20 w-full" />;
  }

  const allSelected = [...npClassL1, ...npClassL2, ...npClassL3];

  return (
    <div className="space-y-2">
      <span className="text-sm font-medium">NP Chemical Class</span>
      <div className="max-h-48 overflow-auto">
        {(npClasses ?? []).map((node) => (
          <NpNode
            key={node.name}
            node={node}
            depth={0}
            level="l1"
            selected={allSelected}
            onToggle={handleToggle}
          />
        ))}
      </div>
    </div>
  );
}
