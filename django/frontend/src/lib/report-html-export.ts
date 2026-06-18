/**
 * Client-side "Download HTML" for the Shortlist Report.
 *
 * Produces a single self-contained ``.html`` file that reproduces the report
 * — every table plus interactive Plotly charts — with the full ``plotly.js``
 * library inlined, so the saved file opens and stays interactive with **no
 * network access**. Charts are rebuilt deterministically from the report
 * payload (the same field mapping the React panels use), not snapshotted from
 * the DOM, so the export does not depend on render timing.
 *
 * The full ``plotly.js-dist-min`` build is used (the app's runtime bundle is
 * the *basic* dist, which lacks the ``sunburst`` trace the report relies on).
 * It is fetched lazily from our own origin at click time, so it never bloats
 * the main app chunk.
 */
import type {
  CategoryCount,
  DomainCompositionSummary,
  DomainGoslimMatrix,
  GcfDistributionEntry,
  LengthBucket,
  ReportAssemblyRow,
  ReportIbgcRow,
  ReportPayload,
  ReportScoreDistribution,
  SunburstNode,
} from "@/api/types";
import { colorByAncestorDepth } from "@/lib/sunburst-colors";
import { domainTokenSet, preferredDomainToken } from "@/lib/domains";
import { buildUpsetFigure } from "@/lib/upset";

interface PlotlyFigure {
  id: string;
  data: unknown[];
  layout: Record<string, unknown>;
}

const TIER_COLOR: Record<string, [number, number, number]> = {
  core: [16, 185, 129],
  variable: [245, 158, 11],
  rare: [148, 163, 184],
};
const TIER_LABEL: Record<string, string> = {
  core: "CORE",
  variable: "Variable",
  rare: "RARE",
};

// ── small helpers ────────────────────────────────────────────────────────────

function esc(v: unknown): string {
  if (v === null || v === undefined) return "—";
  return String(v)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function fmt(v: number | null | undefined, digits = 3): string {
  return v === null || v === undefined || Number.isNaN(v)
    ? "—"
    : v.toFixed(digits);
}

function num(v: number | null | undefined): string {
  return v === null || v === undefined ? "—" : String(v);
}

function cellBackground(rgb: [number, number, number], intensity: number): string {
  const i = Math.max(0.06, Math.min(1, intensity));
  const [r, g, b] = rgb;
  const mix = (x: number) => Math.round(255 - (255 - x) * i);
  return `rgb(${mix(r)}, ${mix(g)}, ${mix(b)})`;
}

// ── figure builders (mirror the React panels) ────────────────────────────────

function sunburstFigure(
  id: string,
  nodes: SunburstNode[],
  opts: { colorDepth?: number; unit?: string; height?: number } = {},
): PlotlyFigure {
  const { colorDepth, unit = "iBGC(s)", height = 320 } = opts;
  const marker =
    colorDepth !== undefined
      ? { colors: colorByAncestorDepth(nodes, colorDepth) }
      : undefined;
  return {
    id,
    data: [
      {
        type: "sunburst",
        ids: nodes.map((n) => n.id),
        labels: nodes.map((n) => n.label),
        parents: nodes.map((n) => n.parent),
        values: nodes.map((n) => n.count),
        branchvalues: "total",
        ...(marker ? { marker } : {}),
        hovertemplate: `<b>%{label}</b><br>%{value} ${unit}<extra></extra>`,
      },
    ],
    layout: { autosize: true, height, margin: { l: 8, r: 8, t: 8, b: 8 } },
  };
}

function barFigure(
  id: string,
  rows: CategoryCount[] | LengthBucket[],
  opts: { color?: string; labelKey?: "name" | "label"; horizontal?: boolean } = {},
): PlotlyFigure {
  const { color = "#6366f1", labelKey = "name", horizontal = false } = opts;
  const labels = rows.map(
    (r) => (r as unknown as Record<string, unknown>)[labelKey] as string,
  );
  const counts = rows.map((r) => r.count);
  const data = horizontal
    ? [{ type: "bar", orientation: "h", x: counts, y: labels, marker: { color } }]
    : [{ type: "bar", x: labels, y: counts, marker: { color } }];
  return {
    id,
    data,
    layout: {
      autosize: true,
      height: 240,
      margin: horizontal
        ? { l: 140, r: 16, t: 8, b: 30 }
        : { l: 40, r: 16, t: 8, b: 48 },
      yaxis: horizontal
        ? { automargin: true, tickfont: { size: 10 } }
        : { title: { text: "iBGCs" } },
    },
  };
}

function scoreFigure(
  id: string,
  distributions: ReportScoreDistribution[],
): PlotlyFigure {
  return {
    id,
    data: distributions.map((d) => ({
      type: "histogram",
      x: d.values,
      name: d.label,
      opacity: 0.6,
      xbins: { start: 0, end: 1, size: 0.05 },
    })),
    layout: {
      autosize: true,
      height: 240,
      margin: { l: 40, r: 16, t: 8, b: 30 },
      barmode: "overlay",
      xaxis: { title: { text: "Score" }, range: [0, 1] },
      yaxis: { title: { text: "iBGCs" } },
      legend: { orientation: "h", y: -0.2 },
    },
  };
}

function completenessFigure(id: string, rows: CategoryCount[]): PlotlyFigure {
  const COLORS: Record<string, string> = {
    Complete: "#10b981",
    Partial: "#94a3b8",
  };
  return {
    id,
    data: [
      {
        type: "bar",
        x: rows.map((r) => r.name),
        y: rows.map((r) => r.count),
        marker: { color: rows.map((r) => COLORS[r.name] ?? "#94a3b8") },
      },
    ],
    layout: {
      autosize: true,
      height: 240,
      margin: { l: 40, r: 16, t: 8, b: 30 },
      yaxis: { title: { text: "iBGCs" } },
    },
  };
}

function pieFigure(id: string, rows: CategoryCount[]): PlotlyFigure {
  return {
    id,
    data: [
      {
        type: "pie",
        labels: rows.map((r) => r.name),
        values: rows.map((r) => r.count),
        hole: 0.4,
        textinfo: "label+percent",
      },
    ],
    layout: {
      autosize: true,
      height: 240,
      margin: { l: 16, r: 16, t: 16, b: 16 },
      showlegend: false,
    },
  };
}

// ── HTML table / panel builders ──────────────────────────────────────────────

function ibgcTable(rows: ReportIbgcRow[]): string {
  const head = [
    "iBGC", "Assembly", "Collection", "Biome", "Size (kb)",
    "Novelty", "Dom. nov.", "GCF", "Class", "Sources", "Contig", "Start", "End",
    "Taxonomy",
  ];
  const body = rows
    .map((r) => {
      const badges =
        (r.is_validated ? ' <span class="badge">Validated</span>' : "") +
        (r.is_type_strain ? ' <span class="badge ts">Type Strain</span>' : "") +
        (r.is_partial ? ' <span class="badge out">partial</span>' : "");
      return `<tr>
        <td class="mono">${esc(r.label)}${badges}</td>
        <td class="mono">${esc(r.parent_assembly_accession)}</td>
        <td>${esc(r.collection)}</td>
        <td>${esc(r.biome_path || null)}</td>
        <td class="r">${fmt(r.size_kb, 1)}</td>
        <td class="r">${fmt(r.novelty_score)}</td>
        <td class="r">${fmt(r.domain_novelty)}</td>
        <td class="mono">${esc(r.classification_path || null)}</td>
        <td>${esc(r.bgc_class || null)}</td>
        <td>${esc((r.source_tools || []).join(", ") || null)}</td>
        <td class="mono">${esc(r.contig_accession)}</td>
        <td class="r">${num(r.start)}</td>
        <td class="r">${num(r.end)}</td>
        <td>${esc(r.taxonomy_path || null)}</td>
      </tr>`;
    })
    .join("");
  return table(head, body);
}

function assemblyTable(rows: ReportAssemblyRow[]): string {
  const head = [
    "Accession", "Collection", "Biome", "Size (Mb)",
    "iBGCs (shortlist)", "Taxonomy",
  ];
  const body = rows
    .map(
      (r) => `<tr>
        <td class="mono">${esc(r.accession)}${
        r.is_type_strain ? ' <span class="badge out">type strain</span>' : ""
      }</td>
        <td>${esc(r.source_name)}</td>
        <td>${esc(r.biome_path || null)}</td>
        <td class="r">${fmt(r.assembly_size_mb, 2)}</td>
        <td class="r b">${num(r.ibgcs_in_shortlist)}</td>
        <td>${esc(r.taxonomy_path || null)}</td>
      </tr>`,
    )
    .join("");
  return table(head, body);
}

function gcfDistributionTable(rows: GcfDistributionEntry[]): string {
  if (!rows.length) return "";
  const body = rows
    .map(
      (r) => `<tr>
        <td class="mono">${esc(r.classification_path)}</td>
        <td class="r">${num(r.ibgc_count)}</td>
        <td class="r">${(r.fraction * 100).toFixed(1)}%</td>
      </tr>`,
    )
    .join("");
  return `<h3>GCF distribution (table)</h3><div class="scroll-sm">${table(
    ["GCF", "iBGCs", "Fraction"],
    body,
  )}</div>`;
}

function domainCompositionPanel(c: DomainCompositionSummary): string {
  const total = c.total_unique || 1;
  const seg = (count: number, cls: string, label: string) => {
    const pct = (count / total) * 100;
    return `<div class="seg ${cls}" style="width:${pct}%">${
      pct > 6 ? `${count} ${label}` : ""
    }</div>`;
  };
  const bar = `<div class="compbar">${seg(c.core_count, "core", "core")}${seg(
    c.variable_count,
    "var",
    "var",
  )}${seg(c.rare_count, "rare", "rare")}</div>`;
  const body = c.rows
    .map((d) => {
      const [r, g, b] = TIER_COLOR[d.tier] ?? [148, 163, 184];
      // InterPro-entry-else-signature accession, linked to its InterPro page
      // (entry or member-DB) when one resolved server-side.
      const token = preferredDomainToken(d);
      const cell = d.domain_url
        ? `<a href="${esc(d.domain_url)}" target="_blank" rel="noopener noreferrer">${esc(
            token,
          )}</a>`
        : esc(token);
      return `<tr>
        <td class="mono nowrap">${cell}${
        d.domain_name ? ` <span class="muted">· ${esc(d.domain_name)}</span>` : ""
      }</td>
        <td class="r">${num(d.ibgc_count)}</td>
        <td class="r">${(d.fraction * 100).toFixed(1)}%</td>
        <td><span class="badge" style="background:rgb(${r},${g},${b})">${esc(
          d.tier,
        )}</span></td>
      </tr>`;
    })
    .join("");
  // Copy-as-set buttons (InterPro-else-signature, deduped, comma-joined),
  // wired to the clipboard by the inline script in the page body.
  const copyBtn = (tier: "core" | "variable" | "rare", label: string) => {
    const set = domainTokenSet(c.rows.filter((d) => d.tier === tier));
    const count =
      tier === "core"
        ? c.core_count
        : tier === "variable"
          ? c.variable_count
          : c.rare_count;
    return `<button class="copybtn" data-set="${esc(set)}"${
      count === 0 ? " disabled" : ""
    }>Copy ${label} (${count})</button>`;
  };
  const copyRow = `<div class="copybtns">${copyBtn(
    "core",
    "Core",
  )}${copyBtn("variable", "Variable")}${copyBtn("rare", "Rare")}</div>`;
  return `<h3>Domain composition</h3>${bar}${copyRow}<div class="scroll-sm">${table(
    ["Domain", "iBGCs", "Fraction", "Tier"],
    body,
  )}</div>`;
}

function goslimHeatmap(matrix: DomainGoslimMatrix): string {
  if (!matrix.categories.length) {
    return `<h3>Domain composition × GO slim</h3><p class="muted">No GO slim data available for this shortlist.</p>`;
  }
  const cellByKey = new Map<string, DomainGoslimMatrix["cells"][number]>();
  for (const c of matrix.cells) cellByKey.set(`${c.category}::${c.tier}`, c);
  const tierMax: Record<string, number> = {};
  for (const t of matrix.tiers) {
    let max = 0;
    for (const cat of matrix.categories) {
      const cell = cellByKey.get(`${cat}::${t}`);
      if (cell && cell.count > max) max = cell.count;
    }
    tierMax[t] = max || 1;
  }
  const headCells = matrix.categories
    .map((cat) => `<th class="vert"><span>${esc(cat)}</span></th>`)
    .join("");
  const rows = matrix.tiers
    .map((tier) => {
      const cells = matrix.categories
        .map((cat) => {
          const cell = cellByKey.get(`${cat}::${tier}`);
          const count = cell?.count ?? 0;
          const intensity = count / (tierMax[tier] || 1);
          const bg = cellBackground(
            TIER_COLOR[tier] ?? [148, 163, 184],
            intensity,
          );
          const tip = (cell?.domains ?? [])
            .slice(0, 20)
            .map((d) => `${d.domain_acc}${d.domain_name ? ` — ${d.domain_name}` : ""}`)
            .join("\n");
          return `<td class="hm" style="background:${bg}" title="${esc(
            `${cat} · ${TIER_LABEL[tier] ?? tier}\n${tip}`,
          )}">${count > 0 ? count : ""}</td>`;
        })
        .join("");
      return `<tr><th class="tier">${TIER_LABEL[tier] ?? tier}</th>${cells}</tr>`;
    })
    .join("");
  return `<h3>Domain composition × GO slim</h3>
    <div class="hm-wrap"><table class="heatmap"><thead><tr><th></th>${headCells}</tr></thead><tbody>${rows}</tbody></table></div>`;
}

function table(head: string[], body: string): string {
  return `<table><thead><tr>${head
    .map((h) => `<th>${esc(h)}</th>`)
    .join("")}</tr></thead><tbody>${body}</tbody></table>`;
}

function plotBlock(title: string, fig: PlotlyFigure | null): string {
  if (!fig) return "";
  return `<div class="panel"><h3>${esc(title)}</h3><div id="${
    fig.id
  }" class="plot"></div></div>`;
}

// ── assembly_stats accessors (loosely typed dict on the payload) ──────────────

function asNodes(v: unknown): SunburstNode[] {
  return Array.isArray(v) ? (v as SunburstNode[]) : [];
}
function asCounts(v: unknown): CategoryCount[] {
  return Array.isArray(v) ? (v as CategoryCount[]) : [];
}

// ── document assembly ────────────────────────────────────────────────────────

const STYLES = `
:root{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#0f172a}
body{margin:0;background:#f8fafc;padding:24px}
.wrap{max-width:1200px;margin:0 auto}
h1{font-size:24px;margin:0 0 4px}
h2{font-size:18px;margin:28px 0 8px;border-bottom:1px solid #e2e8f0;padding-bottom:4px}
h3{font-size:14px;margin:14px 0 6px}
.sub{color:#64748b;font-size:12px;margin:0 0 12px}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin:12px 0}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.panel{min-width:0}
.plot{width:100%}
table{border-collapse:collapse;width:100%;font-size:12px}
th,td{border-bottom:1px solid #eef2f7;padding:4px 8px;text-align:left;vertical-align:top}
th{color:#475569;font-weight:600;background:#f8fafc;position:sticky;top:0}
td.r,th.r{text-align:right}
td.b{font-weight:600}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.muted{color:#94a3b8}
.scroll{max-height:480px;overflow:auto;border:1px solid #e2e8f0;border-radius:6px}
.scroll-sm{max-height:320px;overflow:auto;border:1px solid #e2e8f0;border-radius:6px}
td.nowrap,th.nowrap{white-space:nowrap}
.copybtns{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0}
.copybtn{font-size:11px;padding:3px 8px;border:1px solid #cbd5e1;border-radius:4px;background:#fff;color:#334155;cursor:pointer}
.copybtn:hover:not(:disabled){background:#f1f5f9}
.copybtn:disabled{opacity:.5;cursor:default}
.copybtn.copied{background:#10b981;border-color:#10b981;color:#fff}
.badge{display:inline-block;font-size:10px;color:#fff;background:#6366f1;border-radius:4px;padding:1px 5px;margin-left:4px}
.badge.ts{background:#018786}
.badge.out{background:#94a3b8}
.compbar{display:flex;height:22px;width:100%;overflow:hidden;border:1px solid #e2e8f0;border-radius:4px;margin:6px 0}
.compbar .seg{font-size:10px;color:#fff;display:flex;align-items:center;justify-content:center;white-space:nowrap}
.seg.core{background:#10b981}.seg.var{background:#f59e0b}.seg.rare{background:#94a3b8}
.hm-wrap{overflow-x:auto}
table.heatmap td.hm{text-align:center;font-size:10px;min-width:32px}
table.heatmap th.vert{height:120px;white-space:nowrap}
table.heatmap th.vert span{writing-mode:vertical-rl;transform:rotate(180deg);font-size:10px;color:#64748b}
table.heatmap th.tier{text-align:right;font-size:10px}
.foot{color:#94a3b8;font-size:11px;margin-top:24px;text-align:center}
`;

function buildReportHtml(payload: ReportPayload, plotlySource: string): string {
  const figs: PlotlyFigure[] = [];
  const add = (f: PlotlyFigure | null): PlotlyFigure | null => {
    if (f) figs.push(f);
    return f;
  };

  // BGC stats panels.
  const gcfFig =
    payload.gcf_sunburst?.length
      ? add(sunburstFigure("fig-gcf", payload.gcf_sunburst, { height: 280 }))
      : null;
  const scoreFig = add(scoreFigure("fig-score", payload.score_distributions));
  const completeFig = add(
    completenessFigure("fig-complete", payload.completeness_bar),
  );
  const classFig = add(pieFigure("fig-class", payload.bgc_class_pie));
  const lengthFig = add(
    barFigure("fig-length", payload.length_histogram, {
      color: "#6366f1",
      labelKey: "label",
    }),
  );
  // Predictor distribution as an UpSet (iBGCs per predictor-tool combination).
  const upset = buildUpsetFigure(payload.ibgc_rows);
  const predictorFig = add(
    upset
      ? {
          id: "fig-predictor",
          data: upset.figure.data,
          layout: upset.figure.layout,
        }
      : null,
  );
  const sourceFig = add(
    barFigure("fig-source", payload.source_distribution, {
      color: "#a855f7",
      horizontal: true,
    }),
  );

  // Biome & taxonomy.
  const biomeFig = payload.biome_sunburst?.length
    ? add(sunburstFigure("fig-biome", payload.biome_sunburst, { colorDepth: 3 }))
    : null;
  const taxFig = payload.taxonomy_sunburst?.length
    ? add(
        sunburstFigure("fig-tax", payload.taxonomy_sunburst, { colorDepth: 1 }),
      )
    : null;

  // Assembly stats.
  const stats = payload.assembly_stats || {};
  const asmBiome = asNodes((stats as Record<string, unknown>).biome_sunburst);
  const asmTax = asNodes((stats as Record<string, unknown>).taxonomy_sunburst);
  const asmSrc = asCounts(
    (stats as Record<string, unknown>).source_distribution,
  );
  const asmBiomeFig = asmBiome.length
    ? add(
        sunburstFigure("fig-asm-biome", asmBiome, {
          colorDepth: 3,
          unit: "assembly(ies)",
        }),
      )
    : null;
  const asmTaxFig = asmTax.length
    ? add(
        sunburstFigure("fig-asm-tax", asmTax, {
          colorDepth: 1,
          unit: "assembly(ies)",
        }),
      )
    : null;
  const asmSrcFig = asmSrc.length ? add(pieFigure("fig-asm-src", asmSrc)) : null;

  const figJson = JSON.stringify(
    figs.map((f) => ({ id: f.id, data: f.data, layout: f.layout })),
  ).replace(/</g, "\\u003c");
  const safePlotly = plotlySource.replace(/<\/(script)/gi, "<\\/$1");

  const assemblyStatsSection =
    asmBiomeFig || asmTaxFig || asmSrcFig
      ? `<div class="card"><h2>Assembly Stats</h2><div class="grid">
          ${plotBlock("Biome distribution (coloured by depth 3)", asmBiomeFig)}
          ${plotBlock("Taxonomy distribution (coloured by phylum)", asmTaxFig)}
          ${plotBlock("Source distribution (per assembly)", asmSrcFig)}
        </div></div>`
      : "";

  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BGC Shortlist Report</title>
<style>${STYLES}</style>
</head><body><div class="wrap">
  <h1>BGC Shortlist Report</h1>
  <p class="sub">${payload.n_ibgcs} iBGC(s) · ${
    payload.n_assemblies
  } assembly(ies) · generated ${esc(payload.generated_at)} · token ${esc(
    payload.token,
  )}</p>

  <div class="card"><h2>iBGC Results</h2><div class="scroll">${ibgcTable(
    payload.ibgc_rows,
  )}</div></div>

  <div class="card"><h2>BGC Stats</h2>
    <div class="grid">
      <div class="panel">${domainCompositionPanel(
        payload.domain_composition,
      )}</div>
      <div class="panel">${goslimHeatmap(payload.domain_goslim_matrix)}</div>
      ${plotBlock("GCF distribution", gcfFig)}
      ${plotBlock("Score distributions", scoreFig)}
      ${plotBlock("Completeness", completeFig)}
      ${plotBlock("BGC classes", classFig)}
      ${plotBlock("Length distribution", lengthFig)}
      ${plotBlock("Predictor distribution", predictorFig)}
      ${plotBlock("Source distribution (iBGCs per collection)", sourceFig)}
    </div>
    <div class="panel">${gcfDistributionTable(payload.gcf_distribution)}</div>
  </div>

  <div class="card"><h2>Biome &amp; Taxonomy</h2><div class="grid">
    ${plotBlock("Biome (coloured by depth 3)", biomeFig)}
    ${plotBlock("Taxonomy (coloured by phylum)", taxFig)}
  </div></div>

  <div class="card"><h2>Assembly Roster</h2><div class="scroll">${assemblyTable(
    payload.assembly_rows,
  )}</div></div>

  ${assemblyStatsSection}

  <p class="foot">Self-contained report · interactive charts powered by Plotly (inlined)</p>
</div>
<script>${safePlotly}</script>
<script>
(function(){
  var FIGS = JSON.parse(${JSON.stringify(figJson)});
  var cfg = {displayModeBar:false, responsive:true};
  FIGS.forEach(function(f){
    var el = document.getElementById(f.id);
    if (el && window.Plotly) { window.Plotly.newPlot(el, f.data, f.layout, cfg); }
  });
})();
</script>
<script>
(function(){
  // Copy-as-set buttons in the Domain composition panel.
  document.querySelectorAll('.copybtn').forEach(function(btn){
    btn.addEventListener('click', function(){
      var text = btn.getAttribute('data-set') || '';
      if (!text) return;
      var label = btn.textContent;
      var done = function(){
        btn.classList.add('copied');
        btn.textContent = 'Copied!';
        setTimeout(function(){ btn.classList.remove('copied'); btn.textContent = label; }, 1200);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function(){ window.prompt('Copy:', text); });
      } else {
        window.prompt('Copy:', text);
      }
    });
  });
})();
</script>
</body></html>`;
}

let cachedPlotlySource: string | null = null;

async function loadPlotlySource(): Promise<string> {
  if (cachedPlotlySource) return cachedPlotlySource;
  // Vite serves the dist file from our own origin; ``?url`` keeps the ~3.5MB
  // library out of the main app chunk (loaded only on first HTML export).
  const mod = (await import("plotly.js-dist-min/plotly.min.js?url")) as {
    default: string;
  };
  const resp = await fetch(mod.default);
  if (!resp.ok) throw new Error(`Failed to load Plotly (${resp.status})`);
  cachedPlotlySource = await resp.text();
  return cachedPlotlySource;
}

/**
 * Build the self-contained HTML report for ``payload`` and trigger a browser
 * download. Resolves once the download has been initiated.
 */
export async function downloadReportHtml(payload: ReportPayload): Promise<void> {
  const plotlySource = await loadPlotlySource();
  const html = buildReportHtml(payload, plotlySource);
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `report_${payload.token}.html`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Revoke on the next tick so the download has a chance to start.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
