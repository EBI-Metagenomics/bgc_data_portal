import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card } from "@/components/ui/card";
import {
  useDiscoveryStore,
  type ResultsTab,
} from "@/stores/discovery-store";
import { NrbRosterTable } from "./NrbRosterTable";
import { VariablesMapTab } from "./VariablesMapTab";
import { UmapMapTab } from "./UmapMapTab";

/**
 * The Results card. Three tabs share a single right-click context menu and
 * a single left-click handler (sets `compareNrbId` in the discovery store).
 * Each tab renders the same underlying NRB set in a different projection.
 */
export function ResultsCard() {
  const activeTab = useDiscoveryStore((s) => s.activeResultsTab);
  const setActiveTab = useDiscoveryStore((s) => s.setActiveResultsTab);

  return (
    <Card className="flex h-full flex-col overflow-hidden">
      <Tabs
        value={activeTab}
        onValueChange={(v) => setActiveTab(v as ResultsTab)}
        className="flex h-full flex-col"
      >
        <div className="border-b px-3 pt-2">
          <TabsList className="grid w-full max-w-md grid-cols-3">
            <TabsTrigger value="roster">BGC roster</TabsTrigger>
            <TabsTrigger value="variables">Variables map</TabsTrigger>
            <TabsTrigger value="umap">UMAP</TabsTrigger>
          </TabsList>
        </div>
        <TabsContent
          value="roster"
          className="flex-1 overflow-hidden p-0 data-[state=inactive]:hidden"
        >
          <NrbRosterTable />
        </TabsContent>
        <TabsContent
          value="variables"
          className="flex-1 overflow-hidden p-0 data-[state=inactive]:hidden"
        >
          <VariablesMapTab />
        </TabsContent>
        <TabsContent
          value="umap"
          className="flex-1 overflow-hidden p-0 data-[state=inactive]:hidden"
        >
          <UmapMapTab />
        </TabsContent>
      </Tabs>
    </Card>
  );
}
