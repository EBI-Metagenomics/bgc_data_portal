import { useQuery } from "@tanstack/react-query";
import { fetchNrbUmap } from "@/api/nrbs";
import { Loader2 } from "lucide-react";

/**
 * UMAP tab — fetches NRB UMAP coordinates (including ``umap_projected``
 * partial-derived points). Plotly rendering ships in P2.2b; for now the
 * tab confirms the data wiring is alive.
 */
export function UmapMapTab() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["nrb-umap"],
    queryFn: () => fetchNrbUmap({ include_partials: true }),
  });

  const primary = data?.filter((p) => !p.umap_projected).length ?? 0;
  const projected = data?.filter((p) => p.umap_projected).length ?? 0;

  return (
    <div className="flex h-full items-center justify-center p-3 text-sm text-muted-foreground">
      {isLoading ? (
        <span>
          <Loader2 className="mr-2 inline h-4 w-4 animate-spin" />
          Loading UMAP…
        </span>
      ) : isError ? (
        <span className="text-destructive">
          {(error as Error)?.message ?? "Failed to load UMAP"}
        </span>
      ) : (
        <span>
          {primary.toLocaleString()} primary · {projected.toLocaleString()}{" "}
          projected partials · Plotly view wires up next
        </span>
      )}
    </div>
  );
}
