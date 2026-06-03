# Discovery Platform — Manual QA Checklist

Manual verification checklist for the v2 iBGC-first Discovery dashboard.
Work top to bottom; each item is something to click/trigger and confirm it behaves.

- **Dashboard:** `/dashboard/discovery`
- **Report:** `/report?token=…`

> **QA pass — 2026-06-03 (code-level verification).** Each item was verified by
> reading the implementing code (components, stores, API routes, services) rather
> than by live browser clicking; the second checkbox is ticked where the
> implementation is present and correct. **9 items failed** — see the `> ⚠ FAIL`
> notes inline. A handful of passing items carry a `> note` caveat worth knowing.

---


## 1. Landing / Dashboard load

- [ ] [x] Dashboard loads at `/dashboard/discovery` with no console errors
- [ ] [x] Welcome modal appears (first visit) and can be dismissed
- [ ] [ ] Guided tour launches and steps through the tagged controls
  > ⚠ FAIL: `tour-steps.ts` anchors step 1 to `[data-tour="sidebar"]` (Sidebar.tsx)
  > and step 3 to `[data-tour="shortlist-trays"]` (SidebarShortlists.tsx). Both legacy
  > components are mounted nowhere in the v2 dashboard (grep finds no `<Sidebar>` /
  > `SidebarShortlists` usage), so only the middle `run-query` step anchors. Re-tag the
  > v2 equivalents (filter strip + `ShortlistDropdown`) or update the selectors.
- [ ] [x] DB stats badges render with real counts: **Validated**, **Integrated**, **Predicted**, **Genomes**, **Metagenomes**
- [ ] [x] Result-scope banner shows the matching iBGC count
- [ ] [x] Layout renders: results card (left) + Reference / Compare detail slots + Protein panel (right)

---

## 2. Filters (FilterPanel + TopFiltersStrip)

Each: apply it, confirm **Run Query** updates roster/maps/count, then **Reset/Clear**.

- [ ] [x] **Source** — searchable dropdown, count badges, add/remove
- [ ] [x] **Detector** — searchable dropdown with counts
- [ ] [x] **Assembly Type** — All / Metagenome / Genome / Region
- [ ] [x] **BGC Class** — searchable single-select
- [ ] [x] **GCF** — path-based searchable filter with level badges
- [ ] [x] **Taxonomy** — hierarchical tree (kingdom→genus) + live search; selecting ancestor cancels descendants
- [ ] [x] **Biome Lineage** — hierarchy path text input (e.g. `root:Environmental:Soil`)
- [ ] [x] **ChemOnt Class** — hierarchical checkbox tree with expand
- [ ] [ ] **Natural Product Class** — hierarchical checkboxes (L1/L2/L3)
  > ⚠ FAIL: `NpClassFilter.tsx` is fully implemented and store-backed, but is never
  > imported into `FilterPanel.tsx` (no import anywhere in src). `appliedFiltersToApiParams`
  > / `snapshotFiltersToApplied` also drop the NP fields, so even if rendered it would not
  > reach the query. The filter is absent from the UI.
- [ ] [x] **Accessions** — Assembly accession (ERZ) + BGC accession (MGYB) inputs
- [ ] [x] **Length** — min/max kb (auto-swaps if inverted)
- [ ] [ ] **Novelty / Domain-novelty ranges** apply correctly
  > ⚠ FAIL: No UI control or store field exists. `filter-store.ts` has no novelty fields;
  > `AppliedIbgcFilters` omits them; nothing emits `min_novelty` / `max_novelty` /
  > `min_domain_novelty` / `max_domain_novelty`. Those params exist only as unused optional
  > types in `api/ibgcs.ts` — never populated.
- [ ] [x] **Run Query** — disabled + spinner while running
- [ ] [ ] **Reset** — clears all filters and restores full scope
  > ⚠ FAIL: `FilterPanel.tsx` Reset calls only `clearFilters` (chip state). It does not
  > call `clearSelections`, so the applied scope (`appliedFilters` / `resultIbgcIds`) driving
  > the roster + maps persists after Reset; full scope is only restored on the next Run Query.
  > Chips clear, but scope restoration is not immediate.
- [ ] [x] **Context-aware Clear** button label matches active search type
  > note: the `similar_ibgc` and `chemical` label branches are currently unreachable (the
  > run hook only sets sequence/domain/architecture); active paths are correct.
- [ ] [x] Filter count badges on chips reflect active selections
- [ ] [x] Over-cap warning banner appears when matches exceed the cap (deterministic sample note)

---

## 3. Search

- [ ] [x] **Sequence search** — paste protein (FASTA/raw); AA counter; warns >5000 AA
  - [ ] [x] Sliders: min bitscore, min % identity, min query coverage
  - [ ] [x] Returns async (202 → polling); roster shows **Bitscore** + **Best hit** columns
  - [ ] [x] Bitscore axis becomes available in Variables map
- [ ] [x] **Domain query builder**
  - [ ] [x] **AND** mode — all selected domains
  - [ ] [x] **OR** mode — any selected domain
  - [ ] [x] **ARCH** mode — comma-separated accessions + Adjacency/Dice weight slider
  - [ ] [x] req/excl toggle on domain badges works
- [ ] [ ] **Chemical structure search** — SMILES + Tanimoto slider (0.1–1.0); intersects with filters
  > ⚠ FAIL: UI (`ChemicalStructureSearch`) and backend `/query/chemical/` both exist, but
  > `useRunIbgcQuery` has no chemical branch and `postChemicalQuery` has zero callers — the
  > hook comment confirms "the chemical query path is not surfaced in v2 yet" (P1.5b follow-up).
  > Pressing Run Query with only a SMILES string runs filters-only and never intersects.
- [ ] [x] **Find similar iBGCs** (right-click) — top-100 by composite-Dice; sorts by similarity; toast with count
  - [ ] [x] Disabled for partial iBGCs and submitted assets (correct hint shown)
- [ ] [x] **Accession resolve** — MGYB / MGYB-NN accession routes to the right iBGC/cBGC

---

## 4. iBGC Roster Table

- [ ] [x] Columns render: iBGC, Size (kb), Novelty, Domain novelty, Sources, Assembly
- [ ] [x] Dynamic columns appear during sequence search (Similarity/Bitscore, Best hit)
- [ ] [x] Status badges: **Validated** (blue), **Type Strain** (teal), **Partial** (amber outline), **SUBMITTED** (amber)
- [ ] [x] Column sorting: novelty, domain novelty, size, similarity — asc/desc indicators
- [ ] [x] Default sort = novelty desc (or similarity desc when Find Similar active)
- [ ] [x] Pagination: 50/page, Prev/Next, page N/M, total count
- [ ] [x] **Left-click row** → loads into Compare detail slot (accent highlight)
- [ ] [x] **Right-click row** → context menu
- [ ] [x] Asset rows render with amber background
- [ ] [x] **Add all to shortlist** button (with spinner state)
- [ ] [x] Empty states: no scope, loading, error ("Failed to load iBGCs"), "No iBGCs found"

---

## 5. Maps / Visualisations

### UMAP tab
- [ ] [x] Plotly scatter renders; X/Y = UMAP 1/2
- [ ] [x] Colour = GCF group; shapes = status (circle/square=type strain/diamond=validated/star=asset)
- [ ] [x] Halos: selected (black ring), reference (amber ring)
- [ ] [ ] Hover tooltip: label, classification path, novelty, domain novelty, similarity
  > ⚠ FAIL: `baseHover` builds all five fields, but UMAP points never carry `domain_novelty`
  > — `IbgcUmapPoint` (api_schemas.py) omits it and `UmapMapTab` doesn't map it, so domain
  > novelty never renders in the UMAP hover (it works on the Variables tab only).
- [ ] [ ] Left-click → Compare slot; right-click → context menu
  > ⚠ FAIL: Left-click → Compare works. Right-click is dead: `CtxMenuOverlay` renders the
  > ContextMenuTrigger inside a `pointer-events-none absolute inset-0` div, so it can never
  > receive the right-click (code comments admit it's a stopgap). Users must right-click the
  > roster row instead. Affects both map tabs.
- [ ] [x] Pan/zoom; mode bar "save as PNG" works
- [ ] [x] Empty/loading/error states

### Variables map tab
- [ ] [x] X/Y axis dropdowns: Novelty, Domain novelty, Size, # CDS (+ query axes when active)
- [ ] [x] Query axes (Bitscore/Dice/similarity, Identity %, Query coverage %) populate after a query
- [ ] [x] "Run a query to populate this axis" warning when no query
- [ ] [x] Same shapes/halos/interactions as UMAP
  > note: shapes/halos/left-click mirror UMAP correctly; the broken map right-click (see UMAP
  > above) is inherited here too.

---

## 6. Detail Views

- [ ] [x] **Reference slot** — pinned via right-click "Set as reference"; amber border, REFERENCE badge
  > note: border/badge use theme-`primary` token and badge text is CSS-uppercased "Reference",
  > not a hardcoded amber/"REFERENCE" string — functionally correct, cosmetically near-spec.
- [ ] [x] **Compare slot** — set via left-click; COMPARE badge
- [ ] [x] Instruction placeholders show when slots empty
- [ ] [x] Header: label, parent cBGC accession (tooltip), status badges, kebab menu
- [ ] [x] KPI strip chips: Assembly (linked), Completeness, GCF (click→filter), Novelty, Domain novelty, Compound features (→MolView, tooltip with curated compounds + CHAMOIS classes)
- [ ] [x] Contig/location box: contig, start–end, size kb, source tools, member count
- [ ] [x] **Region plot** — CDS features render; clicking a CDS updates Protein panel
- [ ] [x] Member BGCs strip: up to 6 badges + "+N more"
- [ ] [x] **Protein Information Panel** — auto-expands on CDS click; Pfam annotations; collapse/expand; flash highlight; empty state
  > note: auto-expand, collapse/expand, flash (900 ms ring) and empty state all work, but the
  > annotation table renders **InterPro** entries (`cds.interpro`), while the empty-state text
  > says "Pfam annotations" — label inconsistency. Raw Pfam is only used in the RegionPlot hover.

---

## 7. Context Menu / Row Actions

- [ ] [x] **Set as reference iBGC** (disabled if already reference)
- [ ] [x] **Find similar iBGCs** (disabled for partial / asset)
- [ ] [x] **Copy domain architecture** → clipboard, comma-separated Pfam/NCBIFAM; toast with count
- [ ] [x] **Add to shortlist** (respects cap; toast)
- [ ] [x] **Clear shortlist & add** → replaces shortlist with single iBGC

---

## 8. Shortlist

- [ ] [x] Shortlist dropdown shows count badge
- [ ] [x] Items list with remove (X) buttons
- [ ] [x] **Clear All** (destructive)
- [ ] [x] Cap warning toast when at MAX_SHORTLIST
- [ ] [x] Empty state message
- [ ] [x] **Generate Report** opens `/report?token=…` in new tab (spinner; disabled when empty)
- [ ] [x] Report generates correctly when shortlist contains uploaded-asset iBGCs (asset_token)

---

## 9. Report Page (`/report?token=…`)

- [ ] [x] Header: title + "X iBGCs · Y assemblies"
- [ ] [x] **iBGC results table**: iBGC, Assembly, Organism, Phylum, Biome, Size, Novelty, Dom. nov., GCF, Sources + status badges
- [ ] [x] Report is shareable/reload-safe via token (within TTL)

### Report plots
- [ ] [x] **Domain composition** — stacked bar (Core/Variable/Rare) + table with tiers
- [ ] [x] **Domain × GO-slim heatmap** — tiers × GO categories, hover tooltip
- [ ] [x] **GCF distribution** — top-20 horizontal bar
- [ ] [x] **Score distributions** — novelty / domain-novelty histogram overlay
- [ ] [x] **Completeness** — pie (complete/partial)
- [ ] [x] **BGC classes** — pie
- [ ] [x] **Length distribution** — histogram
- [ ] [x] **Predictor distribution** — bar
- [ ] [x] **Source distribution** — horizontal bar
- [ ] [x] **Taxonomy sunburst** — interactive drill-down (kingdom→genus)
- [ ] [x] **Assembly roster table**: Accession, Organism, Phylum, Biome, Source, Size (Mb), BGCs, iBGCs
- [ ] [x] **Assembly stats**: biome distribution bar + source pie

---

## 10. Export / Download

### Report page
- [ ] [x] **Export JSON** → `/report/{token}/export.json`
- [ ] [x] **Export GBKs (zip)** → `/report/{token}/export.gbk.zip` (one GBK per source BGC)
  > note: produces one GBK per iBGC (each embedding its source-BGC features), not literally one
  > file per source BGC — doc-only nuance, functionally correct.
- [ ] [x] **Export Assemblies (TSV)** → `/report/{token}/export.assemblies.tsv`

### Single BGC
- [ ] [x] BGC download in **gbk / fna / faa / json** formats (`/bgcs/{id}/download/?format=…`)

### Shortlist export (API)
- [ ] [x] Assembly shortlist export → CSV
- [ ] [ ] BGC shortlist export → multi-record GBK (max 20)
  > ⚠ FAIL: `api.py:3232` imports `build_multi_bgc_gbk`, but `gbk.py:273` defines
  > `build_multi_ibgc_gbk` — name mismatch raises `ImportError` at request time, so the endpoint
  > 500s. The max-20 cap (`api.py:3229`) is correct. One-word fix: rename the import/call.

### Stats export
- [ ] [ ] BGC stats export (JSON / TSV)
  > ⚠ FAIL: `compute_bgc_stats` exists (`stats.py:151`) but has no API endpoint and no live UI
  > export — it is only rendered as a non-exportable report section. No `/stats/bgc*` route and
  > no `exportBgcStats` in the frontend (the Assembly variant ships; the BGC one is dead-ended).
- [ ] [x] Assembly stats export (JSON / TSV)

### Copy
- [ ] [x] Copy domain architecture → clipboard

---

## 11. Asset Upload (uploaded BGC sets)

- [ ] [x] Upload tarball (≤5 MB gz) → 202 with token + task_id
- [ ] [x] Poll status → SUCCESS; asset iBGCs appear in roster/UMAP/scatter
- [ ] [x] Asset iBGCs marked SUBMITTED, bypass filters ("always shown")
- [ ] [x] X-click evicts asset (204); rows disappear
- [ ] [x] Asset iBGCs survive into report when asset_token supplied

---

## 12. Cross-cutting

- [ ] [x] No `NaN` JSON-parse errors in any numeric panel (known footgun)
- [ ] [x] Over-cap sampling is deterministic (same sample on reload)
  > note: the map over-cap path is deterministic (SQL `id % stride` ordered by id). Stats
  > boxplots use an unseeded `random.sample` (`stats.py:38`) — not the map path, but add a fixed
  > seed if strict reload-determinism is wanted there too.
- [ ] [x] All toasts (success/error/warning/loading/info) render correctly
- [ ] [x] Loading spinners appear on every async action
- [ ] [x] Root landing page `/` renders (NOT covered by e2e — verify manually)
