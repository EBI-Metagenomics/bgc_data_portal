import { Info } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { TOOLTIP_REGISTRY } from "@/lib/tooltip-registry";

interface HelpTooltipProps {
  tooltipKey: string;
  side?: "top" | "right" | "bottom" | "left";
  className?: string;
}

export function HelpTooltip({
  tooltipKey,
  side = "top",
  className,
}: HelpTooltipProps) {
  const entry = TOOLTIP_REGISTRY[tooltipKey];
  if (!entry) {
    return null;
  }

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className={`inline-flex shrink-0 items-center justify-center text-muted-foreground hover:text-foreground ${className ?? ""}`}
            aria-label={`Help: ${tooltipKey}`}
          >
            <Info className="h-3.5 w-3.5" />
          </button>
        </TooltipTrigger>
        <TooltipContent
          side={side}
          className="max-w-xs bg-popover text-popover-foreground border shadow-md"
        >
          <p className="text-xs leading-relaxed">{entry.text}</p>
          {entry.docsUrl && (
            <a
              href={entry.docsUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 block text-xs text-primary hover:underline"
            >
              Learn more &rarr;
            </a>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
