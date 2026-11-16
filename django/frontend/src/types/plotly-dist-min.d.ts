// ``plotly.js-dist-min`` ships no typings; the bundle exposes the same API as
// ``plotly.js`` (typed by ``@types/plotly.js``, pulled in via
// ``@types/react-plotly.js``). The UMD file's ``module.exports`` is the Plotly
// object, so it is consumed as a default import.
declare module "plotly.js-dist-min" {
  import * as Plotly from "plotly.js";

  export default Plotly;
}
