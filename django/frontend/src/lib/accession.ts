/**
 * Client-side mirror of the backend ``classify_accession`` helper
 * (``discovery/services/keyword_resolver.py``). Used by the single-field
 * Accessions filter to show a "detected kind" hint and to route the value
 * to the legacy assembly-side query params, which the assembly endpoints
 * still expect split into ``bgc_accession`` / ``assembly_accession``.
 *
 * Keep the patterns in lockstep with the Python regexes.
 */

export type AccessionKind =
  | "ibgc"
  | "prediction"
  | "cbgc"
  | "assembly"
  | "protein"
  | "unknown";

const IBGC_RE = /^MGYB-[0-9A-HJKMNP-TV-Z]{6}-[0-9A-HJKMNP-TV-Z]{2}$/i;
const CBGC_RE = /^MGYB-[0-9A-HJKMNP-TV-Z]{6}$/i;
const BGC_LEGACY_RE = /^MGYB\d+$/i;
const ASSEMBLY_RE = /^(ERZ|GCA_|GCF_)[\w.]+$/i;
const PROTEIN_RE = /^MGYP\d+$/i;

export function classifyAccession(value: string): AccessionKind {
  const v = (value ?? "").trim();
  if (!v) return "unknown";
  if (IBGC_RE.test(v)) return "ibgc";
  if (v.toUpperCase().startsWith("MGYB") && v.includes(".")) return "prediction";
  if (CBGC_RE.test(v) || BGC_LEGACY_RE.test(v)) return "cbgc";
  if (ASSEMBLY_RE.test(v)) return "assembly";
  if (PROTEIN_RE.test(v)) return "protein";
  return "unknown";
}

/** Human-readable label for the detected-kind hint chip. */
export function accessionKindLabel(kind: AccessionKind): string {
  switch (kind) {
    case "ibgc":
      return "iBGC / region";
    case "prediction":
      return "BGC prediction";
    case "cbgc":
      return "BGC (cBGC)";
    case "assembly":
      return "Assembly";
    case "protein":
      return "Protein";
    default:
      return "Contig / protein";
  }
}
