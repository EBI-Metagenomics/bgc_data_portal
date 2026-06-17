import { useQueryStore } from "@/stores/query-store";
import { DomainQueryBuilder } from "./DomainQueryBuilder";
import { FilterChip } from "./FilterChip";

export function DomainsFilter() {
  const conditions = useQueryStore((s) => s.domainConditions);
  const removeCondition = useQueryStore((s) => s.removeDomainCondition);
  const architectureText = useQueryStore((s) => s.domainArchitectureText);
  const setArchitectureText = useQueryStore((s) => s.setDomainArchitectureText);

  // ARCH mode populates the free-text architecture field instead of discrete
  // conditions, so the count badge alone can't tell whether the filter is set.
  const active = conditions.length > 0 || architectureText.trim().length > 0;

  return (
    <FilterChip
      label="Domains"
      count={conditions.length}
      active={active}
      onClear={() => {
        for (const c of conditions) removeCondition(c.acc);
        setArchitectureText("");
      }}
      width="lg"
    >
      <DomainQueryBuilder />
    </FilterChip>
  );
}
