/**
 * The React app is served under ``<basePath>/dashboard/`` (Django catches
 * everything matching ``^dashboard/.*$`` and serves the SPA, with an
 * optional prefix surfaced via ``<meta name="base-path">``). React
 * Router's ``BrowserRouter`` has its ``basename`` set to that value in
 * ``main.tsx``, so in-app ``<Link>`` / ``navigate()`` calls work without
 * any prefix.
 *
 * For *cross-tab* navigation we go through ``window.open`` / ``window.location``,
 * which bypass React Router and need the full prefix. Use ``buildAppUrl``
 * (or the ``APP_BASE`` constant) instead of hard-coding ``/foo`` paths.
 */

const basePath =
  document.querySelector('meta[name="base-path"]')?.getAttribute("content") ??
  "";

export const APP_BASE = `${basePath}/dashboard`;

/**
 * Build a URL to a Quarto docs page. The docs are served under
 * ``<basePath>/docs/`` (a sibling of ``/dashboard/``, NOT under it), so this
 * must prefix the configured base-path — a bare ``/docs/…`` resolves against
 * the domain root and breaks behind a reverse-proxy prefix (e.g. prod's
 * ``/finn-srv/mgnify-bgcs``). Pass a page path like ``"scores-metrics.html#x"``
 * or ``""`` for the docs index.
 */
export function buildDocsUrl(page = ""): string {
  const clean = page.replace(/^\/+/, "").replace(/^docs\//, "");
  return `${basePath}/docs/${clean}`;
}

/**
 * Build an absolute in-app URL.
 *
 *   buildAppUrl("/report", { token: "abc" })
 *   //=> "/dashboard/report?token=abc"
 *   //   (or with a configured base-path: "/portal/dashboard/report?token=abc")
 */
export function buildAppUrl(
  path: string,
  query?: Record<string, string | number | boolean | undefined | null>,
): string {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  let url = `${APP_BASE}${cleanPath}`;
  if (query) {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== "") {
        params.set(k, String(v));
      }
    }
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }
  return url;
}
