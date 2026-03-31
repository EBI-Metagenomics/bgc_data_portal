import { Loader2 } from "lucide-react";

interface AssessmentLoadingProps {
  label: string;
}

export function AssessmentLoading({ label }: AssessmentLoadingProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24 text-muted-foreground">
      <Loader2 className="h-10 w-10 animate-spin" />
      <p className="text-sm">
        Computing assessment for <span className="font-medium">{label}</span>...
      </p>
      <p className="text-xs">This may take a few seconds.</p>
    </div>
  );
}
