# BGC Data Portal: Comprehensive Data Flow Map

Reference map of how data stored in Django ORM models (`models.py`) flows
through transformations to reach the API endpoints (`api.py`), the web templates
(`bgc_data_portal/templates/`), and the download responses.
Intended as a change-guide: find any output field and trace it back to its DB source.

---

## 1. Model Layer (Source of Truth)

| Model | Key Fields | Notes |
|-------|-----------|-------|
| `Study` | id, accession | Parent of Assembly |
| `Biome` | id, lineage | Parent of Assembly |
| `Assembly` | id, accession, collection, study→Study, biome→Biome | — |
| `Contig` | id, sequence_sha256, mgyc, accession, assembly→Assembly, name, source_organism, length, sequence | Full nt sequence stored here |
| `Bgc` | id, contig→Contig, detector→BgcDetector, identifier, start_position, end_position, metadata (JSON: umap_x_coord, umap_y_coord, detectors, aggregated_region_ids), is_partial, classes↔BgcClass (M2M), embedding (pgvector 1152-d), is_aggregated_region, compounds (list of dicts), smiles_svg | Accession computed: `MGYB{id:012}` |
| `BgcClass` | id, name | e.g. "Polyketide", "NRP" |
| `BgcDetector` | id, name, tool, version | e.g. "antiSMASH", "GECCO", "SanntiS" |
| `Protein` | id, sequence, sequence_sha256, mgyp, cluster_representative, domains↔Domain (M2M), embedding (pgvector 1152-d) | — |
| `Domain` | id, acc, name, ref_db, description | e.g. Pfam acc "PF00001" |
| `ProteinDomain` | id, protein→Protein, domain→Domain, start_position, end_position, score | AA coordinates |
| `Cds` | id, protein→Protein, contig→Contig, gene_caller→GeneCaller, start_position, end_position, strand, protein_identifier, pipeline_version | nt coordinates on contig |
| `CurrentStats` | id, created_at, updated_at, stats (JSON) | Pre-computed global stats |
| `UMAPTransform` | model_blob, n_samples_fit, pca_components, n_neighbors, min_dist, metric, sklearn_version, umap_version, sha256 | Trained UMAP model binary |

---

## 2. Search Pipeline (All 4 Types)

### Entry Points
```
POST /api/search/{keyword,advanced,sequence,chemical}
  → api.py validates with Pydantic schema (api_schemas.py)
  → Celery task dispatched via tasks.py
  → Returns HTTP 202 + {task_id}
```

### Stage 1: Input Validation (api_schemas.py)

| Schema | Input Fields | Transformations |
|--------|-------------|-----------------|
| `KeywordSearchIn` | keyword: str | None |
| `AdvancedSearchIn` | bgc_class_name, mgyb, assembly_accession, contig_accession, biome_lineage, completeness (list[0,1,2]), protein_domain, domain_strategy, detectors | None at schema layer |
| `SequenceSearchIn` | sequence, sequence_type, unit_of_comparison, similarity_measure, similarity_threshold, set_similarity_threshold | Default set_similarity_threshold=0.5 when unit="proteins" (in api.py) |
| `ChemicalSearchIn` | smiles_text, smiles, similarity_threshold | smiles_text takes priority over smiles; normalized to `clean_params["smiles"]` |

### Stage 2: Cache Key Generation (cache_utils.py)
```python
search_key = urlencode(to_post_dict(clean_params), doseq=True)
# OR
generate_job_key_from_dict(cleaned_data)  → SHA256 hex
```

### Stage 3: Search Execution (tasks.py → searches.py → filters.py)

#### Keyword Search
```
tasks.keyword_search(search_key, {keyword})
  → searches.search_bgcs_by_keyword(keyword)
    → filters.BgcKeywordFilter — staged regex dispatch:
        len<3         → empty QS
        ^erp\d+$      → study__accession lookup
        ^erz\d+$      → assembly__accession lookup
        ^mgyc\d+$     → contig__mgyc lookup
        ^mgyb\d+$     → id=int(strip "MGYB")
        ^pf\d{5}$     → domains__acc lookup (distinct)
        ^mgyp\d+      → protein_identifier__icontains (distinct)
        vocab check   → classes__in (BgcClass name match)
        vocab check   → detector__in (BgcDetector name match)
        mixed alphanum → assembly__accession lookup
        pure alpha    → OR(biome_lineage, metadata JSON, domain name)
        fallthrough   → empty QS
```

#### Advanced Search
```
tasks.advanced_search(search_key, clean_params)
  → searches.search_bgcs_by_advanced(criteria)
    Base QS: Bgc.filter(is_aggregated_region=False)
              .select_related(detector, contig, contig__assembly, contig__assembly__biome)
              .prefetch_related(classes)
    Filters applied sequentially (short-circuit on empty):
      detectors      → detector__in (resolve name → latest version PK)
      bgc_class_name → classes__name__icontains
      mgyb           → id=int(strip "MGYB")
      assembly_accession → contig__assembly__accession
      mgyc           → contig__mgyc
      biome_lineage  → contig__assembly__biome__lineage__startswith
      completeness   → 0=is_partial=False, 1,2=is_partial=True
      protein_pfam   → (intersection): each domain → AND-chained Q objects
                       (union): reduce(operator.or_, domain_queries)
```

#### Sequence Search
```
tasks.sequence_search(search_key, clean_params)
  → SeqAnnotator.annotate_sequence_file(sequence)
    │ Parse FASTA/GenBank, detect nt vs protein
    │ Nucleotide: pyrodigal gene prediction → CDS features with translation
    │ Protein: back-translate, single CDS
    │ Embed proteins via ESMEmbedder (esmc_600m model, hidden layer 29)
    │   → individual embeddings + L2-normalized mean BGC embedding
    │ Compute UMAP coordinates via registered UMAPTransform
    └ Returns: SeqRecord with CDS+embedding qualifiers + BGC embedding annotation
  → searches.search_bgcs_by_record(record, unit, measure, threshold, set_thr)
    Dispatches to one of 6 services (bgc_query.py):
      bgc+cosine      → _bgc_embedding_search:
                        pgvector CosineDistance("embedding") ≤ 1-threshold
                        score = 1.0 - pgvector_distance
      bgc+hmmer       → _bgc_hmmer_search:
                        nhmmer (nt query vs all BGC nt sequences block)
                        score = HMMER bit score
      protein+cosine  → _protein_embedding_search:
                        pgvector on Protein.embedding (first CDS)
                        Map protein→BGC via Cds join
      protein+hmmer   → _protein_hmmer_search:
                        phmmer (single query protein vs all protein block)
      proteins+cosine → _proteins_set_embedding_search:
                        pgvector for each query CDS embedding
                        Sørensen–Dice: 2*|matched|/(n_query+n_subject)
      proteins+hmmer  → _proteins_set_hmmer_search:
                        phmmer per BGC protein set
                        Sørensen–Dice on matched sets
    All return Dict[bgc_id → score]
    → Annotated QS: Case/When adds similarity pseudo-column, order_by("-similarity")
```

#### Chemical/SMILES Search
```
tasks.compound_search(search_key, {smiles, similarity_threshold})
  → searches.sequence_bgcs_by_smiles(query_smiles, threshold)
    For each Bgc with compounds (compounds field is list of dicts):
      For each compound SMILES key:
        RDKit Morgan fingerprint (radius=2, 2048-bit)
        Tanimoto similarity
        Track max score per BGC
    Filter where max_score >= threshold
    → Annotated QS with similarity pseudo-column
```

### Stage 4: Queryset → Website Results (helpers.py)
```
all searches → find_doppelganger_bgcs(queryset)
             → annotate_queryset(queryset)
               Adds computed columns:
                 start_position_plus_one  (1-based display)
                 contig_accession         (from contig.name)
                 assembly_accession       (Coalesce → "N/A")
                 study_accession          (Coalesce → "N/A")
                 class_names              (ArrayAgg of class names, distinct)
                 detector_names           (from metadata["detectors"])
               Defers: embedding, contig.sequence, contig.sequence_sha256
             → from_queryset_to_website_results(queryset)
               1. .values() → pandas DataFrame
               2. id → MGYB accession (mgyb_converter)
               3. Sample ≤1000 rows for UMAP scatter (UMAP_PLOT_SAMPLE=1000)
               4. Enrich scatter: umap_x_coord, umap_y_coord, class_tag, is_mibig_tag
               5. Build display_columns: [{name, slug}] for table headers
               Returns: (df, result_stats, scatter_data, display_columns)
```

### Stage 5: Cache Storage (cache_utils.py)
```
set_job_cache(search_key, task_id, results={df, stats, scatter_data, display_columns})
  cache.set(task_id → search_key)
  cache.set(search_key → {task_id, df, stats, scatter_data, display_columns})
```

---

## 3. BGC Detail Page Pipeline

### Entry: `/bgc/?bgc_id=<id>`
```
bgc_page view (views.py)
  → get_job_status(search_key="bgc_id=<id>")
  → if not SUCCESS: tasks.collect_bgc_data.delay(search_key, {bgc_id})
```

### `collect_bgc_data` Task (tasks.py → services)
```
tasks.collect_bgc_data(search_key, {bgc_id})
  → services/annotation/build_bgc_record.py: build_bgc_record(bgc_id, extended_window=2000)
    │
    │ DB Queries:
    │   Bgc + contig + assembly + study + biome
    │   Aggregated BGC regions (from metadata["aggregated_region_ids"])
    │   CDS within window (with proteins, domains, gene_callers)
    │
    │ Window: [bgc.start - 2000, bgc.end + 2000] clipped to contig bounds
    │
    │ Builds SeqRecord:
    │   seq = contig.sequence[window_start:window_end]
    │   id = bgc.accession (MGYB...)
    │
    │ Adds features (all coordinates relative to window_start):
    │   CLUSTER features (for each aggregated BGC):
    │     source = detector.tool
    │     ID = bgc.accession
    │     BGC_CLASS = sorted class names
    │     detector_version = detector.version
    │   CDS features (for each CDS in window):
    │     source = gene_caller.name
    │     ID = cds.protein.mgyp or generated
    │     cluster_representative = protein.cluster_representative
    │     translation = protein.sequence
    │     gene_caller = gene_caller.name
    │   ANNOT features (for each ProteinDomain on CDS proteins):
    │     source = "Pfam"
    │     score = proteindomain.score
    │     ID = domain.acc
    │     GOslim = pfamToGoSlim[domain.acc] → list of GO terms
    │     description = domain.description
    │
    │ annotations dict:
    │   source = JSON: {bgc_accession, assembly_accession, study_accession,
    │                   biome_lineage, contig_accession, start, end, bgc_pk}
    │   molecule_type = "DNA"
    └
    → EnhancedSeqRecord

  → EnhancedSeqRecord.to_gbk() → GenBank text string (cached as record_genebank_text)
  → region_plots.plot_contig_region(record) → HTML div string (Plotly)
  → EnhancedSeqRecord.to_cds_info_dct() → per-CDS dict:
      {
        "cds_id": {
          sequence, cluster_representative, protein_length,
          gene_caller, start, end, strand,
          pfam: [{PFAM, description, go_slim, envelope_start, envelope_end, e-val}]
        }
      }
      Note: envelope coords in AA space: (nt_pos - cds_start) // 3

  Cached result keys:
    record_genebank_text, plot_html, bgc_id, assembly_accession, assembly_url,
    biome_lineage, predicted_classes_dict, functional_annotation_dict,
    cds_info_dict, contig_accession, start_position, end_position
```

---

## 4. Download Pipeline

### Single BGC Download: `GET /api/download/bgc?bgc_id=<id>&output_type=<type>`
```
api.download_bgc (api.py)
  → mgyb_converter: "MGYB000000123" → 123 (int)
  → get_job_status(search_key="bgc_id=<pk>")
  → if not SUCCESS: tasks.collect_bgc_data.apply() (synchronous!)
  → EnhancedSeqRecord.from_genbank_text(cached_record_genebank_text)
  → switch output_type:
      gbk  → record.to_gbk()    Content-Type: application/genbank
      fna  → record.to_fna()    Content-Type: text/x-fasta
      faa  → record.to_faa()    Content-Type: text/x-fasta
                CDS features with "translation" qualifier → individual FASTA proteins
      json → record.to_json()   Content-Type: application/json
  → HttpResponse + Content-Disposition: attachment; filename="{MGYB...}.{ext}"
```

### Search Results TSV: `GET /api/download/results-tsv?task_id=<id>`
```
api.download_results_tsv (api.py)
  → get_job_status(task_id=query.task_id)
  → payload["df"] (pandas DataFrame from cache)
  → Columns: accession, assembly_accession, contig_accession,
             start_position_plus_one, end_position, detector_names, class_names
  → df[display_columns].to_csv(sep="\t", index=False) → TSV string
  → HttpResponse + Content-Disposition: attachment; filename="bgc_search_results_{task_id}.tsv"
```

### Web Download (Views): `GET /bgc/download/?search_key=...&output_type=...`
Same flow as API download but via Django view layer (`views.py`).

---

## 5. Template Rendering Chain

### URL → View → Template → Variables

| URL | View | Template | Key Context Variables |
|-----|------|----------|-----------------------|
| `/` | `landing_page` | `landing_page.html` | (none) |
| `/search/` | `search` | `search.html` | `advanced_form`, `sequence_form`, `chemical_form`, `result_stats` |
| `/results/?...` | `results_view` | `results.html` → includes `results_table.html` | `results` (paginator), `encoded_params`, `result_stats`, `columns`, `sort`, `order`, `scatter_json` |
| `/bgc/?bgc_id=...` | `bgc_page` | `bgc_page.html` | `mgyb`, `predicted_classes_dict`, `functional_annotation_dict`, `assembly_accession`, `assembly_url`, `biome_lineage`, `contig_accession`, `start_position`, `end_position`, `plot_html` (safe HTML), `cds_info_dict` (JSON) |

### `result_stats` Structure (from `CurrentStats.stats` or task payload)
```python
{
    "total_regions": int,
    "n_assemblies": int,
    "n_studies": int,
    "bgc_class_dist": {
        "Polyketide": 23.5,  # % (normalized, aliases folded)
        "NRP": 18.2,
        ...
    }
}
```
Class name normalization in `normalize_class_distribution_dict` (`utils/helpers.py`):
- NRPS → NRP
- PKS → Polyketide
- ribosomal → RiPP
- other → Other

### `columns` Structure (display_columns)
```python
[{"name": "Accession", "slug": "accession"}, ...]
```
Columns: `accession`, `assembly_accession`, `contig_accession`, `start_position_plus_one`,
`end_position`, `detector_names`, `class_names`, (+`similarity` if sequence search)

### `scatter_json` Structure (UMAP points, sampled ≤1000)
```python
[
  {
    "id": 123,                  # BGC pk (int)
    "x": 1.23,                  # from Bgc.metadata["umap_x_coord"]
    "y": -0.45,                 # from Bgc.metadata["umap_y_coord"]
    "class_tag": "Polyketide",  # primary class
    "is_mibig_tag": true,       # from metadata["is_mibig"]
    "accession": "MGYB...",
    ...                         # other result columns for hover text
  }
]
```

### JavaScript Rendering (in templates)

**`results_table.html`** inline JS:
- Parses `scatter_json` from `<script id="bgc-json" type="application/json">` tag
- Groups by `class_tag` → one Plotly trace per class; MiBiG points marker size 14 (vs 8)
- Click point/row → `window.open('/bgc/?bgc_id={id}')`

**`bgc_page.html`** inline JS:
- Parses `cds_info_dict` from `<script id="cds-info-data">` (Django `json_script` filter)
- Listens to Plotly click events; only responds to features where `customdata.type === 'CDS'`
- Dynamically renders PFAM annotation table + protein sequence into `#cds-info` div
- Highlights clicked CDS trace (`line.width = 5`)
- Copy sequence button: `navigator.clipboard.writeText(sequence)`

---

## 6. Key Transformation Functions Quick Reference

| Need to change... | Function | File |
|-------------------|----------|------|
| BGC accession format (MGYB...) | `mgyb_converter()` | `utils/helpers.py` |
| QuerySet fields exposed to UI | `annotate_queryset()` | `utils/helpers.py` |
| Result DataFrame structure | `from_queryset_to_website_results()` | `utils/helpers.py` |
| BGC class name aliases | `normalize_class_distribution_dict()` | `utils/helpers.py` |
| Keyword search patterns | `BgcKeywordFilter` | `filters.py` |
| Advanced search filter logic | `search_bgcs_by_advanced()` | `searches.py` |
| Sequence similarity algorithms | `_bgc_embedding_search()` etc. | `services/bgc_query.py` |
| Chemical similarity | `sequence_bgcs_by_smiles()` | `searches.py` |
| BGC record features (GenBank) | `build_bgc_record()` | `services/annotation/build_bgc_record.py` |
| Plot rendering | `plot_bgc_region()` | `services/region_plots.py` |
| CDS info panel data | `EnhancedSeqRecord.to_cds_info_dct()` | `utils/seqrecord_utils.py` |
| GenBank / FASTA exports | `EnhancedSeqRecord.to_{gbk,fna,faa,json}()` | `utils/seqrecord_utils.py` |
| PFAM → GO-slim mapping | `pfamToGoSlim` dict | `services/region_plots.py` |
| Cache key generation | `generate_job_key_from_dict()` | `cache_utils.py` |
| Protein embeddings | `ESMEmbedder.embed_gene_cluster()` | `services/protein_embeddings.py` |
| UMAP coordinate storage | `register_umap_transform()` | `services/db_operations/register_umap.py` |
| NDJSON ingestion | `ingest_package()` | `services/db_operations/ingest_package.py` |

---

## 7. End-to-End Field Traceability

| UI Field | DB Source | Transformation Chain |
|----------|-----------|----------------------|
| BGC Accession (MGYB...) | `Bgc.id` | `mgyb_converter(id)` → `"MGYB{id:012}"` |
| Assembly Accession | `Assembly.accession` | `annotate_queryset` → Coalesce → DataFrame column |
| Contig Accession | `Contig.name` | `annotate_queryset(contig_accession=contig.name)` |
| Start Position (1-based) | `Bgc.start_position` | `annotate_queryset(start_position_plus_one=start+1)` |
| End Position | `Bgc.end_position` | Direct (0-based) |
| Detector Names | `Bgc.metadata["detectors"]` | `annotate_queryset(detector_names=metadata["detectors"])` |
| Class Names | `BgcClass.name` via M2M | `ArrayAgg("classes__name", distinct=True)` |
| Similarity Score | Computed | `Case/When(pk=pk, then=Value(score))` annotation |
| UMAP x, y | `Bgc.metadata["umap_x_coord/y_coord"]` | Written by `register_umap_transform()` |
| BGC Class % (stats) | `BgcBgcClass` counts | `normalize_class_distribution_dict()` |
| PFAM Domains (plot) | `ProteinDomain.domain.acc` | `build_bgc_record()` → ANNOT features |
| PFAM Envelope AA Coords | `ProteinDomain.start/end_position` | `(nt_pos - cds_start) // 3` in `to_cds_info_dct()` |
| GO-slim Terms | `Domain.acc` + `pfamToGoSlim` dict | Lookup in `services/region_plots.py` |
| Protein Sequence (CDS panel) | `Protein.sequence` | SeqRecord CDS feature `translation` qualifier |
| Cluster Representative | `Protein.cluster_representative` | CDS feature qualifier + URL generation |
| Compound SMILES | `Bgc.compounds` (list of dicts, SMILES as keys) | Iterated in `sequence_bgcs_by_smiles()` |
| SMILES SVG (card view) | `Bgc.smiles_svg` | Stored pre-rendered; `smiles_to_svg()` in `services/compound_search_utils.py` |

---

## 8. Critical Files

```
django/mgnify_bgcs/
  models.py                            ← DB schema
  api.py                               ← REST API endpoints (Ninja)
  api_schemas.py                       ← Pydantic I/O schemas
  tasks.py                             ← Celery task orchestration
  searches.py                          ← Search logic + QS assembly
  filters.py                           ← Keyword pattern dispatch
  cache_utils.py                       ← Redis cache R/W
  utils/helpers.py                     ← annotate_queryset, from_queryset_to_website_results
  utils/seqrecord_utils.py             ← EnhancedSeqRecord, build_bgc_record, export formats
  services/bgc_query.py                ← 6 similarity search engines
  services/region_plots.py             ← Plotly genomic visualization
  services/annotate_record.py          ← SeqAnnotator (gene prediction + ESM embeddings)
  services/protein_embeddings.py       ← ESMEmbedder class
  services/hmmer_utils.py              ← HMMER sequence blocks (lazy cached)
  services/db_operations/
    ingest_package.py                  ← NDJSON stream ingestion
    register_umap.py                   ← UMAP coordinate storage
    export_embeddings.py               ← Parquet export for UMAP training
django/bgc_data_portal/
  views.py                             ← Django views (render + polling)
  urls.py                              ← URL routing
  templates/
    search.html                        ← Search forms + stats sidebar
    results.html                       ← Spinner + result tabs wrapper
    results_table.html                 ← Table/Cards/UMAP tabs + JS
    bgc_page.html                      ← BGC detail + Plotly + CDS panel + JS
    landing_page.html                  ← Home page cards
static/js/scripts.js                   ← Spinner helpers, form submit guard
```
