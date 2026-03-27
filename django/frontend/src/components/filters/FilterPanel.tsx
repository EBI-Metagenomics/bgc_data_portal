import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TypeStrainToggle } from "./TypeStrainToggle";
import { TaxonomyFilter } from "./TaxonomyFilter";
import { BgcClassFilter } from "./BgcClassFilter";
import { NpClassFilter } from "./NpClassFilter";
import { DomainQueryBuilder } from "./DomainQueryBuilder";
import { useFilterStore } from "@/stores/filter-store";
import { useModeStore } from "@/stores/mode-store";
import { Search, RotateCcw } from "lucide-react";

export function FilterPanel() {
  const mode = useModeStore((s) => s.mode);
  const search = useFilterStore((s) => s.search);
  const setSearch = useFilterStore((s) => s.setSearch);
  const clearFilters = useFilterStore((s) => s.clearFilters);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Filters
        </h2>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 gap-1 text-xs"
          onClick={clearFilters}
        >
          <RotateCcw className="h-3 w-3" />
          Reset
        </Button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search organisms..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-9 pl-9 text-sm"
        />
      </div>

      <TypeStrainToggle />

      {mode === "query" ? (
        <Tabs defaultValue="filters">
          <TabsList className="w-full">
            <TabsTrigger value="filters" className="flex-1 text-xs">
              Filters
            </TabsTrigger>
            <TabsTrigger value="domains" className="flex-1 text-xs">
              Domain Query
            </TabsTrigger>
          </TabsList>
          <TabsContent value="filters" className="space-y-4">
            <TaxonomyFilter />
            <BgcClassFilter />
            <NpClassFilter />
          </TabsContent>
          <TabsContent value="domains">
            <DomainQueryBuilder />
          </TabsContent>
        </Tabs>
      ) : (
        <div className="space-y-4">
          <TaxonomyFilter />
          <BgcClassFilter />
          <NpClassFilter />
        </div>
      )}
    </div>
  );
}
