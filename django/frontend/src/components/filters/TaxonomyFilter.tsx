import { useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { useTaxonomyTree } from "@/hooks/use-filter-data";
import { useFilterStore } from "@/stores/filter-store";
import { cn } from "@/lib/utils";
import type { TaxonomyNode } from "@/api/types";
import { FilterChip } from "./FilterChip";

/** Ltree path of the parent node ("" at the root). */
function parentPath(path: string): string {
  const i = path.lastIndexOf(".");
  return i < 0 ? "" : path.slice(0, i);
}

function findNode(
  nodes: TaxonomyNode[],
  path: string,
): TaxonomyNode | undefined {
  for (const node of nodes) {
    if (node.path === path) return node;
    if (path.startsWith(`${node.path}.`)) return findNode(node.children, path);
  }
  return undefined;
}

function TaxonomyNodeItem({
  node,
  depth,
  selectedPath,
  onSelect,
}: {
  node: TaxonomyNode;
  depth: number;
  selectedPath: string;
  onSelect: (path: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const isSelected = node.path === selectedPath;
  const hasChildren = node.children.length > 0;

  return (
    <div>
      <div
        className={cn(
          "flex cursor-pointer items-center gap-1 rounded px-2 py-1 text-sm hover:bg-accent",
          isSelected && "bg-primary/10 font-medium",
        )}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        onClick={() => {
          onSelect(isSelected ? parentPath(node.path) : node.path);
        }}
      >
        {hasChildren && (
          <button
            className="p-0.5"
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(!expanded);
            }}
          >
            {expanded ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
          </button>
        )}
        {!hasChildren && <span className="w-4" />}
        <span className="flex-1 truncate" title={node.rank}>
          {node.name}
        </span>
        <Badge variant="secondary" className="text-xs">
          {node.count}
        </Badge>
      </div>
      {expanded &&
        hasChildren &&
        node.children.map((child) => (
          <TaxonomyNodeItem
            key={child.path}
            node={child}
            depth={depth + 1}
            selectedPath={selectedPath}
            onSelect={onSelect}
          />
        ))}
    </div>
  );
}

export function TaxonomyFilter() {
  const { data: tree, isLoading } = useTaxonomyTree();
  const [searchText, setSearchText] = useState("");
  const filterStore = useFilterStore();

  // The filter value is the selected node's ltree path, as served by the
  // tree endpoint — ranks can be absent, so never rebuild it by position.
  const taxonomyPath = filterStore.taxonomyPath;
  const selected = taxonomyPath ? findNode(tree ?? [], taxonomyPath) : undefined;

  function filterTree(nodes: TaxonomyNode[]): TaxonomyNode[] {
    if (!searchText) return nodes;
    const q = searchText.toLowerCase();
    return nodes.reduce<TaxonomyNode[]>((acc, node) => {
      const matchesSelf = node.name.toLowerCase().includes(q);
      const filteredChildren = filterTree(node.children);
      if (matchesSelf || filteredChildren.length > 0) {
        acc.push({
          ...node,
          children: matchesSelf ? node.children : filteredChildren,
        });
      }
      return acc;
    }, []);
  }

  const displayed = filterTree(tree ?? []);
  const label = taxonomyPath
    ? `Taxonomy: ${
        selected
          ? `${selected.rank} ${selected.name}`
          : taxonomyPath.split(".").pop()
      }`
    : "Taxonomy";

  return (
    <FilterChip
      label={label}
      active={!!taxonomyPath}
      onClear={() => filterStore.setTaxonomyPath("")}
      dataTour="taxonomy-filter"
      width="md"
    >
      {isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-6 w-full" />
        </div>
      ) : (
        <div className="space-y-2">
          <Input
            placeholder="Search taxonomy..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="h-8 text-sm"
          />
          <div className="max-h-64 overflow-auto">
            {displayed.map((node) => (
              <TaxonomyNodeItem
                key={node.path}
                node={node}
                depth={0}
                selectedPath={taxonomyPath}
                onSelect={filterStore.setTaxonomyPath}
              />
            ))}
            {displayed.length === 0 && (
              <p className="py-2 text-center text-xs text-muted-foreground">
                No matches
              </p>
            )}
          </div>
        </div>
      )}
    </FilterChip>
  );
}
