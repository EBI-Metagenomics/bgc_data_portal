import { useMemo, useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { useNpcTree } from "@/hooks/use-filter-data";
import { useFilterStore } from "@/stores/filter-store";
import { cn } from "@/lib/utils";
import type { NpcTreeNode } from "@/api/types";
import { FilterChip } from "./FilterChip";

/** Multi-select over the NPClassifier ontology (pathway → superclass → class).
 *
 *  A checked term also matches its descendants on the server, so checking a
 *  pathway covers every superclass and class under it. A superclass with two
 *  parent pathways appears under both; checking either copy selects the same
 *  term id. Counts are iBGCs labelled with exactly that term. */

function NpcNodeItem({
  node,
  depth,
  selected,
  confidentOnly,
  onToggle,
  forceExpand,
}: {
  node: NpcTreeNode;
  depth: number;
  selected: Set<string>;
  confidentOnly: boolean;
  onToggle: (termId: string) => void;
  forceExpand: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const hasChildren = node.children.length > 0;
  const isChecked = selected.has(node.term_id);
  const count = confidentOnly ? node.confident_count : node.count;
  const open = expanded || forceExpand;

  return (
    <div>
      <div
        className={cn(
          "flex items-center gap-1 rounded px-1 py-0.5 text-sm hover:bg-accent",
          isChecked && "bg-primary/10",
        )}
        style={{ paddingLeft: `${depth * 12 + 4}px` }}
      >
        {hasChildren ? (
          <button
            className="p-0.5"
            onClick={() => setExpanded(!open)}
            aria-label={open ? "Collapse" : "Expand"}
          >
            {open ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
          </button>
        ) : (
          <span className="w-4" />
        )}
        <Checkbox
          id={`npc-${depth}-${node.term_id}`}
          checked={isChecked}
          onCheckedChange={() => onToggle(node.term_id)}
        />
        <label
          htmlFor={`npc-${depth}-${node.term_id}`}
          className="flex-1 cursor-pointer truncate"
          title={`${node.level}: ${node.name}`}
        >
          {node.name}
        </label>
        <Badge variant="secondary" className="text-xs">
          {count}
        </Badge>
      </div>
      {open &&
        hasChildren &&
        node.children.map((child) => (
          <NpcNodeItem
            key={`${node.term_id}/${child.term_id}`}
            node={child}
            depth={depth + 1}
            selected={selected}
            confidentOnly={confidentOnly}
            onToggle={onToggle}
            forceExpand={forceExpand}
          />
        ))}
    </div>
  );
}

function filterTree(nodes: NpcTreeNode[], q: string): NpcTreeNode[] {
  if (!q) return nodes;
  return nodes.reduce<NpcTreeNode[]>((acc, node) => {
    const matchesSelf = node.name.toLowerCase().includes(q);
    const children = filterTree(node.children, q);
    if (matchesSelf || children.length > 0) {
      acc.push({ ...node, children: matchesSelf ? node.children : children });
    }
    return acc;
  }, []);
}

function findName(nodes: NpcTreeNode[], termId: string): string | undefined {
  for (const node of nodes) {
    if (node.term_id === termId) return node.name;
    const hit = findName(node.children, termId);
    if (hit) return hit;
  }
  return undefined;
}

export function NpcFilter() {
  const { data: tree, isLoading } = useNpcTree();
  const [searchText, setSearchText] = useState("");
  const npcTerms = useFilterStore((s) => s.npcTerms);
  const confidentOnly = useFilterStore((s) => s.npcConfidentOnly);
  const setNpcTerms = useFilterStore((s) => s.setNpcTerms);
  const setConfidentOnly = useFilterStore((s) => s.setNpcConfidentOnly);

  const selected = useMemo(() => new Set(npcTerms), [npcTerms]);
  const q = searchText.trim().toLowerCase();
  const displayed = useMemo(() => filterTree(tree ?? [], q), [tree, q]);

  const toggle = (termId: string) => {
    setNpcTerms(
      selected.has(termId)
        ? npcTerms.filter((t) => t !== termId)
        : [...npcTerms, termId],
    );
  };

  const first = npcTerms[0];
  const label =
    first === undefined
      ? "Natural product class"
      : npcTerms.length === 1
        ? `NP class: ${findName(tree ?? [], first) ?? first.split(":").pop() ?? first}`
        : `NP class: ${npcTerms.length} terms`;

  return (
    <FilterChip
      label={label}
      active={npcTerms.length > 0}
      onClear={() => setNpcTerms([])}
      dataTour="npc-filter"
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
          <p className="text-[11px] text-muted-foreground">
            NPClassifier pathway → superclass → class of the predicted or
            curated product. A checked term also matches everything below it.
          </p>
          <Input
            placeholder="Search classes..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="h-8 text-sm"
          />
          <label className="flex items-center gap-2 text-xs">
            <Checkbox
              checked={confidentOnly}
              onCheckedChange={(v) => setConfidentOnly(v === true)}
            />
            Confident labels only
          </label>
          <div className="max-h-64 overflow-auto">
            {displayed.map((node) => (
              <NpcNodeItem
                key={node.term_id}
                node={node}
                depth={0}
                selected={selected}
                confidentOnly={confidentOnly}
                onToggle={toggle}
                forceExpand={q.length > 0}
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
