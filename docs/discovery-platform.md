# Discovery Platform — Feature Reference

The Discovery Platform is the primary interface for exploring, searching, and evaluating Biosynthetic Gene Clusters (BGCs) in the MGnify BGCs database. It provides three complementary modes of interaction, each designed for a different analytical workflow.

## Table of Contents

- [Platform Overview](#platform-overview)
- [Global UI Layout](#global-ui-layout)
- [Shared Filters](#shared-filters)
- [Mode: Explore Assemblies](#mode-explore-assemblies)
- [Mode: Search BGCs](#mode-search-bgcs)
- [Mode: Evaluate Asset](#mode-evaluate-asset)
- [Shortlist Trays](#shortlist-trays)
- [Scoring and Similarity](#scoring-and-similarity)
- [Controlled Vocabularies and Ontologies](#controlled-vocabularies-and-ontologies)
- [Cross-Mode Interactions](#cross-mode-interactions)
- [Download and Export](#download-and-export)

---

## Platform Overview

The Discovery Platform operates in three modes, selectable from the header tabs:

| Mode | Purpose |
|------|---------|
| **Search BGCs** | Find specific BGCs by protein domain architecture, sequence similarity, or chemical structure (SMILES). Returns ranked results with similarity scores. |
| **Explore Assemblies** | Browse and filter the assembly catalogue. Visualise assembly-level statistics, then drill into the BGCs contained within selected or shortlisted assemblies. |
| **Evaluate Asset** | Generate structured assessment reports for an individual assembly or BGC — either from the database or uploaded as a file. Compares the asset against the full database, showing novelty, redundancy, and chemical space context. |

---

## Global UI Layout

The interface is divided into three persistent regions:

1. **Header** — Contains the platform title ("Discovery Platform") and the three mode tabs. The active mode is highlighted.
2. **Sidebar** (left) — Contains filters (in Explore and Search modes) or the upload panel (in Evaluate mode). Below the filters, the sidebar shows the two shortlist trays (assemblies and BGCs).
3. **Main Content Area** (centre/right) — Displays mode-specific panels: rosters (tables), scatter plots, statistics charts, and detail views.

On mobile, the sidebar collapses into a slide-out sheet.

---

## Shared Filters

The following filters appear in the sidebar for both **Explore Assemblies** and **Search BGCs** modes. Changing any filter resets the current query, requiring the user to re-run.

### Organism Search
Free-text input that filters assemblies by organism name substring match.

### Type Strain Toggle
A toggle switch to restrict results to assemblies from type strain organisms only. Type strains are reference organisms with well-characterised taxonomy.

### Assembly Type
Filter by the type of genomic assembly:
- **Metagenome** — assembled from environmental metagenomic samples
- **Genome** — single-organism genome assembly
- **Region** — sub-genomic region

### Taxonomy Tree
A hierarchical, expandable tree of NCBI taxonomic ranks: Kingdom, Phylum, Class, Order, Family, Genus, Species. Selecting a node filters to all assemblies within that lineage. Counts are shown next to each taxon.

### Biome Lineage
A text input for filtering by GOLD Ecosystem Classification lineage. Uses colon-delimited paths (e.g., `root:Environmental:Terrestrial:Soil`). Matches any assembly whose biome path contains the entered substring.

### BGC Class
Toggle buttons for MIBiG broad biosynthetic classes. Each button shows the class name and the number of matching BGCs in the database:
- Polyketide
- NRP (Non-Ribosomal Peptide)
- RiPP (Ribosomally synthesised and Post-translationally modified Peptide)
- Terpene
- Saccharide
- Alkaloid
- Other

Selecting a class filters to BGCs (and their parent assemblies) belonging to that class. Only one class can be active at a time.

### ChemOnt Chemical Ontology
An expandable tree of ChemOnt (Chemical Ontology) classes. Each node shows the class name and associated BGC count. Selecting a node filters to BGCs whose natural products are annotated with that ChemOnt term or any of its descendants.

### Accession Lookups (Search BGCs only)
Two text inputs for direct identifier lookups:
- **Assembly Accession** — e.g., `ERZ...`
- **BGC Accession (MGYB)** — e.g., `MGYB000000000001`

---

## Mode: Explore Assemblies

### Purpose
Browse the full assembly catalogue with filtering. Discover assemblies of interest, then inspect their BGC content.

### Sidebar
Displays the shared filters listed above (without the Query tab or accession lookup inputs).

### Main Content Panels

The main area is divided into two sections: an **Assembly triad** (top) and a **BGC triad** (bottom). Each triad contains three panels arranged in a 2x2 grid: a roster (full-height, left), a scatter plot (top-right), and a statistics panel (bottom-right).

#### Assembly Triad

**Assembly Roster** (table)
- Columns: Organism name, Accession, Type Strain badge, BGC Count, Diversity score, Novelty score, Density score
- Sortable by: Organism, BGC Count, Novelty, Diversity, Density
- Paginated
- Clicking a row selects the assembly and reveals the Assembly Detail panel
- Right-click context menu: Add to Shortlist, Evaluate Assembly

**Assembly Space Map** (scatter plot)
- Interactive 2D scatter plot of assemblies
- Configurable axes: Diversity, Novelty, Density, Taxonomic Novelty
- Points colour-coded by dominant taxonomy
- Click a point to select the corresponding assembly

**Assembly Stats** (charts)
- Summary statistics for the currently filtered/visible assemblies
- Includes: Taxonomy sunburst, score distributions, type strain breakdown
- Exportable as JSON or TSV

#### BGC Triad

The BGC panels show BGCs **from the selected or shortlisted assemblies**. A badge indicates the source (e.g., "From 3 shortlisted assemblies" or "From selected assembly").

**BGC Roster** (table)
- Columns: Accession, Classification, Size (kb), Novelty score, Domain Novelty, Nearest Validated BGC
- Sortable by: Accession, Classification, Novelty, Size, Domain Novelty
- Clicking a row selects the BGC and reveals the BGC Detail panel
- Right-click context menu: Add to Shortlist, Evaluate BGC, Find Similar BGCs

**BGC Space Map** (scatter plot)
- 2D scatter of BGCs, typically Novelty vs Domain Novelty
- Points colour-coded by BGC class (Polyketide, NRP, RiPP, etc.)
- Distinguishes validated (MIBiG) vs unvalidated BGCs
- Click a point to select

**BGC Stats** (charts)
- Statistics for the current BGC set: class distribution, domain frequencies, completeness, NP class sunburst
- Exportable as JSON or TSV

### Detail Panels

**Assembly Detail** — Appears below the assembly triad when an assembly is selected. Shows:
- Organism name and accession
- Type strain badge (if applicable)
- Score metrics displayed as progress bars
- Links to external resources
- Actions: Add to Shortlist, Evaluate Assembly

**BGC Detail** — Appears below the BGC triad when a BGC is selected. Shows:
- Accession and classification path
- Novelty score and nearest validated BGC distance
- Domain architecture diagram (region plot showing gene arrangement and protein domains)
- Natural products with ChemOnt lineage annotations
- Actions: Add to Shortlist, Evaluate BGC, Find Similar BGCs

### Interaction Flow
1. Set filters in the sidebar
2. Click "Run Query" to load filtered assemblies into the Assembly panels
3. Click an assembly row (or shortlist multiple) to populate the BGC panels
4. Click a BGC to see its detail
5. From any detail panel, navigate to Evaluate or Search mode via action buttons

---

## Mode: Search BGCs

### Purpose
Search for specific BGCs using advanced query criteria: protein domain architecture, sequence similarity, or chemical structure. Returns BGCs ranked by similarity score.

### Sidebar
The sidebar in Search mode has two tabs:
- **Filters** — All shared filters (Taxonomy, Biome, BGC Class, ChemOnt) plus Assembly and BGC accession lookup inputs
- **Query** — Advanced search tools (described below)

#### Domain Query Builder
Build complex queries based on Pfam protein domains present in BGCs:
- Add one or more domain conditions by entering Pfam accessions (e.g., `PF00109`)
- Set domain logic: **AND** (all specified domains must be present) or **OR** (any specified domain matches)
- Each condition can be toggled as required or optional

#### Sequence Search
Search by protein or nucleotide sequence similarity:
- Paste a FASTA sequence
- Select comparison type: BGC-level or protein-level
- Select similarity method: HMMER (profile HMM scoring) or embedding cosine similarity
- Set a similarity threshold (0–1)

#### Chemical Structure Search (SMILES)
Search by chemical structure using SMILES notation:
- Enter a SMILES string representing a compound
- Set a Tanimoto similarity threshold (default 0.85)
- Matches BGCs whose associated natural products have similar Morgan fingerprints

### Main Content Panels

The layout mirrors Explore mode but with **BGCs on top** (primary results) and **Assemblies on bottom** (derived from result BGCs).

#### BGC Triad (top)

**BGC Roster** (query results table)
- Displays search results ranked by similarity score
- Columns: Accession, Classification, Similarity Score, Novelty, Domain Novelty, Size (kb)
- The similarity score reflects the match strength from the active query method

**BGC Space Map** (scatter plot)
- X-axis defaults to Query Similarity when a SMILES or sequence query is active
- Y-axis typically shows Novelty or Domain Novelty
- Highlights query result BGCs

**BGC Stats** (charts)
- Statistics computed over the query result set

#### Assembly Triad (bottom)

Derived from the BGCs in the result set. Shows the parent assemblies of shortlisted or selected BGCs.

**Assembly Roster**
- Shows assemblies that contain the result BGCs
- Badge indicates source: "From N shortlisted BGCs" or "From selected BGC"

**Assembly Space Map** and **Assembly Stats** — same as Explore mode but scoped to parent assemblies.

### Query Execution
- Combine filters and query criteria as needed
- The "Run Query" button activates when at least one filter or query criterion is set
- Status indicators show active criteria (domain count, sequence/SMILES flags)
- Queries run asynchronously; results stream in as they become available
- Multiple query types can be combined (e.g., domain + SMILES); results are intersected

---

## Mode: Evaluate Asset

### Purpose
Generate a comprehensive assessment report for a single assembly or BGC. Compare it against the full database to understand its novelty, redundancy, and chemical space position.

### Sidebar
In Evaluate mode, the sidebar shows:
- **Upload for Evaluation** panel — allows submitting external files for assessment
- Shortlist trays (below)

The upload panel has two tabs:
- **Single BGC** — Upload a single BGC package
- **Assembly** — Upload an assembly package

Files are submitted as `.tar.gz` or `.tgz` archives via drag-and-drop or file picker.

### Entering Evaluate Mode
There are three ways to evaluate an asset:
1. **From another mode** — Right-click a row in any roster and select "Evaluate", or click "Evaluate" in a detail panel
2. **Upload** — Use the sidebar upload panel to submit an external file
3. **Direct navigation** — Select an asset by accession

### Assembly Assessment View

When evaluating an assembly, the following panels are displayed:

**Header** — Assembly accession, organism name, type strain badge. Actions: Add to Shortlist, Export JSON, Browse Similar Assemblies.

**Priority Ranking** — Shows the assembly's overall rank within the database (e.g., "Rank 42 of 15,000").

**Priority Score Radar** — A radar (spider) chart comparing the assembly's percentile scores across multiple dimensions (Diversity, Novelty, Density) against database reference lines (mean and 90th percentile).

**Score Percentile Distributions** — Gauge charts showing where the assembly falls on the percentile distribution for each score dimension. Reference lines mark the database mean and 90th percentile.

**BGC Roster, Space Map, and Stats** — The standard BGC triad showing all BGCs belonging to this assembly.

**Redundancy Matrix** — A heatmap showing the breakdown of the assembly's BGCs across categories:
- Novel GCF (gene cluster family not seen elsewhere)
- Known GCF without type strain coverage
- Known GCF with type strain coverage

This helps users understand how much of the assembly's biosynthetic potential is already represented in the database.

**BGC Embeddings Map** — A UMAP projection showing this assembly's BGCs positioned in the global chemical/sequence space. Validated (MIBiG) reference BGCs are shown as landmarks. Summary statistics include mean distance to nearest validated BGC and sparse fraction (proportion of BGCs in low-density regions).

### BGC Assessment View

When evaluating an individual BGC, the following panels are displayed:

**Header** — BGC accession, classification path, "Novel Singleton" badge (if the BGC does not cluster with any known family). Actions: Add to Shortlist, Export JSON, Find in Purchasable Strains.

**GCF Placement** — Shows the Gene Cluster Family context:
- Family ID and known chemistry annotation (if available)
- Member count and validated member count
- Mean novelty of the family
- Distance from this BGC to the family representative
- "Novel Singleton" indicator if the BGC forms its own family

**Novelty Decomposition** — Three circular gauge charts (0–1 scale) breaking down the BGC's novelty into:
- **Sequence Novelty** — Proportion of protein sequences not found in validated BGCs
- **Chemistry Novelty** — Proportion of predicted compounds not matching known structures
- **Architecture Novelty** — Proportion of domain arrangements unique to this BGC

**Domain Architecture Differential** — A chart showing which protein domains in this BGC are core (present in most family members), variable (present in some), or rare/unique (not seen in the family). Helps identify what makes this BGC distinctive.

**Domain Architecture Comparison** — Side-by-side comparison of the domain architecture between this BGC and the nearest validated (MIBiG) BGC, showing shared and divergent regions.

**BGC Space Map** — Scatter plot showing GCF member BGCs plotted by novelty metrics. The evaluated BGC is highlighted, with family members and validated references shown for context.

**BGC Embeddings Map** — UMAP projection showing the evaluated BGC (as a star marker) among its nearest neighbours and validated reference points in embedding space.

---

## Shortlist Trays

Two independent shortlists persist across all modes, displayed in the sidebar below the filters:

### Assembly Shortlist
- Maximum capacity: **20 assemblies**
- Each entry shows: accession, organism name
- Actions: Download as CSV, Remove individual items, Clear all
- Visual highlight when Explore mode is active
- Adding a 21st item shows an error toast

### BGC Shortlist
- Maximum capacity: **20 BGCs**
- Each entry shows: accession (monospace)
- Actions: Download as GBK, Remove individual items, Clear all
- Visual highlight when Search mode is active

### How Shortlists Affect Panels

- **Explore mode**: If assemblies are shortlisted, the BGC panels show BGCs from all shortlisted assemblies (not just the selected one)
- **Search mode**: If BGCs are shortlisted, the Assembly panels show parent assemblies of all shortlisted BGCs
- Shortlists persist across browser sessions (stored in local storage)

---

## Scoring and Similarity

### BGC-Level Scores

| Score | Range | Meaning |
|-------|-------|---------|
| **Novelty Score** | 0.0–1.0 | Distance to the nearest validated (experimentally characterised) BGC in embedding space. Higher values indicate the BGC is more dissimilar from any known BGC. |
| **Domain Novelty** | 0.0–1.0 | Fraction of protein domains in this BGC that are unique (not shared with other BGCs in the database). Higher values indicate a more unusual domain architecture. |
| **Size** | kb | Length of the BGC genomic region in kilobases. |
| **Nearest Validated Distance** | 0.0–1.0 | The raw cosine distance to the closest validated BGC. Related to but distinct from Novelty Score. |

### Assembly-Level Scores

| Score | Range | Meaning |
|-------|-------|---------|
| **BGC Count** | integer | Total number of BGCs detected in the assembly. |
| **Diversity Score** | 0.0–1.0 | Normalised richness of biosynthetic class types (L1 classes) present. An assembly with BGCs spanning many different classes scores higher. |
| **Novelty Score** | 0.0–1.0 | Average novelty score across all BGCs in the assembly. |
| **Density** | float | BGC count per megabase of genome. Indicates how BGC-rich the organism is relative to its genome size. |
| **Taxonomic Novelty** | 0.0–1.0 | Reserved metric for organism-level taxonomic novelty. |

### Percentile Ranks (Evaluate Mode)

In the Evaluate Asset mode, assembly scores are contextualised as percentile ranks (0–100) against the full database:
- **Percentile Novelty** — What percentage of assemblies have a lower novelty score
- **Percentile Diversity** — What percentage of assemblies have a lower diversity score
- **Percentile Density** — What percentage of assemblies have a lower BGC density

Reference lines show the database mean and 90th percentile for comparison.

### Decomposed Novelty (BGC Evaluation)

When evaluating a single BGC, the novelty score is broken into three components:
- **Sequence Novelty** — Based on protein-level embedding distances
- **Chemistry Novelty** — Based on predicted natural product similarity
- **Architecture Novelty** — Based on domain arrangement uniqueness

### Query Similarity Score (Search Mode)

When searching, each result BGC receives a similarity score (0.0–1.0) computed by the active query method:
- **Domain search**: Fraction of query domains matched (Sorensen-Dice coefficient for set-level matching)
- **Sequence search**: Cosine similarity of embeddings or HMMER bit score (depending on selected method)
- **Chemical search**: Tanimoto similarity of Morgan fingerprints between query SMILES and BGC natural products

### Gene Cluster Family (GCF) Metrics

| Metric | Meaning |
|--------|---------|
| **Member Count** | Number of BGCs belonging to this family |
| **Validated Count** | Number of members that are experimentally characterised (from MIBiG) |
| **Mean Novelty** | Average novelty score across family members |
| **Known Chemistry** | Curated compound name (if the family maps to a known natural product) |

---

## Controlled Vocabularies and Ontologies

### BGC Classification (MIBiG Broad Classes)
BGCs are classified into broad biosynthetic classes following the MIBiG convention. Classifications are hierarchical (stored as dot-delimited paths), with a primary level and optional sub-types:
- **Polyketide** — Macrolide, Aromatic polyketide, Linear polyketide, etc.
- **NRP** — Cyclic peptide, Linear peptide, etc.
- **RiPP** — Lanthipeptide, Thiopeptide, Sactipeptide, etc.
- **Terpene** — Sesquiterpene, Diterpene, etc.
- **Saccharide** — Aminoglycoside, Oligosaccharide, etc.
- **Alkaloid** — Indole alkaloid, Pyrrolidine, etc.
- **Other** — Phosphonate, Aminocoumarin, etc.

### ChemOnt (Chemical Ontology)
Natural products predicted from BGCs are annotated with ChemOnt terms — a hierarchical chemical taxonomy with approximately 4,825 terms. Each annotation carries a probability score (0–1) indicating classification confidence. The ontology forms a tree from broad classes (e.g., "Organic compounds") down to specific compound families (e.g., "Macrolides and analogues").

ChemOnt terms are identified by IDs in the format `CHEMONTID:XXXXXXX` and are displayed as expandable trees in the filter sidebar and in BGC detail panels.

### Biome Ontology (GOLD Ecosystem Classification)
Assemblies are annotated with biome lineages from the GOLD Ecosystem Classification. Lineages are colon-delimited hierarchical paths, e.g.:
- `root:Environmental:Terrestrial:Soil`
- `root:Environmental:Aquatic:Marine`
- `root:Host-associated:Human:Digestive system`

### NCBI Taxonomy
Assemblies carry seven-rank NCBI taxonomic classifications: Kingdom, Phylum, Class, Order, Family, Genus, Species. The taxonomy filter in the sidebar presents these as an expandable tree with BGC counts at each node.

### Pfam Protein Domains
Protein domains within BGCs are annotated primarily with Pfam families (e.g., `PF00109` — Beta-ketoacyl synthase). Domains are used in:
- The Domain Query Builder (Search mode)
- Domain architecture diagrams (BGC Detail and Evaluate mode)
- Domain Novelty scoring

### Gene Cluster Families (GCF)
BGCs are clustered into Gene Cluster Families based on embedding similarity. Each family has a unique ID (e.g., `GCF_001`) and may have sub-family levels. Families are characterised by:
- A representative BGC (lowest novelty member)
- Member count and validated member count
- Known chemistry annotation (if mapped to characterised compounds)

### MIBiG Validated References
BGCs from the Minimum Information about a Biosynthetic Gene cluster (MIBiG) database are marked as **validated** — meaning they have been experimentally characterised. These serve as:
- Reference points for novelty scoring (every BGC's novelty is its distance to the nearest validated BGC)
- Landmarks in UMAP embeddings maps
- Ground truth for GCF family characterisation

---

## Cross-Mode Interactions

The three modes are interconnected. Users can navigate between them via action buttons in detail panels and context menus:

| Action | From | To | Effect |
|--------|------|----|--------|
| **Find Similar BGCs** | BGC Detail or BGC context menu | Search BGCs | Switches to Search mode and runs a similarity query using the selected BGC's embedding |
| **Evaluate Assembly** | Assembly Detail or context menu | Evaluate Asset | Switches to Evaluate mode and generates an assembly assessment report |
| **Evaluate BGC** | BGC Detail or context menu | Evaluate Asset | Switches to Evaluate mode and generates a BGC assessment report |
| **Browse Similar Assemblies** | Assembly Assessment view | Explore Assemblies | Finds assemblies similar to the evaluated one and loads them in Explore mode |
| **Find in Purchasable Strains** | BGC Assessment view | Search BGCs | Switches to Search mode to find the evaluated BGC in purchasable/type-strain assemblies |
| **Add to Shortlist** | Any detail panel or context menu | (stays in mode) | Adds the item to the relevant shortlist tray |

---

## Download and Export

### Shortlist Downloads
- **Assembly Shortlist** — Export as **CSV** containing accessions and metadata for all shortlisted assemblies
- **BGC Shortlist** — Export as **GBK** (GenBank format) containing annotated records for all shortlisted BGCs

### Statistics Export
From any Stats panel (Assembly Stats or BGC Stats), an export menu allows downloading:
- **JSON** — Machine-readable statistics
- **TSV** — Tab-separated values for spreadsheet use

### Assessment Export
After completing an evaluation in Evaluate mode, the full assessment report can be exported as **JSON**, capturing all scores, rankings, and comparison data.

### Single BGC Download
Individual BGCs can be downloaded in multiple formats:
- **GBK** (GenBank) — Full feature-annotated record including gene predictions, domain annotations, and BGC metadata
- **FNA** — Nucleotide FASTA sequence of the BGC region
- **FAA** — Protein FASTA sequences of all coding sequences within the BGC
- **JSON** — Structured metadata snapshot