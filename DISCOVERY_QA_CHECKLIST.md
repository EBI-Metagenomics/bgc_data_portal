# Discovery Platform — Manual QA Checklist

Manual verification checklist for the v2 iBGC-first Discovery dashboard.
Work top to bottom; each item is something to click/trigger and confirm it behaves.

- **Dashboard:** `/dashboard/discovery`
- **Report:** `/report?token=…`

---

## API smoke-test results — `kind-bgc-local` (2026-06-03)

Endpoints exercised directly against the running django pod (`bgc-local` ns,
7269 iBGCs / 2624 validated / 219 genomes seeded). UI rendering/interactions
NOT covered — browser-only items still need a manual click-through.

### ✅ Working (HTTP 200, sane payload)
- `/stats/`, `/stats/assemblies/` (+ TSV export)
- All 8 filter facets (taxonomy, bgc-classes, np-classes, chemont, domains, gcfs, sources, detectors)
- iBGC roster / count / ids; iBGC detail; iBGC region
- Assemblies list + detail; accession resolve
- **UMAP map** (`/ibgcs/umap/`); assembly-scatter
- **Domain search (iBGC)** (`/query/ibgc-domain/`)
- **Sequence search** — dispatch 202 + iBGC-level poll (`/query/ibgc-sequence/status/`)
- **Report** — snapshot, GET, all 3 exports (json / assemblies.tsv / gbk.zip); payload carries every plot key

### ✅ FIXED (2026-06-03) — verified 200 in `kind-bgc-local`
- **Variables map tab** — `/ibgcs/scatter/` was 500: annotation `size_kb` collided with the read-only `IntegratedBgc.size_kb` property. Fixed by annotating under `_size_kb` and mapping the axis name (`api.py` ~2017). Now 200 on every axis.
- **Copy domain architecture** — `/ibgcs/{id}/architecture/` was 500: endpoint passed a *list* of member-prediction ids to `ibgc_architecture()`, which takes a single iBGC id. Fixed to call `ibgc_architecture(ibgc_id)` directly. Now returns `ordered_accs`.

### ✅ FIXED (2026-06-03) — single-BGC download, verified 200 in `kind-bgc-local`
- **Single-BGC download** `/bgcs/{id}/download/?format=gbk|fna|faa|json` was 500: it prefetched a `cds_list` relation gone from `SourceBgcPrediction` and imported four deleted BGC-level builders. Rewritten to resolve the prediction's **parent iBGC** and delegate to the iBGC builders (`build_ibgc_genbank_record` / `build_ibgc_fna|faa|json` — previously dormant). All four formats now return 200 with the canonical iBGC record; filename = iBGC accession. Partials with NULL `integrated_bgc` → 404; bad format → 400.

### ✅ RETIRED (2026-06-03) — legacy BGC-level surface removed end-to-end (P1.4b)
The legacy per-prediction (`BgcRoster`/`BgcScatter`) surface was first fixed, then fully
retired once confirmed to be orphaned dead code. Verified in `kind-bgc-local`: every dead
route returns **404**, every live route **200**; frontend `tsc --noEmit` and backend
`py_compile` both green; no test/e2e spec references a removed symbol or route.

**Frontend deleted (29 files):** `DashboardShell`, `panels/{QueryLayout,PanelContainer,PlatformStats}`,
`bgc/{BgcDetail,BgcRoster,BgcScatter,BgcStats,BgcContextMenu,DomainArchitecture}`, all of `components/query/*`,
the dead hooks (`use-bgc-{detail,region,roster,scatter,stats}`, `use-parent-assemblies`,
`use-similar-bgc-query`, `use-query-assembly-{roster,scatter}`, `use-{sequence,domain,chemical}-query`,
`use-assembly-aggregation`), and `api/bgcs.ts` (+ barrel re-export, + dead `exportBgcStats`).
**Kept (live):** `RegionPlot`, `CdsProteinInfo`, `goSlimPalette`, `api/queries.ts`, `query-store`.

**Backend deleted (api.py −824 lines, api_schemas.py −51):** endpoints `assembly_bgc_roster`,
`bgc_roster`, `bgc_detail`, `bgc_region` (+`_build_bgc_region_data`), `bgc_scatter`,
`bgc_parent_assemblies`, `domain_query`, `sequence_query_status`, `bgc_stats` (+export);
orphaned helpers `_apply_bgc_filters`, `_bgc_roster_item`, `_query_result_bgc`, `_ibgc_qs_from_bgc_filters`;
15 now-unused imports; 5 dead schema classes (`BgcRosterItem`, `PaginatedBgcRosterResponse`,
`BgcDetail`, `BgcScatterPoint`, `SequenceQueryStatusResponse`).
**Kept (live):** `download_bgc` (`/bgcs/{id}/download/`), `/query/sequence/` POST + `/query/ibgc-sequence/status/`,
`/query/ibgc-domain/`, `/query/chemical/` (P1.5b), all iBGC endpoints.

**Remaining harmless dead internals (optional follow-up):** `compute_bgc_stats` (services/stats.py)
and `bgc_architecture` (services/architecture.py) are now unreferenced but left in place (entangled
helper graph / standalone); safe to drop later.

### ⚠️ BLOCKED — deployment/data state, not code (missing mounted assets)
- **Find similar iBGCs** + **ARCH architecture search** — 503: `Scoring cache not present … /data/clustering_artifacts/f7ebd0d42b63/scoring_cache`. Needs clustering artifacts on the PVC for the active run sha.
- **Chemical structure search** — 500: `FileNotFoundError: /data/chemont/ChemOnt_2_1.obo` missing.

### ❓ Not verifiable via API — needs manual browser pass
Welcome modal, guided tour, plot halos/hover/click interactions, context menus, toasts, region-plot CDS selection, drag/zoom, status badges, root `/` landing page.

---

## 1. Landing / Dashboard load

- [ ] Dashboard loads at `/dashboard/discovery` with no console errors
- [ ] Welcome modal appears (first visit) and can be dismissed
- [ ] Guided tour launches and steps through the tagged controls
- [ ] DB stats badges render with real counts: **Validated**, **Integrated**, **Predicted**, **Genomes**, **Metagenomes**
- [ ] Result-scope banner shows the matching iBGC count
- [ ] Layout renders: results card (left) + Reference / Compare detail slots + Protein panel (right)

---

## 2. Filters (FilterPanel + TopFiltersStrip)

Each: apply it, confirm **Run Query** updates roster/maps/count, then **Reset/Clear**.

- [ ] **Source** — searchable dropdown, count badges, add/remove
- [ ] **Detector** — searchable dropdown with counts
- [ ] **Assembly Type** — All / Metagenome / Genome / Region
- [ ] **BGC Class** — searchable single-select
- [ ] **GCF** — path-based searchable filter with level badges
- [ ] **Taxonomy** — hierarchical tree (kingdom→genus) + live search; selecting ancestor cancels descendants
- [ ] **Biome Lineage** — hierarchy path text input (e.g. `root:Environmental:Soil`)
- [ ] **ChemOnt Class** — hierarchical checkbox tree with expand
- [ ] **Natural Product Class** — hierarchical checkboxes (L1/L2/L3)
- [ ] **Accessions** — Assembly accession (ERZ) + BGC accession (MGYB) inputs
- [ ] **Length** — min/max kb (auto-swaps if inverted)
- [ ] **Novelty / Domain-novelty ranges** apply correctly
- [ ] **Run Query** — disabled + spinner while running
- [ ] **Reset** — clears all filters and restores full scope
- [ ] **Context-aware Clear** button label matches active search type
- [ ] Filter count badges on chips reflect active selections
- [ ] Over-cap warning banner appears when matches exceed the cap (deterministic sample note)

---

## 3. Search

- [ ] **Sequence search** — paste protein (FASTA/raw); AA counter; warns >5000 AA
  - [ ] Sliders: min bitscore, min % identity, min query coverage
  - [ ] Returns async (202 → polling); roster shows **Bitscore** + **Best hit** columns
  - [ ] Bitscore axis becomes available in Variables map
- [ ] **Domain query builder**
  - [ ] **AND** mode — all selected domains
  - [ ] **OR** mode — any selected domain
  - [ ] **ARCH** mode — comma-separated accessions + Adjacency/Dice weight slider
  - [ ] req/excl toggle on domain badges works
- [ ] **Chemical structure search** — SMILES + Tanimoto slider (0.1–1.0); intersects with filters
- [ ] **Find similar iBGCs** (right-click) — top-100 by composite-Dice; sorts by similarity; toast with count
  - [ ] Disabled for partial iBGCs and submitted assets (correct hint shown)
- [ ] **Accession resolve** — MGYB / MGYB-NN accession routes to the right iBGC/cBGC

---

## 4. iBGC Roster Table

- [ ] Columns render: iBGC, Size (kb), Novelty, Domain novelty, Sources, Assembly
- [ ] Dynamic columns appear during sequence search (Similarity/Bitscore, Best hit)
- [ ] Status badges: **Validated** (blue), **Type Strain** (teal), **Partial** (amber outline), **SUBMITTED** (amber)
- [ ] Column sorting: novelty, domain novelty, size, similarity — asc/desc indicators
- [ ] Default sort = novelty desc (or similarity desc when Find Similar active)
- [ ] Pagination: 50/page, Prev/Next, page N/M, total count
- [ ] **Left-click row** → loads into Compare detail slot (accent highlight)
- [ ] **Right-click row** → context menu
- [ ] Asset rows render with amber background
- [ ] **Add all to shortlist** button (with spinner state)
- [ ] Empty states: no scope, loading, error ("Failed to load iBGCs"), "No iBGCs found"

---

## 5. Maps / Visualisations

### UMAP tab
- [ ] Plotly scatter renders; X/Y = UMAP 1/2
- [ ] Colour = GCF group; shapes = status (circle/square=type strain/diamond=validated/star=asset)
- [ ] Halos: selected (black ring), reference (amber ring)
- [ ] Hover tooltip: label, classification path, novelty, domain novelty, similarity
- [ ] Left-click → Compare slot; right-click → context menu
- [ ] Pan/zoom; mode bar "save as PNG" works
- [ ] Empty/loading/error states

### Variables map tab
- [ ] X/Y axis dropdowns: Novelty, Domain novelty, Size, # CDS (+ query axes when active)
- [ ] Query axes (Bitscore/Dice/similarity, Identity %, Query coverage %) populate after a query
- [ ] "Run a query to populate this axis" warning when no query
- [ ] Same shapes/halos/interactions as UMAP

---

## 6. Detail Views

- [ ] **Reference slot** — pinned via right-click "Set as reference"; amber border, REFERENCE badge
- [ ] **Compare slot** — set via left-click; COMPARE badge
- [ ] Instruction placeholders show when slots empty
- [ ] Header: label, parent cBGC accession (tooltip), status badges, kebab menu
- [ ] KPI strip chips: Assembly (linked), Completeness, GCF (click→filter), Novelty, Domain novelty, Compound features (→MolView, tooltip with curated compounds + CHAMOIS classes)
- [ ] Contig/location box: contig, start–end, size kb, source tools, member count
- [ ] **Region plot** — CDS features render; clicking a CDS updates Protein panel
- [ ] Member BGCs strip: up to 6 badges + "+N more"
- [ ] **Protein Information Panel** — auto-expands on CDS click; Pfam annotations; collapse/expand; flash highlight; empty state

---

## 7. Context Menu / Row Actions

- [ ] **Set as reference iBGC** (disabled if already reference)
- [ ] **Find similar iBGCs** (disabled for partial / asset)
- [ ] **Copy domain architecture** → clipboard, comma-separated Pfam/NCBIFAM; toast with count
- [ ] **Add to shortlist** (respects cap; toast)
- [ ] **Clear shortlist & add** → replaces shortlist with single iBGC

---

## 8. Shortlist

- [ ] Shortlist dropdown shows count badge
- [ ] Items list with remove (X) buttons
- [ ] **Clear All** (destructive)
- [ ] Cap warning toast when at MAX_SHORTLIST
- [ ] Empty state message
- [ ] **Generate Report** opens `/report?token=…` in new tab (spinner; disabled when empty)
- [ ] Report generates correctly when shortlist contains uploaded-asset iBGCs (asset_token)

---

## 9. Report Page (`/report?token=…`)

- [ ] Header: title + "X iBGCs · Y assemblies"
- [ ] **iBGC results table**: iBGC, Assembly, Organism, Phylum, Biome, Size, Novelty, Dom. nov., GCF, Sources + status badges
- [ ] Report is shareable/reload-safe via token (within TTL)

### Report plots
- [ ] **Domain composition** — stacked bar (Core/Variable/Rare) + table with tiers
- [ ] **Domain × GO-slim heatmap** — tiers × GO categories, hover tooltip
- [ ] **GCF distribution** — top-20 horizontal bar
- [ ] **Score distributions** — novelty / domain-novelty histogram overlay
- [ ] **Completeness** — pie (complete/partial)
- [ ] **BGC classes** — pie
- [ ] **Length distribution** — histogram
- [ ] **Predictor distribution** — bar
- [ ] **Source distribution** — horizontal bar
- [ ] **Taxonomy sunburst** — interactive drill-down (kingdom→genus)
- [ ] **Assembly roster table**: Accession, Organism, Phylum, Biome, Source, Size (Mb), BGCs, iBGCs
- [ ] **Assembly stats**: biome distribution bar + source pie

---

## 10. Export / Download

### Report page
- [ ] **Export JSON** → `/report/{token}/export.json`
- [ ] **Export GBKs (zip)** → `/report/{token}/export.gbk.zip` (one GBK per source BGC)
- [ ] **Export Assemblies (TSV)** → `/report/{token}/export.assemblies.tsv`

### Single BGC
- [ ] BGC download in **gbk / fna / faa / json** formats (`/bgcs/{id}/download/?format=…`)

### Shortlist export (API)
- [ ] Assembly shortlist export → CSV
- [ ] BGC shortlist export → multi-record GBK (max 20)

### Stats export
- [ ] BGC stats export (JSON / TSV)
- [ ] Assembly stats export (JSON / TSV)

### Copy
- [ ] Copy domain architecture → clipboard

---

## 11. Asset Upload (uploaded BGC sets)

- [ ] Upload tarball (≤5 MB gz) → 202 with token + task_id
- [ ] Poll status → SUCCESS; asset iBGCs appear in roster/UMAP/scatter
- [ ] Asset iBGCs marked SUBMITTED, bypass filters ("always shown")
- [ ] X-click evicts asset (204); rows disappear
- [ ] Asset iBGCs survive into report when asset_token supplied

---

## 12. Cross-cutting

- [ ] No `NaN` JSON-parse errors in any numeric panel (known footgun)
- [ ] Over-cap sampling is deterministic (same sample on reload)
- [ ] All toasts (success/error/warning/loading/info) render correctly
- [ ] Loading spinners appear on every async action
- [ ] Root landing page `/` renders (NOT covered by e2e — verify manually)
