/**
 * Domain-accession helpers shared by the report and the domain filters.
 *
 * A "preferred token" for a domain is its InterPro entry accession when one
 * is set (e.g. ``IPR000873``), else the raw signature accession (``PF00501``,
 * ``G3DSA:3.30.559.30``, …). This mirrors the backend's IPR-projection
 * (``project_to_ipr``) so copied sets paste straight back into the domain
 * filter, which resolves either form.
 */

export interface DomainLike {
  domain_acc: string;
  interpro_entry_acc?: string;
}

/** External InterPro entry page for an ``IPRxxxxxx`` accession. */
export function interproEntryUrl(acc: string): string {
  return `https://www.ebi.ac.uk/interpro/entry/InterPro/${acc}/`;
}

/** InterPro entry accession if present, else the raw signature accession. */
export function preferredDomainToken(d: DomainLike): string {
  const ipr = (d.interpro_entry_acc ?? "").trim();
  return ipr || d.domain_acc;
}

/**
 * Ordered, de-duplicated comma-separated set of preferred tokens for the
 * given rows. Preserves first-seen order so the output is deterministic.
 */
export function domainTokenSet(rows: DomainLike[]): string {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const d of rows) {
    const tok = preferredDomainToken(d);
    if (tok && !seen.has(tok)) {
      seen.add(tok);
      out.push(tok);
    }
  }
  return out.join(", ");
}
