import { ReactNode, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface PanelContainerProps {
  title: string;
  children: ReactNode;
  className?: string;
  collapsible?: boolean;
  defaultCollapsed?: boolean;
  actions?: ReactNode;
  constrained?: boolean;
  dataTour?: string;
}

export function PanelContainer({
  title,
  children,
  className,
  collapsible = false,
  defaultCollapsed = false,
  actions,
  constrained = false,
  dataTour,
}: PanelContainerProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  return (
    <article
      className={cn(
        "vf-card vf-card--brand vf-card--bordered flex flex-col",
        constrained && "overflow-hidden min-h-0",
        className
      )}
      {...(dataTour ? { "data-tour": dataTour } : {})}
    >
      <div className={cn(
        "vf-card__content | vf-stack vf-stack--200 flex flex-col",
        constrained && "flex-1 min-h-0"
      )}>
        <div className="flex items-center justify-between">
          <h3 className="vf-card__heading" style={{ margin: 0 }}>{title}</h3>
          <div className="flex items-center gap-2">
            {actions}
            {collapsible && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0"
                onClick={() => setCollapsed(!collapsed)}
              >
                {collapsed ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronUp className="h-4 w-4" />
                )}
              </Button>
            )}
          </div>
        </div>
        {!collapsed && <div className={cn("flex-1 overflow-auto", constrained && "min-h-0")}>{children}</div>}
      </div>
    </article>
  );
}
