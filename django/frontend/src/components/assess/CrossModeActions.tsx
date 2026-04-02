import { useModeStore } from "@/stores/mode-store";
import { useQueryStore } from "@/stores/query-store";
import { useFilterStore } from "@/stores/filter-store";
import { fetchSimilarAssemblies } from "@/api/assessment";
import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";
import { toast } from "sonner";

interface CrossModeActionsProps {
  assetType: "assembly" | "bgc";
  assetId: number;
}

export function CrossModeActions({ assetType, assetId }: CrossModeActionsProps) {
  const setMode = useModeStore((s) => s.setMode);
  const setSimilarBgcSourceId = useQueryStore((s) => s.setSimilarBgcSourceId);
  const setAssemblyIds = useFilterStore((s) => s.setAssemblyIds);

  if (assetType === "assembly") {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={async () => {
          try {
            const ids = await fetchSimilarAssemblies(assetId);
            if (ids.length === 0) {
              toast.info("No similar assemblies found");
              return;
            }
            setAssemblyIds(ids.join(","));
            setMode("explore");
          } catch {
            toast.error("Failed to find similar assemblies");
          }
        }}
      >
        Browse similar assemblies
        <ArrowRight className="ml-1 h-3 w-3" />
      </Button>
    );
  }

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() => {
        setSimilarBgcSourceId(assetId);
        setMode("query");
      }}
    >
      Find in purchasable strains
      <ArrowRight className="ml-1 h-3 w-3" />
    </Button>
  );
}
