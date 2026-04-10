import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { useFilterStore } from "@/stores/filter-store";
import { Star } from "lucide-react";
import { HelpTooltip } from "@/components/ui/help-tooltip";

export function TypeStrainToggle() {
  const typeStrainOnly = useFilterStore((s) => s.typeStrainOnly);
  const setTypeStrainOnly = useFilterStore((s) => s.setTypeStrainOnly);

  return (
    <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 p-3" data-tour="type-strain-toggle">
      <Checkbox
        id="type-strain"
        checked={typeStrainOnly}
        onCheckedChange={(v) => setTypeStrainOnly(v === true)}
      />
      <Label htmlFor="type-strain" className="flex items-center gap-1.5 text-sm font-medium cursor-pointer">
        <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
        Type strains only (purchasable)
        <HelpTooltip tooltipKey="type_strain" side="right" />
      </Label>
    </div>
  );
}
