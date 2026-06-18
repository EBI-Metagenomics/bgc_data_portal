import { useQueryStore } from "@/stores/query-store";
import { DomainQueryBuilder } from "./DomainQueryBuilder";
import { FilterChip } from "./FilterChip";

export function DomainsFilter() {
  const domainText = useQueryStore((s) => s.domainText);
  const setDomainText = useQueryStore((s) => s.setDomainText);
  const architectureText = useQueryStore((s) => s.domainArchitectureText);
  const setArchitectureText = useQueryStore((s) => s.setDomainArchitectureText);

  // The Boolean and Architecture queries are independent and both apply, so
  // the chip badge counts tokens across both.
  const tokenCount = (t: string) =>
    t.split(/[,\s]+/).filter((x) => x.trim().length > 0).length;
  const count = tokenCount(domainText) + tokenCount(architectureText);
  const active = count > 0;

  return (
    <FilterChip
      label="Domains"
      count={count}
      active={active}
      onClear={() => {
        setDomainText("");
        setArchitectureText("");
      }}
      width="lg"
    >
      <DomainQueryBuilder />
    </FilterChip>
  );
}
