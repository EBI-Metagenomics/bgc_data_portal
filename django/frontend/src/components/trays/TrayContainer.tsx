import { GenomeShortlistTray } from "./GenomeShortlistTray";
import { BgcShortlistTray } from "./BgcShortlistTray";

export function TrayContainer() {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <GenomeShortlistTray />
      <BgcShortlistTray />
    </div>
  );
}
