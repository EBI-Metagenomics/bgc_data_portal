import { useAssessStore } from "@/stores/assess-store";
import { AssemblyAssessmentView } from "@/components/assess/AssemblyAssessmentView";
import { BgcAssessmentView } from "@/components/assess/BgcAssessmentView";
import { Microscope } from "lucide-react";

export function AssessLayout() {
  const assetType = useAssessStore((s) => s.assetType);

  if (!assetType) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-muted-foreground">
        <Microscope className="h-16 w-16 opacity-30" />
        <h2 className="text-lg font-medium">Evaluate Asset</h2>
        <p className="max-w-md text-center text-sm">
          Right-click an assembly or BGC in the Explore or Query tabs and select
          "Evaluate Assembly" or "Evaluate BGC" to generate a structured
          assessment report.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-4 overflow-auto p-4">
      {assetType === "assembly" ? (
        <AssemblyAssessmentView />
      ) : (
        <BgcAssessmentView />
      )}
    </div>
  );
}
