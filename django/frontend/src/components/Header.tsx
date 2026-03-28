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
        "flex items-center justify-between border-b px-6 py-2",
        mode === "explore" ? "border-b-explore/30" : "border-b-query/30"
      )}
    >
      <div className="vf-cluster">
        <div className="vf-cluster__inner" style={{ alignItems: "center", gap: "1rem" }}>
          <h2 className="vf-text-heading--5" style={{ margin: 0 }}>
            Discovery Dashboard
          </h2>
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
      </div>
    </header>
  );
}
