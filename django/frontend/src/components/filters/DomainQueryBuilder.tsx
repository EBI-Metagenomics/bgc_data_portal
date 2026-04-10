import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Command, CommandInput, CommandItem, CommandList, CommandEmpty } from "@/components/ui/command";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Plus, Minus, X } from "lucide-react";
import { fetchDomains } from "@/api/filters";
import { useQueryStore } from "@/stores/query-store";
import { HelpTooltip } from "@/components/ui/help-tooltip";

export function DomainQueryBuilder() {
  const [search, setSearch] = useState("");
  const conditions = useQueryStore((s) => s.domainConditions);
  const logic = useQueryStore((s) => s.logic);
  const addCondition = useQueryStore((s) => s.addDomainCondition);
  const removeCondition = useQueryStore((s) => s.removeDomainCondition);
  const toggleRequired = useQueryStore((s) => s.toggleDomainRequired);
  const setLogic = useQueryStore((s) => s.setLogic);

  const { data: domainResults } = useQuery({
    queryKey: ["filters", "domains", search],
    queryFn: () => fetchDomains({ search, page: 1, page_size: 10 }),
    enabled: search.length >= 2,
    staleTime: 30_000,
  });

  return (
    <div className="space-y-3" data-tour="domain-query">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1 text-sm font-medium">Domain Query <HelpTooltip tooltipKey="sorensen_dice" side="right" /></span>
        <ToggleGroup
          type="single"
          value={logic}
          onValueChange={(v) => {
            if (v === "and" || v === "or") setLogic(v);
          }}
          className="h-7"
        >
          <ToggleGroupItem value="and" className="h-6 px-2 text-xs">
            AND
          </ToggleGroupItem>
          <ToggleGroupItem value="or" className="h-6 px-2 text-xs">
            OR
          </ToggleGroupItem>
        </ToggleGroup>
      </div>

      {/* Current conditions */}
      {conditions.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {conditions.map((cond) => (
            <Badge
              key={cond.acc}
              variant={cond.required ? "default" : "destructive"}
              className="gap-1 text-xs"
            >
              {cond.required ? (
                <Plus className="h-3 w-3" />
              ) : (
                <Minus className="h-3 w-3" />
              )}
              {cond.acc}
              <button
                className="ml-1 hover:opacity-70"
                onClick={() => toggleRequired(cond.acc)}
                title="Toggle required/excluded"
              >
                {cond.required ? "req" : "excl"}
              </button>
              <button
                className="hover:opacity-70"
                onClick={() => removeCondition(cond.acc)}
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}

      {/* Domain search */}
      <Command className="rounded-md border" shouldFilter={false}>
        <CommandInput
          placeholder="Search domains (e.g. KS, PF00109)..."
          value={search}
          onValueChange={setSearch}
        />
        <CommandList>
          {search.length >= 2 && (
            <>
              <CommandEmpty>No domains found</CommandEmpty>
              {(domainResults?.items ?? []).map((domain) => (
                <CommandItem
                  key={domain.acc}
                  value={domain.acc}
                  onSelect={() => {
                    addCondition({ acc: domain.acc, required: true });
                    setSearch("");
                  }}
                  disabled={conditions.some((c) => c.acc === domain.acc)}
                >
                  <div className="flex flex-1 items-center justify-between">
                    <div>
                      <span className="font-mono text-xs">{domain.acc}</span>
                      <span className="ml-2 text-xs text-muted-foreground">
                        {domain.name}
                      </span>
                    </div>
                    <Badge variant="secondary" className="text-[10px]">
                      {domain.count}
                    </Badge>
                  </div>
                </CommandItem>
              ))}
            </>
          )}
        </CommandList>
      </Command>

      {conditions.length > 0 && (
        <Button
          variant="outline"
          size="sm"
          className="w-full text-xs"
          onClick={() => useQueryStore.getState().clearQuery()}
        >
          Clear all domains
        </Button>
      )}
    </div>
  );
}
