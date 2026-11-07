/**
 * The single Plotly runtime for the dashboard.
 *
 * ``react-plotly.js``'s default entry imports the full ``plotly.js`` source
 * package (an undeclared peer); building the component through its factory
 * with ``plotly.js-dist-min`` instead means the app ships exactly one Plotly
 * build — the same file ``report-html-export.ts`` inlines into the offline
 * HTML report. Every ``<Plot>`` in the app must import from here.
 */
import createPlotlyComponent from "react-plotly.js/factory";
import Plotly from "plotly.js-dist-min";

export const Plot = createPlotlyComponent(Plotly);
