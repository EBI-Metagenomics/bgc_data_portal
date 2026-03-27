import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useModeStore } from "@/stores/mode-store";
import { cn } from "@/lib/utils";
import { Microscope, FlaskConical } from "lucide-react";

export function Header() {
  const mode = useModeStore((s) => s.mode);
  const setMode = useModeStore((s) => s.setMode);

  return (
    <header
      className={cn(
        "flex items-center justify-between border-b px-6 py-3",
        mode === "explore" ? "border-b-explore/30" : "border-b-query/30"
      )}
    >
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-bold tracking-tight">
          Discovery Dashboard
        </h1>
        <ToggleGroup
          type="single"
          value={mode}
          onValueChange={(v) => {
            if (v === "explore" || v === "query") setMode(v);
          }}
          className="rounded-lg border bg-muted p-1"
        >
          <ToggleGroupItem
            value="explore"
            className={cn(
              "gap-2 rounded-md px-4 py-1.5 text-sm font-medium",
              mode === "explore" &&
                "bg-background text-explore shadow-sm"
            )}
          >
            <Microscope className="h-4 w-4" />
            Explore Genomes
          </ToggleGroupItem>
          <ToggleGroupItem
            value="query"
            className={cn(
              "gap-2 rounded-md px-4 py-1.5 text-sm font-medium",
              mode === "query" &&
                "bg-background text-query shadow-sm"
            )}
          >
            <FlaskConical className="h-4 w-4" />
            Query BGC / Chemistry
          </ToggleGroupItem>
        </ToggleGroup>
      </div>
      <div className="text-xs text-muted-foreground">
        MGnify BGCs
      </div>
    </header>
  );
}
