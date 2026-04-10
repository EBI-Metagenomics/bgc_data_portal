import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useBgcClasses } from "@/hooks/use-filter-data";
import { useFilterStore } from "@/stores/filter-store";
import { HelpTooltip } from "@/components/ui/help-tooltip";

export function BgcClassFilter() {
  const { data: classes, isLoading } = useBgcClasses();
  const bgcClass = useFilterStore((s) => s.bgcClass);
  const setBgcClass = useFilterStore((s) => s.setBgcClass);

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-4 w-24" />
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-8 w-full" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-2" data-tour="bgc-class-filter">
      <span className="flex items-center gap-1 text-sm font-medium">BGC Class <HelpTooltip tooltipKey="bgc_class_toggle" side="right" /></span>
      <ToggleGroup
        type="single"
        value={bgcClass}
        onValueChange={(v) => setBgcClass(v)}
        className="flex flex-wrap gap-1"
      >
        {(classes ?? []).map((cls) => (
          <ToggleGroupItem
            key={cls.name}
            value={cls.name}
            className="h-auto gap-1 rounded-full px-3 py-1 text-xs"
          >
            {cls.name}
            <Badge variant="secondary" className="text-[10px] px-1">
              {cls.count}
            </Badge>
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  );
}
