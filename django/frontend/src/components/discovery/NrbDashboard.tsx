import { Header } from "@/components/Header";
import { WelcomeModal } from "@/components/onboarding/WelcomeModal";
import { GuidedTour } from "@/components/onboarding/GuidedTour";
import { TopFiltersStrip } from "./TopFiltersStrip";
import { ResultsCard } from "./ResultsCard";
import { ReferenceDetailSlot } from "./ReferenceDetailSlot";
import { CompareDetailSlot } from "./CompareDetailSlot";
import { ProteinInfoPanel } from "./ProteinInfoPanel";

/**
 * v2 Discovery dashboard shell.
 *
 * Layout (per locked design):
 *   ┌───────────────────────────────────────────────────────────┐
 *   │  TopFiltersStrip  (DB stats · filters · [Run Query])       │
 *   ├──────────────┬────────────────────────────────────────────┤
 *   │              │  Reference NRB detail                       │
 *   │   Results    ├────────────────────────────────────────────┤
 *   │   (Roster |  │  Compare NRB detail                         │
 *   │   Variables ├────────────────────────────────────────────┤
 *   │    | UMAP)   │  Protein Information (collapsible)          │
 *   └──────────────┴────────────────────────────────────────────┘
 */
export function NrbDashboard() {
  return (
    <div
      className="flex flex-col"
      style={{ height: "calc(100vh - var(--vf-chrome-height, 90px))" }}
    >
      <WelcomeModal />
      <GuidedTour />
      <Header />
      <TopFiltersStrip />
      <div className="grid flex-1 min-h-0 grid-cols-3 grid-rows-[1fr_1fr_auto] gap-2 p-2 overflow-hidden">
        <div className="col-span-1 row-span-3 min-h-0">
          <ResultsCard />
        </div>
        <div className="col-span-2 min-h-0">
          <ReferenceDetailSlot />
        </div>
        <div className="col-span-2 min-h-0">
          <CompareDetailSlot />
        </div>
        <div className="col-span-2 min-h-0">
          <ProteinInfoPanel />
        </div>
      </div>
    </div>
  );
}
