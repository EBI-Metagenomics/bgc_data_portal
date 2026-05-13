import { useDiscoveryStore } from "@/stores/discovery-store";
import { CompactNrbDetail } from "./CompactNrbDetail";

export function ReferenceDetailSlot() {
  const referenceNrbId = useDiscoveryStore((s) => s.referenceNrbId);
  return <CompactNrbDetail nrbId={referenceNrbId} variant="reference" />;
}
