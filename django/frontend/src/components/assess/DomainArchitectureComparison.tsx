import { useState } from "react";
import { RegionPlot } from "@/components/bgc/RegionPlot";
import { useBgcRegion } from "@/hooks/use-bgc-region";
import { useBgcRegions } from "@/hooks/use-bgc-regions";
import { Loader2 } from "lucide-react";
import type { RegionCds } from "@/api/types";

interface DomainArchitectureComparisonProps {
  bgcId: number;
  nearestValidatedBgcId: number | null;
  nearestValidatedAccession: string | null;
  comparisonBgcIds?: number[];
}

export function DomainArchitectureComparison({
  bgcId,
  nearestValidatedBgcId,
  nearestValidatedAccession,
  comparisonBgcIds,
}: DomainArchitectureComparisonProps) {
  const isUploaded = bgcId < 0;
  // Uploaded BGCs aren't in the DB, so skip the region fetch that would 404.
  const submittedRegion = useBgcRegion(isUploaded ? null : bgcId);
  const validatedRegion = useBgcRegion(nearestValidatedBgcId);

  // Filter the comparison list to avoid redundant fetches: drop the
  // submitted BGC and the nearest-validated reference (both rendered
  // separately above the sibling section).
  const siblingIds = (comparisonBgcIds ?? []).filter(
    (id) => id !== bgcId && id !== nearestValidatedBgcId,
  );
  const siblingRegions = useBgcRegions(siblingIds);

  const [selectedCds, setSelectedCds] = useState<string | null>(null);

  const handleCdsClick = (_cds: RegionCds) => {
    setSelectedCds((prev) => (prev === _cds.protein_id ? null : _cds.protein_id));
  };

  if (!isUploaded && submittedRegion.isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const hasSubmittedRegion = !isUploaded && !!submittedRegion.data;
  const hasAnyPanel =
    hasSubmittedRegion ||
    !!nearestValidatedBgcId ||
    siblingIds.length > 0;

  if (isUploaded && !hasAnyPanel) {
    return (
      <p className="py-4 text-sm text-muted-foreground">
        Region-level architecture is unavailable for uploaded BGCs — the
        upload bundle doesn't include CDS coordinates. See the Domain
        Architecture Differential panel above for the domain summary.
      </p>
    );
  }

  if (!hasAnyPanel) {
    return (
      <p className="py-4 text-sm text-muted-foreground">
        Region data not available for this BGC.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {/* Submitted BGC region */}
      {hasSubmittedRegion && (
        <div>
          <p className="mb-1 text-xs font-medium">Submitted BGC</p>
          <RegionPlot
            data={submittedRegion.data!}
            onCdsClick={handleCdsClick}
            selectedCdsId={selectedCds}
          />
        </div>
      )}

      {/* Nearest Validated region */}
      {nearestValidatedBgcId && (
        <div>
          <p className="mb-1 text-xs font-medium">
            Nearest Validated: {nearestValidatedAccession || "Unknown"}
          </p>
          {validatedRegion.isLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : validatedRegion.data ? (
            <RegionPlot
              data={validatedRegion.data}
              onCdsClick={handleCdsClick}
              selectedCdsId={selectedCds}
            />
          ) : (
            <p className="py-2 text-xs text-muted-foreground">
              Region data not available for validated reference.
            </p>
          )}
        </div>
      )}

      {!nearestValidatedBgcId && nearestValidatedAccession && (
        <p className="text-xs text-muted-foreground">
          Nearest Validated: {nearestValidatedAccession} (region data not available)
        </p>
      )}

      {/* GCF sibling BGCs — batched fetch so one request covers all. */}
      {siblingIds.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs font-medium text-muted-foreground">
            GCF siblings
          </p>
          {siblingRegions.isLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : siblingRegions.data && siblingRegions.data.length > 0 ? (
            siblingRegions.data.map((sibling) => (
              <div key={sibling.bgc_id}>
                <p className="mb-1 text-xs font-medium">{sibling.accession}</p>
                <RegionPlot
                  data={sibling.region}
                  onCdsClick={handleCdsClick}
                  selectedCdsId={selectedCds}
                />
              </div>
            ))
          ) : (
            <p className="py-2 text-xs text-muted-foreground">
              No sibling region data available.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
