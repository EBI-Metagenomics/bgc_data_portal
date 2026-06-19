# Changelog

## [3.9.0](https://github.com/EBI-Metagenomics/bgc_data_portal/compare/bgc_data_portal-v3.8.0...bgc_data_portal-v3.9.0) (2026-06-19)


### Features

* **portal:** per-criterion scoring in Discovery combined query ([18326ea](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/18326eab2efe7c42e3ef28340507b4b67d00eef0))
* **portal:** per-criterion scoring in Discovery combined query ([4729228](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/472922831a1661e82d1ad6ea237eeab9356f88cc))


### Bug Fixes

* **deployment:** Bump app and chart version ([f2b64ef](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/f2b64ef0dfe8952b0ec7851b72e241911edc49e6))
* result-set token. So large Run Query allow-lists no longer ride in the GET URL ([5b6aa85](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/5b6aa8545c428be53bd168d4280740d33b498e4c))

## [3.8.0](https://github.com/EBI-Metagenomics/bgc_data_portal/compare/bgc_data_portal-v3.7.0...bgc_data_portal-v3.8.0) (2026-06-18)


### Features

* **discovery:** Improve iBGC provenance in Reports by adding: taxonomy, collection, bgc detectors ([fdf7f08](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/fdf7f0879fa1b9c053fd473e4f97376046d75ede))
* **discovery:** Support new core domain extraction and querying in platform ([e28db41](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/e28db4116cddebe78483c1b9bd760b3507799650))

## [3.7.0](https://github.com/EBI-Metagenomics/bgc_data_portal/compare/bgc_data_portal-v3.6.0...bgc_data_portal-v3.7.0) (2026-06-17)


### Features

* **portal:** cap query results at 5k with banner, add sortable pident/qcov ([19a8f61](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/19a8f611391cf9cabcf832bc1dd2db05ebbc76f6))
* **worker:** Keep copy of ChemOnt OBO in repo ([f06e6a0](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/f06e6a00da7e2ec7d133a8b0baa218d68587b3e2))


### Bug Fixes

* **discovery:** detect MIBiG accessions as assembly and fix filter reset/chip state ([8f07b22](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/8f07b2256e4a973569a8a440f35453947fbc3a98))

## [3.6.0](https://github.com/EBI-Metagenomics/bgc_data_portal/compare/bgc_data_portal-v3.5.4...bgc_data_portal-v3.6.0) (2026-06-15)


### Features

* **asset classification:** Support rectangular matrix similarity search ([9d42625](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/9d4262505b7aea6d44683d9b17ddaa9db8ea475f))
* **prod:** pin portal 3.5.4-12801fe ([9c48f1d](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/9c48f1d65c809c9866763fcc1e24d1f100669f03))


### Bug Fixes

* **helm chart:** Bump chart version ([fe944d8](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/fe944d8ee3342e4e30825bf222300c58de6193ba))

## [3.5.4](https://github.com/EBI-Metagenomics/bgc_data_portal/compare/bgc_data_portal-v3.5.3...bgc_data_portal-v3.5.4) (2026-06-15)


### Bug Fixes

* **portal:** Drop WebGL for scatterplots to support CSP enforcement ([e5dae5e](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/e5dae5e8793d72c583ed66a08a850d2c459ab3db))
* **portal:** Drop WebGL for scatterplots to support CSP enforcement ([30cbfc9](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/30cbfc94bc9579fe698a078e24a13908ad48e23d))

## [3.5.3](https://github.com/EBI-Metagenomics/bgc_data_portal/compare/bgc_data_portal-v3.5.2...bgc_data_portal-v3.5.3) (2026-06-12)


### Bug Fixes

* **ci:** Reference to OCI chart repo ([3362a4a](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/3362a4a01789cc86f17e6e990fcec72b130fa202))

## [3.5.2](https://github.com/EBI-Metagenomics/bgc_data_portal/compare/bgc_data_portal-v3.5.1...bgc_data_portal-v3.5.2) (2026-06-12)


### Bug Fixes

* **ci:** Readability of container tags ([1279031](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/1279031d673485913498a6a90e02b239a287bf8f))

## [3.5.1](https://github.com/EBI-Metagenomics/bgc_data_portal/compare/bgc_data_portal-v3.5.0...bgc_data_portal-v3.5.1) (2026-06-12)


### Bug Fixes

* **ci:** Bad path to chain build and push with release-please ([e635d60](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/e635d604f3327d54f77f068e8d3b1afc4985d6f6))

## [3.5.0](https://github.com/EBI-Metagenomics/bgc_data_portal/compare/bgc_data_portal-v3.4.0...bgc_data_portal-v3.5.0) (2026-06-12)


### Features

* **ci:** Support contener build & push after release-please action ([306353c](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/306353c296aa2cf22de0fcc2a79ebac8267cac7d))

## [3.4.0](https://github.com/EBI-Metagenomics/bgc_data_portal/compare/bgc_data_portal-v3.3.1...bgc_data_portal-v3.4.0) (2026-06-12)


### Features

* **ci:** Support OCI publishing ([654cf6d](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/654cf6dd6698701828e92e7138c1cdfcb3ce7027))

## [3.3.1](https://github.com/EBI-Metagenomics/bgc_data_portal/compare/bgc_data_portal-v3.3.0...bgc_data_portal-v3.3.1) (2026-06-11)


### Bug Fixes

* Remove "Evaluate Asset" card from landing page ([d52015c](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/d52015ce6cbd3ebbdfeed8a25e4c3442c39d0cec))

## [3.3.0](https://github.com/EBI-Metagenomics/bgc_data_portal/compare/bgc_data_portal-v3.2.0...bgc_data_portal-v3.3.0) (2026-06-11)


### Features

* **bgc clustering:** Support knn-graph/laiden clustering analysis ([4b98d80](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/4b98d80e6969a06f2f177c4ffcea0c0ac03fba58))
* **bgc clustering:** Support local clustering ([1afea6c](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/1afea6ce4d2bf5d30db8342b8dac221152614a61))
* **BGC detail:** Mark selected NRB ([bdd633a](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/bdd633a021947e6298c471926081b0c685c9c58a))
* **BGC plots:** When IPS domain has GO term that only maps to 'molecular function' emit no GO slim ([8233baf](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/8233baff5ab59184fd1eedef4124604dc12a3a58))
* **chart:** make self-host turnkey from the public OCI chart ([26736bd](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/26736bdecd9c2e9afab6044ef23e76ff8276d09e))
* **clustering:** Support clustering pattern using knn graph and leiden CPM approach ([a05caf8](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/a05caf8a8757bf693e387e306c950dfabfdb80ce))
* **clustering:** Support compact GCF naming convention ([ae5aaa5](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/ae5aaa500a37b2b60c2a80aaae0b5c30847acc69))
* **clusterin:** Support IPR entry deduplication in domain architecture ([35cf1f6](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/35cf1f628e51cfafad28c6d908b4c42dd2399e02))
* **dashboard:** Aesthetic changes ([c769ed2](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/c769ed24e86aa3e18cc91ba0f1de32bc901b1161))
* **dashboard:** New dashboard version ([a1a1a54](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/a1a1a54ea16da8ca559ade5c1f9cccd48076f160))
* **dashboard:** Support asset submission ([73c4c43](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/73c4c431ba578dc201f5eec8158ff5ae66e6a3dc))
* **dashboard:** Support domain architechture similarity searches ([6ae3e79](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/6ae3e7954baa0e5733e5ee258bd0b853556d9adb))
* **dashboard:** Support filters by GCF and kebab menu in NRB cards ([f7eed79](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/f7eed793df3e6d68c845aa23eaa86c9febd8a775))
* **dashboard:** Support hmmer sequence protein searches ([1f4192e](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/1f4192e7d6ab72b313cd63e470f940e90bad6da2))
* **dashboard:** support query results varibles in maps ([860a56a](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/860a56a9ff706e2811d4c7d378b644d61beb2bea))
* **Dashboard:** Support report generation with ([c3fcce1](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/c3fcce1247d47979fef411075908cc65a3eac79d))
* **deploy:** add canonical Helm chart for portal (laptop + cloud targets) ([268544b](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/268544b7babaf91a2c89c91e1b9753ad58f618d1))
* **deploy:** build-from-source self-host path (no private registry) ([7c1b39f](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/7c1b39f3598d44e81ce662d9dd741889b6443b4c))
* **deploy:** migrate dev inner-loop to k3d + Skaffold Helm deployer ([bb730e5](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/bb730e54d8da2a7754fd3190af6b380c831f97e2))
* **deploy:** retire cloud Skaffold profiles + legacy manifests; publish chart to OCI ([5f011ee](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/5f011eeabcf83e48cc2de76ff280292bceda9f16))
* **discovery:** Chain async DiscoveryStats refresh after ingestion commands ([a9b1520](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/a9b1520320e050e55c0c52e662b641767d454782))
* **discovery:** convert sequence search to async POST→202+poll pattern ([ec5b1d9](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/ec5b1d9007d1469f17cd677e4eaf2b320ab5a474))
* **discovery:** gate UI-only API endpoints and add per-IP rate limiting ([8d51447](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/8d5144777fc48f399693d51f605cee7b8161ff38))
* **discovery:** iBGC class/status chips, report class bar, roster columns ([02f598b](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/02f598bb85994149c14710d61e68a53a916639cc))
* **discovery:** ingest BGC classification_path + derive normalized iBGC class ([3c71fd7](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/3c71fd783ba595a155f4a64ba84fb18353223eab))
* **discovery:** unify Accessions filter into a single smart field ([035ade1](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/035ade176911fe293f1f3325ff96623a186127a0))
* Infor in NRB chips and urls ([9091529](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/909152952b1b5ec9bd1ba77f72843a297d600d2f))
* **ingestion:** capture InterPro entry + GO terms on BgcDomain ([837f56a](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/837f56aeaa1e0f8b014dcb4efb69ccb7a50b8157))
* **local dev pattern:** Support auto clean of previous versions in `make dev` command ([edadcc4](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/edadcc497269e7d2d97cd4205cb4264cdb1bf0df))
* **local_dev:** Support make command to load real data into local dev cluster ([5c406a4](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/5c406a4ce3d9da92c1bede761f921c1025592221))
* **NP preds:** Support CHEMONT to GENE using CHAMOIS results ([0d00f42](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/0d00f4214c1b563730b7eb1a41dda95efe633d4a))
* **portal:** Switch frontend to /api/discovery and iBGC accessions ([97e0a67](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/97e0a67671cc368f7104efa693912d3365c0a6da))
* Support ClassyFire using API ([e240510](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/e240510e1b03c8d62d6a765880de12403b3b8ebf))


### Bug Fixes

* **bgc detail plot:** Standardize Go SLIM colors ([6f6e4b0](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/6f6e4b0714ab9532ab635b8fff00679b0cb40ce9))
* **clusering:** Force is_validated==true iBGC have novelty of 0.0 ([9ba753d](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/9ba753d328ded90637403e09c4a7b40caf4c1f42))
* **clustering:** Amebd local clustering inputs path ([16b407e](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/16b407ee32007335a4d56de4defcdc2849d2bc80))
* **dashboard:** filters looks ([c1c4268](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/c1c4268a6f7df58355e262cfc5dc0c645700caf3))
* **dashboard:** Fix filters wiring ([bb3d374](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/bb3d374a2d68557aede9f1d48e8fe032f4a1d032))
* **dashboard:** GOslim assignment in submitted assets ([00f713c](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/00f713ca87c23e43f500ddca55177d92f41efe80))
* **dashboard:** Load of asset to repport failing ([fa3d970](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/fa3d970bcde9064f9d8e4f2b4954780ffc6b5c6d))
* **dashboard:** NRB detector overlap on partial BGCs ([146a32c](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/146a32c58e9c6b352e736f1152bd7e60e96a3836))
* **deploy:** pin Helm v3 for the Skaffold dev loop (Helm v4 incompatible) ([63d6f51](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/63d6f51dce86f8f1da25b6dd2b0375d355d9cbff))
* **deploy:** pin k3d kube-context on the dev loop; repair cluster-create kubeconfig merge ([8cae415](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/8cae415de61b7b0ead164ebace7804aac2fa443e))
* **deploy:** wire PROTEIN_SEARCH_INDEX_DIR onto hf-cache PVC for celery ([3592564](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/35925646d71c5856f0d9819bdf62f0d47c3d1303))
* **discovery platform:** Change NRB references for integrated BGCs (iBGC) ([283462b](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/283462b357d67a6747db316c1484551240d80d77))
* **discovery:** add missing NRB scoring columns (umap_projected, novelty_score, domain_novelty) ([6d792dd](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/6d792dd4b75a19ce01ef35a0ce7bb584929d25c3))
* **discovery:** apply catalogue filters alongside a loaded asset ([c23dfbc](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/c23dfbc6da158e7370a9578e76c5a3ec9af7a4d2))
* **discovery:** Correct ContigDomain table name in range-overlap SQL ([f549345](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/f5493456da41995a79fb257d3981fb423d3cf369))
* **discovery:** make the roster Bitscore column sortable ([2287358](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/228735897477a50de976105c79b0272f01ad0b76))
* **discovery:** map sequence search results by iBGC id ([e654aa5](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/e654aa5fba9fcaf90e64eaa11da04ff589c1985d))
* **discovery:** Repair iBGC API endpoints broken by the Phase 2f rename ([1f14a7a](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/1f14a7ad725a5d621a8f67656bb3faec91cb1920))
* **discovery:** repair Load Asset end-to-end (tarball validation, projection ([57f3a81](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/57f3a81abad23916735beefc6683d8542d7f00a7))
* **discovery:** Replace psycopg2 NumericRange import with Django's psycopg_any shim ([3dfd4d4](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/3dfd4d4bee16479410228c8742b0eda7a8234c0d))
* **discovery:** Restore DashboardBgcClass import in api.py ([95800c1](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/95800c1c5742dbf41f7ab3209f765bd4ee61499d))
* **ingestion:** Dedup upsert batches to avoid ON CONFLICT double-touch ([6993820](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/699382007177299e2eefe840d6b17533eda2c252))
* **keyword search:** Route free-text keywords to domain annotations and auto-run the v2 query ([887b50a](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/887b50a89c4aba0b585cb7c0b5d423dcded6d0f6))
* **keyword search:** Wiring keyword search pattern ([9088858](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/9088858b765546219835be9b82147e8f263b8983))
* **migrations:** Migrations error on pair based clustering ([353879e](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/353879e76e3207da76fcb903b355c351bd4d331b))
* Nesting of ChemOnt classes ([a5bb084](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/a5bb08494b2436b4856641321e3b44a5039c8100))
* **NP predictions:** gene - chemont asociation scores ([c48b9c4](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/c48b9c48cdff4243da8d56fe22ef4e590ebb61c9))
* **NRB plot:** Prevent extremely large regions plot from failing. Add guard ([0f4d22b](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/0f4d22b74d3a5c6df4913a91d169b4a599b3b1dd))
* **portal:** path traversal + info leaks + workflow perms, fix(deps): ([5d20ab6](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/5d20ab6d62fcfa089c16f269917d3e61aba50c82))
* **portal:** Unblock prod frontend build (BgcScatter mode type) ([872b71d](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/872b71df8539bdf366194bbbe603d0d3522ae752))
* Render report correcly ([b479900](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/b479900e3c872021b2c797c7fe721b47f544943d))
* **scoring patter:** Download needed OBO file for classyfire and novelty scoring patterns ([51f7c38](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/51f7c38166865adb850d3f446abedd231377a28e))
* **security:** Close securityh gaps raise by CodeQL ([2cc3950](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/2cc3950b1ab65751dc6b9bdb787f43c9c8b0cacb))


### Performance Improvements

* **api:** Retrive assembly source in first queryset pass ([bb3456c](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/bb3456c495f9d94d4a078c9f8ddcabe9f88d594b))
* **discovery:** Support chunked protein searches to leverage multi threading ([bc72a8e](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/bc72a8eefc9131698ea21a66bf35f8e569b7b245))

## [3.2.0](https://github.com/EBI-Metagenomics/bgc_data_portal/compare/bgc_data_portal-v3.1.0...bgc_data_portal-v3.2.0) (2026-04-23)


### Features

* **Dashboard Roster:** Display source in roster ([ee01f79](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/ee01f7900fd290c5fda742946cde61516377d8b8))
* **discovery:** add GO slim to BgcDomain and load_pfam_go_slim command ([fda506c](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/fda506c822126cafe9e0ca50cf024f7e4328d545))
* **portal:** CDS connector lines in BGC comparison view ([ebe012f](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/ebe012fbd273053cdfc93d4e1a0f46e4daaa8e10))
* **portal:** ChemOnt leaf-only display and SMILES MolView link ([8290167](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/829016723fde3fca0672dafc27b1660cd2615af5))
* **portal:** GO slim CDS coloring and remove domain overlays from RegionPlot ([549c2ac](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/549c2acba43c4f5b20b8ee8de4b91427a03cc220))
* **portal:** parent assembly accession link to assembly URL ([51fc437](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/51fc437778deae4c1b7c261d2c58c6cefd0d5fa3))
* **portal:** replace type-strains toggle with Source and BGC Detector filters ([2867370](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/2867370d090ed1edb4252cbf9fdb92c638ea8745))


### Bug Fixes

* **clustering:** add --sync flag to run_bgc_clustering to bypass RabbitMQ ([78aeb4b](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/78aeb4bbff86dce7e5bd0df7bb666b1300b3c370))
* **dashboard:** Empty BGC Roster in the Assembly "Evaluate Asset" ([7dfcd2c](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/7dfcd2ce84c452ca490c55ca8c32c3467ca2c90a))
* **ingestion:** add batch_size to bulk_create in sequence loaders ([5e10d49](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/5e10d4997b63fba851e8dcf700f960a070596d9e))
* **ingestion:** avoid absorbing current region in _extend conflict path ([90f0f9b](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/90f0f9b6128daf1423f18ddf15b0bf2edbaf69c7))
* **ingestion:** avoid absorbing current region in _extend conflict path ([45efd5b](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/45efd5bf8a342b8e9f986af922a637dddc078191))
* **ingestion:** handle region extend collision from prior interrupted run ([c6695c9](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/c6695c9d564dd4b9a270a552f216b060127e29d6))
* **search:** align protein sequence search to final ESM-C layer ([eac57bf](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/eac57bf5339c7988fe3b9e528cc6e060f40d2302))
* **search:** correct three bugs in keyword filter that silently broke free-text search and threw errors on regex-unsafe input ([feb4777](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/feb4777be0a8c6ce09e40aa28999613d0379630a))


### Reverts

* **portal:** remove CDS connector lines from comparison view ([0863b02](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/0863b024d5050685ac10b3d9accae6caf414dc5c))

## [3.1.0](https://github.com/EBI-Metagenomics/bgc_data_portal/compare/bgc_data_portal-v3.0.0...bgc_data_portal-v3.1.0) (2026-04-20)


### Features

* **discovery:** scope domain novelty to GCF bucket ([fc739a4](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/fc739a4abb94e1a60facad4a513b1cf6499cb364))
* **portal:** evaluate-asset region comparison, taxonomy hierarchy, UMAP fixes ([bed2939](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/bed2939565977c5da99e28aca8950a67468a783c))
* **portal:** filter asset-upload domains to PFAM/TIGRFAM + count skipped rows ([1f0e9a0](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/1f0e9a0ac767ce1682cb3bf8367f109db41d75dc))


### Bug Fixes

* **asset evaluation:** Fix file path extention pattern to align with ETL pipeline. `*tar.gz` and `*tgz` ([3fea228](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/3fea228cd84f624af5bb251e5759e7804264927c))
* **clustering:** convert HalfVector to list before numpy array construction ([8ad0dba](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/8ad0dbae55fc6a63a94d7796382ae0d203ba4250))
* **clustering:** read hdbscan version via importlib.metadata ([56818e5](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/56818e50226c24069fc1bfdeafda12e071138bcc))
* **clustering:** use HalfVector.to_list() for numpy conversion ([7cc35f4](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/7cc35f4cfb64e0951ef00e58550c03c8b404ba85))
* **Django ORM:** Manual migrations ([a1cf7ee](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/a1cf7ee7b84e72375296084cf6637b8905cd391a))
* **ingestion:** deduplicate cds_sequences batch by cds_id before bulk_create ([6591afb](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/6591afbf0c01bbf1734683f3f458845582fff4d6))
* **ingestion:** deduplicate domains batch by constraint key before bulk_create ([c5635f8](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/c5635f8e8adfacf19633137ee484338de8bc8f86))
* **portal:** align EMBEDDING_DIM with 960-dim DB column ([27a3fbd](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/27a3fbd79ebcb7b14d4cbb1ec6e0f697a4273e9f))
* **portal:** allow group-write on /app for ([998235a](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/998235ab53d6986ba1c3fed198261dcbb748f724))
* **portal:** bake ingress prefix into Vite base for prod build ([521b5db](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/521b5db6da2effcd65672b7e4a789328103deda1))
* **portal:** bump umap-learn to 0.5.12 for scikit-learn 1.6+ compat ([497bef4](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/497bef4e45e6c09d9f96c26db286ae088d36f36b))
* **portal:** match BGC embeddings case-insensitively in asset upload parser ([f3eba3f](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/f3eba3f43960608d3f2c869ec9e7b8e2fcc320bc))
* **portal:** run collectstatic on Django pod startup ([fbdbfa8](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/fbdbfa8a29ef9cd9d3220ae8e16f94a426f6a941))
* **portal:** show Protein Details card when clicking a CDS in Domain Architecture Comparison ([b91850e](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/b91850eec260091c68409da18a0e6c9b31a6e5d6))

## [3.0.0](https://github.com/EBI-Metagenomics/bgc_data_portal/compare/bgc_data_portal-v2.1.0...bgc_data_portal-v3.0.0) (2026-04-19)


### ⚠ BREAKING CHANGES

* **portal:** release new discovery platform

### Features

* **bgc-data-portal:** add self-contained k8s dev/prod infrastructure ([21e3af2](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/21e3af2b1edcfa2fddf98b7565fc9a4eb7e1deee))
* **ci:** support local-dev with KIND ([ab3b6c7](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/ab3b6c7cb230d2258d3e4c6ee083decc435d1649))
* **ci:** support version bump with please-release ([e87f65a](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/e87f65a09ab079d6646019145e9fc6d0d3559dcd))
* **dashboard:** Add aggregated region and ingestion patterns ([5f5de42](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/5f5de4215fa5b2c9888e33fe5e68bc9bcc979330))
* **dashboard:** Dorp chemical space map from explore/search modes ([d7074e9](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/d7074e90b748ceb6d4b3ef50bd9d6df70e1ea919))
* **dashboard:** element urls in db ([339029b](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/339029b18b4ab0678fa9864115b730d502d53c4f))
* **dashboard:** First draft of Asset evaluation ([c75cd90](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/c75cd90d7a86d5778fc1ea3563fc75ccc191d4bf))
* **dashboard:** Histograms in BGC Asset Evaluation ([8df3bee](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/8df3bee06840fe9f7aa80fa29e7ba7dfcad3829a))
* **dashboard:** Implemented core components of Asset evaluation ([65387d4](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/65387d4dfdd4fc01234c34b4847c12ef9d02f51f))
* **dashboard:** Support filtering by ChemOnt ([26305c5](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/26305c5b0c8339a560f7ad4857b2a667d08eb5b0))
* **dashboard:** Support full BGC and protein card in dashboard ([f0971e9](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/f0971e9d8c96360093a6e0192242d2db292cf0bf))
* **dashboard:** Support stats panel ([7e91ae6](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/7e91ae6040de9cabe3a359ce1db3ecc79a20aca9))
* **dashboard:** support validated bgcs beyond mibig ([a609e7b](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/a609e7b8d5f1fa2a38f7a057217fc7a06552ad66))
* **db:** Encode sequneces as blob ([fde4b41](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/fde4b41f2d648910aee9065eee614cfd5d0fd0b9))
* **db:** Support seed data generation for test and dev ([fb8f082](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/fb8f0825af813fa9875ddf0a38f29244206a78b4))
* **discovery platform:** suppor user submited assets ([79589f6](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/79589f6ca96a1c0a88bae53d40d885c4796124bb))
* **django:** Create a pattern—task,command,api ep, and front end—to expose basic stats ([ddeb0ac](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/ddeb0ace91b17f6cf6b6edbc48566837fafd8135))
* **django:** Support dashboard for exploration ([4110f9b](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/4110f9b854b207aca2fb745cf68e5511fd51d26d))
* **django:** Support dashboard frontend for exploration ([bf9188b](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/bf9188b250a689b435f72d2395c66c97bdae8cbb))
* **django:** Support domain and protein generation in seed data for discovery dashboard ([2866d5d](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/2866d5d0b92536a8ae3151b240c6b87bc84b02f7))
* **env:** Add activation script ([609e0f8](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/609e0f8ead499b9a8be8d9d6e9c68500a785ff77))
* **ingestion:** add bulk ingrstion patters for mgnify-bgcs-etl tables and parquets ([5659064](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/565906403446745a4de79fe5b5e0c9751f6eacdb))
* **landing page:** add cards to access dashboard modes ([fdbdcbc](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/fdbdcbcfc090f59314a01e069fd5e3e174a8ca5a))
* **lanfing page:** Support quickstart card ([3812618](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/3812618735e58a80827065c7e7c89b0cdada6672))
* **portal:** release new discovery platform ([63dadb9](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/63dadb9211bab247a045b1adb39ee9165023cc6b))
* **scoring infrastructure:** Include django commands for updates ([d73f717](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/d73f717eb8cf5ff1d7427cb8c59d4d07fc3ab734))


### Bug Fixes

* **BGC EMBEDDING:** Add migrations to allocate ESM_300M ([23bf19e](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/23bf19e04e0a2bc689ac65039a3d658160ab51cd))
* **ci:** typo in release.yml ([35487a5](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/35487a587448a88becfae41bcd1f403da2918831))
* **container:** fixes to build react ([cb625a9](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/cb625a9b4d1825ba2fe6a5998905d8b48ae1bbd3))
* **container:** Removed dirs from gitignore so react build doesnot fail ([250760e](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/250760e687ef96e15e6c91aea78036e27af833be))
* **dashboard:** BGC stats in Genome exploration beahaviour ([0a8d971](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/0a8d9716d3d6291fcc2a5f500bd00c787edd00fb))
* **dashboard:** BGC/genome roster behaviour on modes ([6d04996](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/6d04996f02ed7a7864d896db89cf9e46f433bcb4))
* **dashboard:** Card stripes and tabs fixed to match style ([1e9caf1](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/1e9caf1bbd217e0eb31535a299453b093dc395b6))
* **dashboard:** Chemical map not showing ([3f6d9e1](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/3f6d9e1f90a74384585468b668f1a60b67de6e3b))
* **dashboard:** Empty BGC map on emty genome shortlist ([c67ff51](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/c67ff51218199ea05bdbe8e7f47b72fce24107a7))
* **dashboard:** Fix Roster size ([b31f06e](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/b31f06e3d1d7014128ad7e6c9c88f24c9fec2e8c))
* **dashboard:** Plase api call for correct query similarity ([8d55c5f](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/8d55c5fe9d6d3c91b0219302ef63a3985f5e5ac0))
* **dashboard:** recover {BGC,Assembly} Detail cards ([b885a5c](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/b885a5c2ea0f040a4a0b6ff5949c155f060af24f))
* **dashboard:** recover BGC space map in Asset Evaluation ([259d4bb](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/259d4bb355e180e6f7c08b959a0563a80b611f37))
* **dashboard:** Resolve import to fix Assembly assestment ([8515cc0](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/8515cc0a378eed63425ed648658c546e2fc437e8))
* **dashboard:** Rosters fixed size ([003d8b4](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/003d8b46782f10b807a5a22e33972715c6965c93))
* **dashboard:** Scrolable BGC roster panel ([76a4ee8](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/76a4ee89f6f1911004a012e51b86c2f23a8d9780))
* **dashboard:** Shepher tour highliting the right elements ([5eaf51d](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/5eaf51da70b7f8f6868d3169d14beba89d29c450))
* **dashboard:** Sidebar overunning main content ([c27ce9d](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/c27ce9d6fef7b1061add050a1cdfd5faecac4e31))
* **dashboard:** similarity default columns ([f599df7](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/f599df7b6cd813e40e86072e7c20ca5080e388a0))
* **dashboard:** UX enhanced with biome lineage in sidebar ([12ad045](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/12ad045ba63644ad4e7a10ea3fd8e292f5e83991))
* **db models:** Ingestion pattern to include sequence records for 'discovery db' ([0324cbd](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/0324cbd0b2d2f4b8106fde6897973411e8fae8ee))
* **db models:** taxonomy to contigs; and add assembly types ([b900858](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/b90085886670dba06601c6b066f62dc47b3d1c09))
* **db/model:** improve unique constrains to biome and cds ([9efbf14](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/9efbf14ca0366af2faf008054eda32c60a4fd540))
* **DB:** add PGDATA to prevent break when redeploying ([69ed00f](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/69ed00feb458769f9b2313eb00a77927031cdc4e))
* **DB:** remove redundancy of ltree fields ([7127370](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/7127370ca519094de03d075049af8671ab572909))
* **deployments:** Unblock skaffold deploys on k8s clusters ([0a3ef2c](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/0a3ef2ce49f2ec1e813cdd04e05381e271a14e88))
* **dev site:** seed_discovery_data targets all models and fields ([1a05089](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/1a05089880173df9c46df6bf45885bcd02431180))
* **django:** Discovery dashboard correcly displayed ([5f2644c](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/5f2644cb7fd0bffe7cae8c6fb8a42d99538f1455))
* **EMBEDDINGS:** Manual DB migrations ([2130795](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/213079586c0d8d461a1ddb880b7ae5c2e31befaa))
* **ingestion pattern:** Include domain url handling ([8cef729](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/8cef7291bac95fcedd9d595fdb36ddcf0e8d9378))
* **ingestion pattern:** Include protein embedding loader ([b250e86](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/b250e860db76b803f59ce6595ab94a77eff8dcc6))
* **ingestion:** Ignore conflicts on duplicated unique constraints ([2a4f1bd](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/2a4f1bd4ccd32aca9e32460a2b88c13696f43edb))
* **keyword search:** Fix search pattern ([da25bb1](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/da25bb1eed2f210aae967093beef815cd8d42ff0))
* **loader:** Get_or_create instead of create on loaded regions ([5e88fd1](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/5e88fd17f7cfc16ac03dc0c42aef5fe9c9320f7e))
* **loader:** Ingnore conglicts on unique constraints ([32283d9](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/32283d937871a110c5a124f0cfa29ad89947ad6a))
* **loader:** Resolve domain aggregations ([948e334](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/948e334f8210d0e0040b861ce44c69d794bc8cd3))
* **LOADER:** Set max limit of csv filed to support sequnece loading ([69069e7](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/69069e72325bf42be8f198090636d33fe5e53f0d))
* **local deploy:** dont copy artifacts to local ([910900d](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/910900de3805568756c63bd9a2f4b467777be6a5))
* **quickstart slides:** correct blurring background ([d5e88eb](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/d5e88ebfcfa98519e37af0efe442a36ac6fdfa47))
* **scoring:** Amend data type for percentile calcs ([c6b03d6](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/c6b03d67754f69ec243843ac35ca152ad0726d58))
* **scoring:** Avoid collition of PFAM names ([adb911a](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/adb911a2b400b9b7086021716903fa592192013f))
* **search:** Fixed forms for keyword search ([f16afe0](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/f16afe023df67184cf6e1d41a0b4d3394b22da32))
* **seed_data:** Correct loading of discovery data to test accessioning pattern ([9222cb2](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/9222cb20f8615c9cb9a0481916e0c37c6e021c8c))


### Performance Improvements

* **bgc_aggregator:** Change esm model from 600M to 300M params ([448d36d](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/448d36defd11b09ab5efa55bf19dfcac04064cce))
* **django:** Redisign db models to scale with full data ([2e4e112](https://github.com/EBI-Metagenomics/bgc_data_portal/commit/2e4e112c0a72af1426f11574ef7ea543b0ca0673))
