import type { SunburstNode } from "@/api/types";

/**
 * Categorical palette for colouring sunburst arcs by a fixed-depth ancestor
 * (e.g. taxonomy by phylum, biome by depth 3). Distinct, reasonably
 * colour-blind-tolerant hues; cycled if there are more groups than colours.
 */
export const SUNBURST_PALETTE = [
  "#3b82f6", // blue
  "#ef4444", // red
  "#10b981", // emerald
  "#f59e0b", // amber
  "#8b5cf6", // violet
  "#ec4899", // pink
  "#14b8a6", // teal
  "#f97316", // orange
  "#6366f1", // indigo
  "#84cc16", // lime
  "#06b6d4", // cyan
  "#a855f7", // purple
  "#eab308", // yellow
  "#22c55e", // green
  "#e11d48", // rose
];

// Rings shallower than the colour depth (e.g. root / kingdom) stay neutral so
// the coloured ancestor ring reads as the legend.
const NEUTRAL = "#cbd5e1"; // slate-300

/**
 * Return a ``marker.colors`` array aligned to ``nodes``: every node is
 * coloured by its ancestor at ``depth`` (root = depth 0), and descendants
 * inherit that ancestor's colour. Nodes shallower than ``depth`` get a
 * neutral grey. Colour assignment is first-seen-wins over ``nodes`` order, so
 * it is deterministic for a given payload.
 */
export function colorByAncestorDepth(
  nodes: SunburstNode[],
  depth: number,
  palette: string[] = SUNBURST_PALETTE,
): string[] {
  const byId = new Map(nodes.map((n) => [n.id, n]));

  const nodeDepth = (start: SunburstNode): number => {
    let d = 0;
    let cur: SunburstNode | undefined = start;
    const seen = new Set<string>();
    while (cur && cur.parent && !seen.has(cur.id)) {
      seen.add(cur.id);
      cur = byId.get(cur.parent);
      d++;
    }
    return d;
  };

  const ancestorAt = (start: SunburstNode): SunburstNode | undefined => {
    let cur: SunburstNode | undefined = start;
    let d = nodeDepth(start);
    const seen = new Set<string>();
    while (cur && d > depth && !seen.has(cur.id)) {
      seen.add(cur.id);
      cur = byId.get(cur.parent);
      d--;
    }
    return cur && d === depth ? cur : undefined;
  };

  const colorForAncestor = new Map<string, string>();
  let next = 0;
  return nodes.map((n) => {
    const anc = ancestorAt(n);
    if (!anc) return NEUTRAL;
    let c = colorForAncestor.get(anc.id);
    if (!c) {
      c = palette[next % palette.length] ?? NEUTRAL;
      next += 1;
      colorForAncestor.set(anc.id, c);
    }
    return c;
  });
}
