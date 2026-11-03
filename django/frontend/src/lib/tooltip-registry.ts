export interface TooltipEntry {
  /** Short explanation (1-2 sentences, plain text) */
  text: string;
  /**
   * Relative Quarto docs page, e.g. ``"scores-metrics.html#assembly-level-scores"``.
   * Resolved through ``buildDocsUrl`` at render time so the configured
   * base-path is applied — do NOT store a leading ``/docs/``.
   */
  docsUrl?: string;
}

export const TOOLTIP_REGISTRY: Record<string, TooltipEntry> = {
  // ── Assembly-level scores ──────────────────────────────────────────
  novelty_score_assembly: {
    text: "Average novelty across all BGCs in this assembly. Higher values (closer to 1) indicate BGC repertoires collectively dissimilar from all characterised chemistry in MIBiG.",
    docsUrl: "scores-metrics.html#assembly-level-scores",
  },
  diversity_score: {
    text: "Normalised richness of BGC broad-class types present (0\u20131). An assembly spanning Polyketide + RiPP + Terpene + NRP scores higher than one with only Polyketides.",
    docsUrl: "scores-metrics.html#assembly-level-scores",
  },
  density: {
    text: "BGC count per megabase of assembled sequence. A high-density organism is a prolific natural product producer relative to its genome size.",
    docsUrl: "scores-metrics.html#assembly-level-scores",
  },
  taxonomic_novelty: {
    text: "Measures how taxonomically distant this organism is from well-characterised BGC producers. High values indicate an underexplored lineage.",
    docsUrl: "scores-metrics.html#assembly-level-scores",
  },

  // ── BGC-level scores ───────────────────────────────────────────────
  novelty_score_bgc: {
    text: "Distance (0\u20131) to the nearest validated (MIBiG) BGC, i.e. 1 \u2212 its composite protein-domain similarity. 0 = matches a known cluster; 1 = nothing validated resembles it.",
    docsUrl: "scores-metrics.html#bgc-level-scores",
  },
  domain_novelty: {
    text: "Fraction (0\u20131) of protein domains in this BGC that are unique \u2014 not shared with other BGCs in the database. High values indicate an unusual enzymatic architecture.",
    docsUrl: "scores-metrics.html#bgc-level-scores",
  },
  nearest_validated_distance: {
    text: "Raw distance (1 \u2212 composite protein-domain similarity) to the closest validated (MIBiG) BGC. Lower values mean this cluster closely resembles a known characterised compound.",
    docsUrl: "scores-metrics.html#bgc-level-scores",
  },

  // ── Concepts ───────────────────────────────────────────────────────
  gcf_definition: {
    text: "Gene Cluster Family \u2014 a group of BGCs from different assemblies that share high protein-domain composite similarity. A large GCF with zero validated members is an uncharacterised but widespread biosynthetic strategy.",
    docsUrl: "gcf-explained.html",
  },
  mibig_validated: {
    text: "This BGC has a verified match in MIBiG, the repository of experimentally characterised biosynthetic gene clusters linked to known compounds.",
    docsUrl: "mibig-validated.html",
  },
  novel_singleton: {
    text: "This BGC does not cluster with any other BGC in the database into a GCF. It forms a family of one \u2014 the strongest possible novelty signal.",
    docsUrl: "gcf-explained.html#novel-singletons",
  },
  type_strain: {
    text: "A designated reference strain for its species, typically available for purchase from a culture collection (e.g. DSMZ, ATCC). Enable the Type Strain filter to restrict to purchasable organisms.",
    docsUrl: "glossary.html#type-strain",
  },
  bgc_class_toggle: {
    text: "Filter by biosynthetic machinery type (Polyketide, NRP, RiPP, Terpene, Saccharide, Alkaloid, Other). These reflect the enzymatic strategy, not the product\u2019s chemical structure.",
    docsUrl: "bgc-classes.html",
  },

  // ── Similarity methods ─────────────────────────────────────────────
  sorensen_dice: {
    text: "S\u00F8rensen-Dice coefficient: fraction of query domains matched vs. total domains in the union (0\u20131). Used for domain query similarity scoring.",
    docsUrl: "scores-metrics.html#the-basis-domain-based-similarity",
  },
  domain_containment: {
    text: "Filter iBGCs by the protein domains they contain. Tokens are InterPro entries (IPR…) or signature accessions (PF…, G3DSA:…, TIGR…); either form matches. OR returns iBGCs carrying any token; AND is a containment search — the slider sets the minimum fraction of input tokens that must be present (100% = all). Prefix a token with - to exclude it.",
    docsUrl: "domain-query.html",
  },
  architecture_search: {
    text: "Composite similarity over a positional domain architecture. Each iBGC is scored as w\u00B7S(domain set) + (1\u2212w)\u00B7S(adjacent-pair set), where S is the clustering run's similarity: a cosine weighted towards rare, BGC-core domains (S\u00F8rensen-Dice on older runs). Adjacency rewards matching neighbour pairs in the supplied order; the domain set measures unordered overlap. Slide right to favour bag-of-domains; slide left to favour gene-order similarity. Accessions outside the clustering run's vocabulary are silently dropped.",
    docsUrl: "domain-query.html#architecture-mode-arch",
  },
  phmmer_bitscore: {
    text: "HMMER bit score for the full target sequence. Higher = more significant. 30 is HMMER's conventional weak-significance cut; \u2265200 indicates a very strong homolog.",
    docsUrl: "sequence-search.html",
  },
  phmmer_pident: {
    text: "Aggregate percent identity across all aligned domains of the best phmmer hit (identical residues / aligned columns). 70% is a stringent default; lower for distant homologs.",
    docsUrl: "sequence-search.html",
  },
  phmmer_qcoverage: {
    text: "Fraction of the query sequence covered by the union of phmmer domain envelopes in the matched protein. Low values mean only part of your query aligned.",
    docsUrl: "sequence-search.html",
  },

  // ── Filters ────────────────────────────────────────────────────────
  biome_lineage: {
    text: "GOLD Ecosystem Classification path for metagenome assemblies, e.g. root:Environmental:Terrestrial:Soil. Filter by typing a path substring.",
    docsUrl: "biome-ontology.html",
  },
};
