import { AssemblySidebarShortlist } from "./AssemblySidebarShortlist";
import { BgcSidebarShortlist } from "./BgcSidebarShortlist";

export function SidebarShortlists() {
  return (
    <div className="rounded-md bg-explore/5 p-3 space-y-3">
      <AssemblySidebarShortlist />
      <BgcSidebarShortlist />
    </div>
  );
}
