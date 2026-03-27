import { useBgcDetail } from "@/hooks/use-bgc-detail";
import { DomainArchitecture } from "./DomainArchitecture";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { useModeStore } from "@/stores/mode-store";
import { useSelectionStore } from "@/stores/selection-store";
import { useQueryStore } from "@/stores/query-store";
import { Microscope, Search, Star } from "lucide-react";

interface BgcDetailProps {
  bgcId: number;
}

export function BgcDetail({ bgcId }: BgcDetailProps) {
  const { data: bgc, isLoading } = useBgcDetail(bgcId);
  const setMode = useModeStore((s) => s.setMode);
  const setActiveGenomeId = useSelectionStore((s) => s.setActiveGenomeId);
  const setSimilarBgcSourceId = useQueryStore((s) => s.setSimilarBgcSourceId);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-8 w-full" />
      </div>
    );
  }

  if (!bgc) {
    return (
      <p className="py-4 text-center text-sm text-muted-foreground">
        BGC not found
      </p>
    );
  }

  const classification = [
    bgc.classification_l1,
    bgc.classification_l2,
    bgc.classification_l3,
  ]
    .filter(Boolean)
    .join(" > ");

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h4 className="font-mono font-semibold">{bgc.accession}</h4>
          <p className="mt-1 text-sm text-muted-foreground">{classification}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge variant={bgc.is_partial ? "outline" : "secondary"}>
              {bgc.is_partial ? "Partial" : "Complete"}
            </Badge>
            {bgc.is_validated && <Badge variant="default">Validated</Badge>}
            <Badge variant="outline">{bgc.size_kb.toFixed(1)} kb</Badge>
          </div>
        </div>
        <div className="flex gap-2">
          {bgc.parent_genome && (
            <Button
              variant="outline"
              size="sm"
              className="gap-1 text-xs"
              onClick={() => {
                setActiveGenomeId(bgc.parent_genome!.assembly_id);
                setMode("explore");
              }}
            >
              <Microscope className="h-3 w-3" />
              Explore parent genome
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            className="gap-1 text-xs"
            onClick={() => {
              setSimilarBgcSourceId(bgc.id);
              setMode("query");
            }}
          >
            <Search className="h-3 w-3" />
            Find similar BGCs
          </Button>
        </div>
      </div>

      <Separator />

      {/* Scores */}
      <div className="grid grid-cols-2 gap-4 text-xs md:grid-cols-4">
        <div>
          <span className="text-muted-foreground">Novelty</span>
          <p className="font-mono font-medium">{bgc.novelty_score.toFixed(3)}</p>
        </div>
        <div>
          <span className="text-muted-foreground">Domain Novelty</span>
          <p className="font-mono font-medium">{bgc.domain_novelty.toFixed(3)}</p>
        </div>
        {bgc.nearest_mibig_accession && (
          <div>
            <span className="text-muted-foreground">Nearest MIBiG</span>
            <p className="font-mono font-medium">
              {bgc.nearest_mibig_accession}
            </p>
            <p className="text-muted-foreground">
              dist: {bgc.nearest_mibig_distance?.toFixed(3)}
            </p>
          </div>
        )}
      </div>

      <Separator />

      {/* Domain architecture */}
      <div>
        <h5 className="mb-2 text-sm font-medium">Domain Architecture</h5>
        <DomainArchitecture domains={bgc.domain_architecture} />
      </div>

      {/* Parent genome */}
      {bgc.parent_genome && (
        <>
          <Separator />
          <div className="text-xs">
            <h5 className="mb-1 text-sm font-medium">Parent Genome</h5>
            <div className="flex items-center gap-2">
              <span>{bgc.parent_genome.organism_name ?? bgc.parent_genome.accession}</span>
              {bgc.parent_genome.is_type_strain && (
                <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
              )}
              {bgc.parent_genome.taxonomy_family && (
                <Badge variant="outline" className="text-[10px]">
                  {bgc.parent_genome.taxonomy_family}
                </Badge>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
