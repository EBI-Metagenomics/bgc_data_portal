import { useAssessStore } from "@/stores/assess-store";
import { exportAssessmentJson } from "@/api/assessment";
import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";
import { toast } from "sonner";

export function AssessmentExportButton() {
  const taskId = useAssessStore((s) => s.taskId);
  const status = useAssessStore((s) => s.status);

  if (!taskId || status !== "success") return null;

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={async () => {
        try {
          await exportAssessmentJson(taskId);
        } catch {
          toast.error("Export failed");
        }
      }}
    >
      <Download className="mr-1 h-3 w-3" />
      Export JSON
    </Button>
  );
}
