import { useDiscoveryStore } from "@/stores/discovery-store";
import { CompactNrbDetail } from "./CompactNrbDetail";

export function CompareDetailSlot() {
  const compareNrbId = useDiscoveryStore((s) => s.compareNrbId);
  return <CompactNrbDetail nrbId={compareNrbId} variant="compare" />;
}
