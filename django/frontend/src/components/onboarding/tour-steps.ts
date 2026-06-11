import type Shepherd from "shepherd.js";

type StepDef = Shepherd.Step.StepOptions;

const skipBtn = {
  text: "Skip tour",
  action: function (this: Shepherd.Tour) {
    this.cancel();
  },
  secondary: true,
};
const backBtn = {
  text: "Back",
  action: function (this: Shepherd.Tour) {
    this.back();
  },
  secondary: true,
};
const nextBtn = {
  text: "Next",
  action: function (this: Shepherd.Tour) {
    this.next();
  },
};
const finishBtn = {
  text: "Finish",
  action: function (this: Shepherd.Tour) {
    this.complete();
  },
};

/**
 * Six-step walkthrough of the v2 iBGC-first dashboard, following the real
 * query → triage → shortlist → export flow. Each step anchors to a live
 * `data-tour` target rendered by `IbgcDashboard`.
 */
export function getTourSteps(): StepDef[] {
  return [
    {
      id: "filters",
      text: `<strong>1. Build your query</strong>
<p>Start here. Add <b>filter chips</b> to narrow the catalogue by taxonomy, biome, BGC class, chemical class, or <b>GCF</b> — a gene cluster family, i.e. a group of related clusters. The advanced chips search by <b>protein domain</b>, <b>sequence similarity</b>, or <b>chemical structure</b>. Combine as many as you need.</p>`,
      attachTo: { element: '[data-tour="filters"]', on: "bottom" },
      buttons: [skipBtn, nextBtn],
    },
    {
      id: "load-asset",
      text: `<strong>2. Compare your own assembly</strong>
<p>Have your own data? <b>Load Asset</b> uploads a packaged assembly analysis (<code>.tar.gz</code>) and projects its clusters into the catalogue — tagged <b>SUBMITTED</b> — so you can compare them against the database alongside everything else. <a href="/docs/" target="_blank" rel="noopener noreferrer">Full documentation →</a></p>`,
      attachTo: { element: '[data-tour="load-asset"]', on: "bottom" },
      buttons: [backBtn, nextBtn],
    },
    {
      id: "run-query",
      text: `<strong>3. Run the query</strong>
<p>Nothing loads until you press <b>Run Query</b>. The badges above show the size of the full catalogue; once you run, a banner reports how many <b>iBGCs</b> match your filters. An iBGC is an <i>integrated BGC</i> — overlapping cluster predictions consolidated into one candidate.</p>`,
      attachTo: { element: '[data-tour="run-query"]', on: "bottom" },
      buttons: [backBtn, nextBtn],
    },
    {
      id: "results-tabs",
      text: `<strong>4. Browse the results</strong>
<p>Matches appear three ways: the <b>BGC roster</b> (a sortable table — sort by <b>Novelty</b> to surface candidates least like known validated clusters), the <b>Variables map</b> (plot any two metrics against each other), and <b>UMAP</b> (similar iBGCs cluster together). Points are coloured by GCF.</p>`,
      attachTo: { element: '[data-tour="results-tabs"]', on: "bottom" },
      buttons: [backBtn, nextBtn],
    },
    {
      id: "reference-detail",
      text: `<strong>5. Set a reference & find similar</strong>
<p><b>Right-click</b> an iBGC for actions. <b>Set as reference</b> pins it to this panel so you can compare other clusters against it. <b>Find similar iBGCs</b> re-runs the search around it to expand your candidates. <b>Add to shortlist</b> collects it for export.</p>`,
      attachTo: { element: '[data-tour="reference-detail"]', on: "left" },
      buttons: [backBtn, nextBtn],
    },
    {
      id: "compare-detail",
      text: `<strong>6. Inspect an iBGC</strong>
<p><b>Left-click</b> any iBGC — in the table or on a map — to load it into the <b>Compare</b> panel here. You'll see its size, source predictions, GCF classification, predicted compounds, and its <b>novelty</b> and <b>domain novelty</b> scores (how unique its protein domains are within its family).</p>`,
      attachTo: { element: '[data-tour="compare-detail"]', on: "left" },
      buttons: [backBtn, nextBtn],
    },
    {
      id: "protein-info",
      text: `<strong>7. Inspect a protein</strong>
<p>Click any <b>gene (CDS)</b> in either detail card to load its protein here — its <b>protein-domain annotations</b> and full, copyable sequence.</p>`,
      attachTo: { element: '[data-tour="protein-info"]', on: "top" },
      buttons: [backBtn, nextBtn],
    },
    {
      id: "shortlist",
      text: `<strong>8. Shortlist & export</strong>
<p>Pinned iBGCs collect in the <b>iBGC Shortlist</b>. Open it and <b>Generate Report</b> to materialise your selection, then download <b>GenBank (.gbk)</b> files, assembly tables, or JSON — ready for your downstream workflows. This is your main finding.</p>`,
      attachTo: { element: '[data-tour="shortlist"]', on: "bottom" },
      buttons: [backBtn, finishBtn],
    },
  ];
}
