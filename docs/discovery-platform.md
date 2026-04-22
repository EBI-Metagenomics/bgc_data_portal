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

## User Stories

### Explore Assemblies Mode

- I want to browse all assemblies ranked by how chemically novel and diverse their BGCs are, so I can identify the most promising candidates without a prior hypothesis.
- I want to filter to type strains only, so I only see organisms I can actually purchase.
- I want to filter by BGC class (enzymatic machinery) independently from ChemOnt class (product chemistry), so I can narrow to a specific research area without conflating the two.
- I want to filter metagenome assemblies by biome, so I can focus on BGCs from ecologically relevant environments.
- I want to click an assembly row and immediately see all its BGCs in a linked panel below, so I can assess its full biosynthetic repertoire at a glance.
- I want to shortlist multiple assemblies and see their combined BGC set in one view.
- I want to pin specific BGCs to a shortlist and export them as GenBank files ready for the lab.

### Search BGCs Mode

- I want to search by protein domain architecture (Pfam), so I can find all BGCs encoding a specific enzymatic function.
- I want to search by a chemical structure (SMILES), so I can find BGCs predicted to produce compounds structurally similar to one I am studying.
- I want to search by a protein or nucleotide sequence, so I can find BGCs related to a published or novel cluster.
- I want BGC results ranked by similarity to my query, so the most relevant hits appear first.
- I want to see which parent assemblies contain my result BGCs, so I can identify purchasable type strains that carry the chemistry I'm interested in.

### Evaluate Asset Mode

- I want to evaluate a database assembly and see how its scores rank against all other assemblies, so I can decide whether it is worth pursuing.
- I want to evaluate a database BGC and see which GCF it belongs to, its novelty decomposition, and the nearest known compound, so I can assess its research value.
- I want to upload my own assembly (as a .tar.gz file) and receive a structured assessment comparing it to the database, so I can decide whether to work with my strain or purchase an equivalent.
- I want to see a Redundancy Matrix for my assembly showing which of its BGCs are in novel GCFs vs. already covered by purchasable type strains.
- I want to upload my own BGC and see a domain architecture comparison with its nearest MIBiG relative, so I can identify what is novel about it.

---

## Mode 1: Explore Assemblies

### Purpose
Browse the full assembly catalogue — genomes, metagenomes, and regions — to identify assemblies worth pursuing, with no prior hypothesis required.

### When to Use
Use when starting a new screening campaign, exploring an unfamiliar taxonomic group or ecological niche, or when you want the database to surface promising candidates rather than confirming a specific hypothesis.

### Use Flow

1. Open the Discovery Platform. Click the **Explore Assemblies** tab.
2. Set filters in the sidebar as needed (all are optional):
   - **Type Strain only** — restricts to purchasable organisms. Enable this early if purchase is a hard requirement.
   - **Assembly Type** — choose Genome, Metagenome, or Region, or leave unset for all types.
   - **Taxonomy tree** — click any node to filter to that clade. Counts update in real time.
   - **BGC Class** — click a class button (Polyketide, NRP, RiPP, Terpene, Saccharide, Alkaloid, Other) to filter to assemblies containing at least one BGC of that type. Only one class active at a time.
   - **ChemOnt** — expand the tree to find a chemical class and click to filter. Independent of BGC Class.
   - **Biome Lineage** — type a GOLD path substring to filter metagenome assemblies by ecological origin.
   - **Organism Search** — type a name substring to filter by organism name.
3. Click **Run Query** to load results.
4. Review the **Assembly Roster** (top-left panel). Rows are assemblies matching your filters. Columns show Novelty, Diversity, Density, and BGC Count. Sort by any column.
5. Explore the **Assembly Space Map** (top-right). Each point is an assembly. Choose axes from Diversity, Novelty, Density, or Taxonomic Novelty. Points are coloured by dominant taxonomy. Click a point to select its assembly.
6. Click an assembly row (or point) to select it. The **BGC Roster** (bottom-left) populates with all BGCs from that assembly. The **Assembly Detail** panel appears below the assembly triad.
7. Optionally, shortlist multiple assemblies. The BGC panels then show the merged BGC set from all shortlisted assemblies, with a badge indicating the source count.
8. Review the **BGC Roster**. Sort by Novelty Score or Domain Novelty. Click a BGC row to open its **BGC Detail** panel, which shows the domain architecture, ChemOnt annotations, and nearest validated BGC.
9. Use the right-click context menu on any row to: **Add to Shortlist**, **Evaluate Assembly**, or **Evaluate BGC** / **Find Similar BGCs**.
10. Use the **Assembly Stats** and **BGC Stats** panels for summary charts. Export stats as JSON or TSV.
11. To export, use the shortlist trays at the bottom of the sidebar.

### Layout: The Triad System

Each mode is organised around **triads** — groups of three linked panels for one entity level. Explore Assemblies has two triads stacked vertically.

**Assembly Triad (top)**

*Assembly Roster* — Full-height table on the left. Columns: Organism name, Accession, Type Strain badge, BGC Count, Diversity Score, Novelty Score, Density. Sortable by all columns. Paginated. Click a row to select; right-click for context menu.

*Assembly Space Map* — Scatter plot (top right). Axes are user-configurable: Diversity, Novelty, Density, or Taxonomic Novelty. Points coloured by dominant taxonomy. Click a point to select the corresponding assembly row.

*Assembly Stats* — Summary charts (bottom right): taxonomy sunburst of the current result set, score distributions (histograms), type strain breakdown. Export as JSON or TSV.

**BGC Triad (bottom)**

Populated by: the currently selected assembly, OR the merged set from all shortlisted assemblies. A badge at the top of the triad indicates the source (e.g. "From 3 shortlisted assemblies").

*BGC Roster* — Table. Columns: Accession, Classification (BGC class path), Size (kb), Novelty Score, Domain Novelty, Nearest Validated BGC. Sortable. Click a row to select and open BGC Detail. Right-click: Add to Shortlist, Evaluate BGC, Find Similar BGCs.

*BGC Space Map* — Scatter plot, typically Novelty Score vs. Domain Novelty. Points coloured by BGC class. MIBiG validated BGCs shown as distinct markers for reference. Click a point to select.

*BGC Stats* — Summary charts: BGC class distribution, domain frequency bar chart, completeness breakdown, ChemOnt sunburst. Export as JSON or TSV.

### Detail Panels

**Assembly Detail** — Appears below the Assembly Triad when a row is selected. Shows: organism name, accession, type strain badge, score metrics as progress bars, links to external resources. Actions: Add to Shortlist, Evaluate Assembly.

**BGC Detail** — Appears below the BGC Triad when a row is selected. Shows: accession, full classification path (BGC class → sub-type), novelty score, domain novelty, distance to nearest validated BGC, **domain architecture diagram** (a region plot showing each gene's position and Pfam domain annotations as coloured blocks), natural products with their ChemOnt lineage annotations and probability scores. Actions: Add to Shortlist, Evaluate BGC, Find Similar BGCs.

---

## Mode 2: Search BGCs

### Purpose
Find specific BGCs using advanced query criteria — protein domain architecture, sequence similarity, or chemical structure similarity. Returns BGCs ranked by similarity score, with parent assemblies derived below.

### When to Use
Use when you have a chemical scaffold you want analogs of, a protein family you are tracking, a published BGC you want to find relatives of, or a Pfam domain combination you want to survey across the database.

### Layout

Search BGCs inverts the triad order: **BGC Triad is on top** (primary results), **Assembly Triad is on bottom** (parent assemblies of the result BGCs).

The sidebar has two tabs:
- **Filters** — All shared filters (Taxonomy, Biome, BGC Class, ChemOnt) plus direct accession lookups for Assembly Accession and BGC Accession (MGYB format).
- **Query** — Advanced search criteria (described below).

### Building a Query

Queries are built in the **Query tab** of the sidebar. Multiple query criteria can be combined; results are intersected. The **Run Query** button activates when at least one filter or query criterion is set. Status indicators in the sidebar show which criteria are active.

**Domain Query Builder**
Find BGCs by the Pfam protein domains they contain.
- Add one or more domain conditions by entering Pfam accessions (e.g. `PF00109`).
- Set domain logic: **AND** (all specified domains must be present) or **OR** (any domain matches).
- Useful for: finding all BGCs encoding a specific enzyme family, or finding PKS clusters with an unusual tailoring domain.
- Similarity score method: **Sorensen-Dice coefficient** on the set of matched domains.

**Sequence Search**
Find BGCs by sequence similarity to a query protein or nucleotide sequence.
- Paste a FASTA sequence in the input box.
- Select comparison scope: BGC-level or protein-level.
- Select similarity method: **HMMER** (profile hidden Markov model scoring, best for divergent homologs) or **embedding cosine similarity** (faster, better for close relatives).
- Set a similarity threshold (0–1).
- Runs asynchronously for large databases; results stream in as available.

**Chemical Structure Search (SMILES)**
Find BGCs whose predicted natural products are structurally similar to a query compound.
- Enter a SMILES string representing your compound of interest.
- Set a Tanimoto similarity threshold (default 0.85; lower values return more distant analogs).
- Matches by Morgan fingerprint similarity against all BGC-associated natural products.
- Useful for: finding potential producers of structural analogs of a known bioactive compound.

### Search Results

The **BGC Roster** in Search mode shows results ranked by **similarity score** (the primary column). Additional columns: Accession, Classification, Novelty Score, Domain Novelty, Size (kb). Sort by any column. Click a row to open the BGC Detail panel.

The **Assembly Triad** below is derived from the BGC results. It shows parent assemblies of: the selected BGC (if one is selected) or all shortlisted BGCs. This is the path from "matching BGCs" to "assemblies I can purchase." Apply the **Type Strain only** filter to immediately restrict to purchasable organisms.

### Similarity Score by Method

| Query method | Score meaning | Scale |
|---|---|---|
| Domain query | Sorensen-Dice coefficient: fraction of query domains matched vs. total domains in the union | 0–1 |
| Sequence (embedding) | Cosine similarity between query embedding and BGC embedding | 0–1 |
| Sequence (HMMER) | Normalised HMMER bit score | 0–1 |
| Chemical structure | Tanimoto similarity of Morgan fingerprints | 0–1 |

When multiple query methods are combined, results are intersected and the minimum score across active methods is shown.

---

## Mode 3: Evaluate Asset

### Purpose
Generate a comprehensive assessment report for a single assembly or BGC. Compare it against the full database to understand its novelty, GCF placement, and chemical space context. Works for both database entries (accessed by accession or via cross-mode actions) and externally uploaded files.

### When to Use
Use when: you want a detailed breakdown of a specific assembly's competitive position in the database; you want to understand a BGC's novelty from multiple angles; you have your own sequenced organism or cloned BGC and want to benchmark it against the database.

### Entering Evaluate Mode

Three entry points:
1. **From any roster or detail panel** — right-click a row and select "Evaluate Assembly" or "Evaluate BGC"; or click the "Evaluate" action button in a detail panel.
2. **Upload** — use the **Upload for Evaluation** panel in the sidebar. Accepts `.tar.gz` archives via drag-and-drop or file picker. Separate tabs for Single BGC and Assembly packages.
3. **Direct navigation** — select an asset by accession via the sidebar.

> **Important:** Uploaded assets are analysed ephemerally. They are never added to the database automatically.

### Assembly Assessment View

**Header** — Assembly accession, organism name, type strain badge. Actions: Add to Shortlist, Export JSON, Browse Similar Assemblies.

**Priority Ranking** — The assembly's absolute rank within the full database (e.g. "Rank 42 of 15,000"). Immediately answers: how does this assembly compare to everything else?

**Priority Score Radar** — A radar (spider) chart comparing the assembly's percentile scores across Diversity, Novelty, and Density against two reference rings: the database mean and the database 90th percentile. An assembly with scores outside the 90th percentile ring on multiple axes is an exceptional candidate.

**Score Percentile Distributions** — Gauge charts for each score dimension (Percentile Novelty, Percentile Diversity, Percentile Density). Reference lines mark the database mean and 90th percentile. Shows precisely where the assembly falls within the database distribution for each dimension independently.

**BGC Triad** — The standard BGC triad (Roster, Space Map, Stats) scoped to this assembly's BGCs. Same columns and interactions as in Explore mode.

**Redundancy Matrix** — A heatmap showing the breakdown of this assembly's BGCs across three categories:
- *Novel GCF* — BGC belongs to a gene cluster family not seen elsewhere in the database. Highest priority for experimental follow-up.
- *Known GCF, no type strain* — The GCF has database members, but none are type strains available for purchase. Moderate priority.
- *Known GCF, type strain available* — The chemistry represented by this BGC is already accessible via a purchasable type strain. Lower priority for this BGC specifically.

Reading the Redundancy Matrix: an assembly where most BGCs fall in the "Novel GCF" column is a strong candidate for experimental work. An assembly where most BGCs are in the "Known GCF, type strain available" column offers little advantage over purchasing an existing reference strain.

**BGC Embeddings Map** — A UMAP projection showing this assembly's BGCs positioned in the global embedding space. Validated (MIBiG) reference BGCs are shown as labelled landmarks. Summary statistics show: mean distance to nearest validated BGC (lower = chemistry is closer to known compounds) and sparse fraction (proportion of BGCs in low-density embedding regions, a measure of overall novelty).

### BGC Assessment View

**Header** — BGC accession, full classification path, Novel Singleton badge (if applicable). Actions: Add to Shortlist, Export JSON, Find in Purchasable Strains.

**GCF Placement** — The primary contextual result. Shows:
- *Family ID* and known chemistry annotation (compound name, if the family maps to a characterised natural product)
- *Member count* — how many BGCs in the database share this family
- *Validated count* — how many of those members are MIBiG-characterised
- *Mean novelty* — average novelty score across family members
- *Distance to representative* — how similar this BGC is to its family's representative (lower = more typical member; higher = outlier within its family)
- *Novel Singleton indicator* — shown prominently if the BGC does not cluster with any other BGC

A large family (many members) with zero validated members is a widespread, entirely uncharacterised biosynthetic strategy — one of the most compelling research targets on the platform.

**Novelty Decomposition** — Three circular gauge charts breaking down the BGC's novelty score into independent components:
- *Sequence Novelty* — based on protein-level embedding distances. High = protein sequences are unlike those in validated BGCs.
- *Chemistry Novelty* — based on predicted natural product similarity to known compounds. High = predicted chemistry has no known structural analog.
- *Architecture Novelty* — based on domain arrangement uniqueness. High = the specific combination and order of protein domains is unusual.

These three axes can diverge in informative ways. A BGC with high Sequence Novelty but low Architecture Novelty uses familiar enzymatic logic in a new sequence context — the product may be a variant of a known compound. A BGC with high Architecture Novelty but moderate Sequence Novelty has unusual domain combinations — the product chemistry may be genuinely unprecedented.

**Domain Architecture Differential** — A chart showing which protein domains in this BGC are:
- *Core* — present in most GCF family members; defines the shared enzymatic logic of the family
- *Variable* — present in some family members; may explain chemical variation within the family
- *Rare / Unique* — not seen in the rest of the family; distinguishes this BGC and is a candidate for structural novelty

**Domain Architecture Comparison** — Side-by-side domain map comparing this BGC (top) to its nearest validated (MIBiG) BGC (bottom). Shared domain regions are aligned; divergent regions are visually apparent. This is the most direct answer to "what makes my BGC different from the nearest known cluster?"

**BGC Space Map** — Scatter plot showing GCF member BGCs plotted by novelty metrics. The evaluated BGC is highlighted; family members and validated references provide context.

**BGC Embeddings Map** — UMAP projection with the evaluated BGC marked as a star (★) among its nearest embedding neighbours and validated reference landmarks.

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