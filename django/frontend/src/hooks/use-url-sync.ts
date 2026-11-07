import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { useFilterStore, type FilterValues } from "@/stores/filter-store";
import {
  snapshotFiltersToApplied,
  useDiscoveryStore,
} from "@/stores/discovery-store";

/** Query params from retired features (ChemOnt class filter, SMILES chemical
 *  search). Hydration below is table-driven so these are never read; they
 *  are stripped on mount so old shared links don't keep re-sharing them. */
const LEGACY_URL_PARAMS = [
  "chemont_ids",
  "smiles",
  "similarity_threshold",
  "np_classes",
];

/**
 * One filter ↔ URL mapping. ``encode`` turns the store value into the URL
 * string (``""`` = omit the param); ``decode`` turns a present URL string back
 * into the store value. Both directions of the sync are driven by this table,
 * so a filter is either shareable in both directions or not at all.
 */
interface UrlSyncEntry<K extends keyof FilterValues> {
  storeKey: K;
  urlKey: string;
  encode: (value: FilterValues[K]) => string;
  decode: (raw: string) => FilterValues[K];
}

const csv = {
  encode: (v: string[]) => v.join(","),
  decode: (raw: string) => raw.split(",").filter(Boolean),
};
const text = {
  encode: (v: string) => v,
  decode: (raw: string) => raw,
};
const kb = {
  encode: (v: number | null) => (v == null ? "" : String(v)),
  decode: (raw: string): number | null => {
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  },
};

function entry<K extends keyof FilterValues>(
  storeKey: K,
  urlKey: string,
  codec: Pick<UrlSyncEntry<K>, "encode" | "decode">,
): UrlSyncEntry<K> {
  return { storeKey, urlKey, ...codec };
}

/** URL param names mirror the iBGC API query params (``search`` → ``organism``
 *  is the historical exception, kept so existing shared links keep working). */
const URL_SYNC_TABLE = [
  entry("sourceNames", "source_names", csv),
  entry("detectorTools", "detector_tools", csv),
  entry("bgcClass", "bgc_class", text),
  entry("search", "search", text),
  entry("domainText", "domain_text", text),
  entry("taxonomyPath", "taxonomy_path", text),
  entry("gcfPath", "leaf_path_prefix", text),
  entry("npcTerms", "npc_terms", csv),
  // Default (true) is omitted; only the non-default ``false`` is shared.
  entry("npcConfidentOnly", "npc_confident", {
    encode: (v: boolean) => (v ? "" : "false"),
    decode: (raw: string) => raw !== "false",
  }),
  entry("assemblyType", "assembly_type", text),
  entry("biomeLineage", "biome_lineage", text),
  entry("accession", "accession", text),
  entry("assemblyIds", "assembly_ids", text),
  entry("minLengthKb", "min_length_kb", kb),
  entry("maxLengthKb", "max_length_kb", kb),
] as const;

/** Filter values present in ``params`` (absent params leave the default). */
function decodeFilters(params: URLSearchParams): Partial<FilterValues> {
  const next: Partial<FilterValues> = {};
  for (const e of URL_SYNC_TABLE) {
    const raw = params.get(e.urlKey);
    if (raw === null || raw === "") continue;
    // The table is heterogeneous; each entry's decode matches its storeKey.
    (next as Record<string, unknown>)[e.storeKey] = e.decode(raw);
  }
  return next;
}

/** Write every synced filter into ``params`` (deleting the empty ones). */
function encodeFilters(state: FilterValues, params: URLSearchParams): void {
  for (const e of URL_SYNC_TABLE) {
    const encoded = (e.encode as (v: FilterValues[typeof e.storeKey]) => string)(
      state[e.storeKey],
    );
    if (encoded) params.set(e.urlKey, encoded);
    else params.delete(e.urlKey);
  }
}

const URL_WRITE_DEBOUNCE_MS = 300;

export function useUrlSync() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialized = useRef(false);
  // ``setSearchParams`` changes identity with the URL; keep the latest in a
  // ref so the store subscription below is set up once.
  const setSearchParamsRef = useRef(setSearchParams);
  setSearchParamsRef.current = setSearchParams;

  // Hydrate the filter store from the URL on mount.
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    if (LEGACY_URL_PARAMS.some((k) => searchParams.has(k))) {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          LEGACY_URL_PARAMS.forEach((k) => next.delete(k));
          return next;
        },
        { replace: true }
      );
    }

    useFilterStore.setState(decodeFilters(searchParams));

    // Auto-run query when redirected from landing page keyword search.
    // The v2 dashboard's roster + maps key off ``discovery-store``'s
    // ``appliedFilters`` (populated by the Run Query button), NOT the
    // filter-chip store we just hydrated above. So commit the same snapshot
    // here — otherwise the chips show the term but nothing ever fetches.
    if (searchParams.get("auto_run") === "true") {
      useDiscoveryStore.getState().setAppliedFilters(snapshotFiltersToApplied());
      // Remove auto_run from URL so refreshing doesn't re-trigger
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.delete("auto_run");
          return next;
        },
        { replace: true }
      );
    }
  }, [searchParams, setSearchParams]);

  // Mirror filter-store changes into the URL (debounced, one write for all
  // params) so a shared link reproduces the full filter state.
  useEffect(() => {
    let timeout: ReturnType<typeof setTimeout> | undefined;
    const unsubscribe = useFilterStore.subscribe((state) => {
      clearTimeout(timeout);
      timeout = setTimeout(() => {
        setSearchParamsRef.current(
          (prev) => {
            const next = new URLSearchParams(prev);
            encodeFilters(state, next);
            return next;
          },
          { replace: true }
        );
      }, URL_WRITE_DEBOUNCE_MS);
    });
    return () => {
      clearTimeout(timeout);
      unsubscribe();
    };
  }, []);
}
