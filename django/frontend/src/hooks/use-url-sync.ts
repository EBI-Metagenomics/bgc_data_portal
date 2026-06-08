import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { useFilterStore } from "@/stores/filter-store";
import { useSelectionStore } from "@/stores/selection-store";
import {
  snapshotFiltersToApplied,
  useDiscoveryStore,
} from "@/stores/discovery-store";

export function useUrlSync() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialized = useRef(false);

  // Hydrate stores from URL on mount
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    const sourceNamesParam = searchParams.get("source_names");
    if (sourceNamesParam) {
      useFilterStore.getState().setSourceNames(sourceNamesParam.split(",").filter(Boolean));
    }

    const detectorToolsParam = searchParams.get("detector_tools");
    if (detectorToolsParam) {
      useFilterStore.getState().setDetectorTools(detectorToolsParam.split(",").filter(Boolean));
    }

    const bgcClass = searchParams.get("bgc_class");
    if (bgcClass) useFilterStore.getState().setBgcClass(bgcClass);

    const search = searchParams.get("search");
    if (search) useFilterStore.getState().setSearch(search);

    const domainText = searchParams.get("domain_text");
    if (domainText) useFilterStore.getState().setDomainText(domainText);

    const taxonomyPath = searchParams.get("taxonomy_path");
    if (taxonomyPath) useFilterStore.getState().setTaxonomyPath(taxonomyPath);

    const assemblyType = searchParams.get("assembly_type");
    if (assemblyType) useFilterStore.getState().setAssemblyType(assemblyType);

    const biomeLineage = searchParams.get("biome_lineage");
    if (biomeLineage) useFilterStore.getState().setBiomeLineage(biomeLineage);

    const accession = searchParams.get("accession");
    if (accession) useFilterStore.getState().setAccession(accession);

    const assemblyId = searchParams.get("assembly");
    if (assemblyId) {
      useSelectionStore.getState().setActiveAssemblyId(Number(assemblyId));
    }

    // Auto-run query when redirected from landing page keyword search.
    // The v2 dashboard's roster + maps key off ``discovery-store``'s
    // ``appliedFilters`` (populated by the Run Query button), NOT the
    // filter-chip store we just hydrated above. So commit the same snapshot
    // here — otherwise the chips show the term but nothing ever fetches.
    const autoRun = searchParams.get("auto_run");
    if (autoRun === "true") {
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

  // Write store changes to URL
  useEffect(() => {
    const unsubscribers = [
      useFilterStore.subscribe((state) => {
        updateUrl("source_names", state.sourceNames.join(","));
        updateUrl("detector_tools", state.detectorTools.join(","));
        updateUrl("bgc_class", state.bgcClass);
        updateUrl("search", state.search);
        updateUrl("taxonomy_path", state.taxonomyPath);
        updateUrl("assembly_type", state.assemblyType);
        updateUrl("biome_lineage", state.biomeLineage);
        updateUrl("accession", state.accession);
      }),
      useSelectionStore.subscribe((state) => {
        updateUrl("assembly", state.activeAssemblyId?.toString() ?? "");
      }),
    ];

    return () => unsubscribers.forEach((unsub) => unsub());
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();

  function updateUrl(key: string, value: string) {
    clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (value) next.set(key, value);
          else next.delete(key);
          return next;
        },
        { replace: true }
      );
    }, 300);
  }
}
