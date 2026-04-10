import type Shepherd from "shepherd.js";
import { useModeStore } from "@/stores/mode-store";

function waitForElement(
  selector: string,
  timeout = 2000
): Promise<Element | null> {
  return new Promise((resolve) => {
    const el = document.querySelector(selector);
    if (el) return resolve(el);
    const observer = new MutationObserver(() => {
      const found = document.querySelector(selector);
      if (found) {
        observer.disconnect();
        resolve(found);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
    setTimeout(() => {
      observer.disconnect();
      resolve(null);
    }, timeout);
  });
}

function switchMode(mode: "explore" | "query" | "assess") {
  useModeStore.getState().setMode(mode);
  return waitForElement(`[data-tour]`, 500);
}

/** Scroll a sidebar element into view within its scroll container before Shepherd positions the popover */
function scrollSidebarTo(selector: string): () => Promise<unknown> {
  return () =>
    new Promise<void>((resolve) => {
      const el = document.querySelector(selector);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        setTimeout(resolve, 250);
      } else {
        resolve();
      }
    });
}

type StepDef = Shepherd.Step.StepOptions;

export function getTourSteps(): StepDef[] {
  return [
    {
      id: "mode-tabs",
      text: "<strong>Mode tabs</strong><p>Switch between the three exploration modes here. Your filters and shortlists are preserved when you switch.</p>",
      attachTo: { element: '[data-tour="mode-tabs"]', on: "bottom" },
      beforeShowPromise: () => switchMode("explore") as Promise<unknown>,
      buttons: [
        { text: "Skip tour", action: function (this: Shepherd.Tour) { this.cancel(); }, secondary: true },
        { text: "Next", action: function (this: Shepherd.Tour) { this.next(); } },
      ],
    },
    {
      id: "type-strain-toggle",
      text: "<strong>Type Strain filter</strong><p>Enable this to see only purchasable reference organisms from culture collections like DSMZ and ATCC.</p>",
      attachTo: { element: '[data-tour="type-strain-toggle"]', on: "right" },
      beforeShowPromise: scrollSidebarTo('[data-tour="type-strain-toggle"]'),
      buttons: [
        { text: "Back", action: function (this: Shepherd.Tour) { this.back(); }, secondary: true },
        { text: "Next", action: function (this: Shepherd.Tour) { this.next(); } },
      ],
    },
    {
      id: "assembly-type-filter",
      text: "<strong>Assembly Type</strong><p>Filter by genome (single organism), metagenome (environmental community DNA), or sub-genomic region.</p>",
      attachTo: { element: '[data-tour="assembly-type-filter"]', on: "right" },
      beforeShowPromise: scrollSidebarTo('[data-tour="assembly-type-filter"]'),
      buttons: [
        { text: "Back", action: function (this: Shepherd.Tour) { this.back(); }, secondary: true },
        { text: "Next", action: function (this: Shepherd.Tour) { this.next(); } },
      ],
    },
    {
      id: "taxonomy-filter",
      text: "<strong>Taxonomy tree</strong><p>Narrow results by any NCBI taxonomic rank. Counts update as you apply other filters.</p>",
      attachTo: { element: '[data-tour="taxonomy-filter"]', on: "right" },
      beforeShowPromise: scrollSidebarTo('[data-tour="taxonomy-filter"]'),
      buttons: [
        { text: "Back", action: function (this: Shepherd.Tour) { this.back(); }, secondary: true },
        { text: "Next", action: function (this: Shepherd.Tour) { this.next(); } },
      ],
    },
    {
      id: "bgc-class-filter",
      text: '<strong>BGC Class</strong><p>Filter by biosynthetic machinery type \u2014 e.g. Polyketide, NRP, or RiPP. These reflect how the compound is built, not its chemical structure.</p>',
      attachTo: { element: '[data-tour="bgc-class-filter"]', on: "right" },
      beforeShowPromise: scrollSidebarTo('[data-tour="bgc-class-filter"]'),
      buttons: [
        { text: "Back", action: function (this: Shepherd.Tour) { this.back(); }, secondary: true },
        { text: "Next", action: function (this: Shepherd.Tour) { this.next(); } },
      ],
    },
    {
      id: "chemont-filter",
      text: '<strong>ChemOnt Chemical Class</strong><p>Filter by predicted chemical product class. Independent of BGC class \u2014 a Polyketide BGC can produce a macrolide, a phenol, or something entirely novel.</p>',
      attachTo: { element: '[data-tour="chemont-filter"]', on: "right" },
      beforeShowPromise: scrollSidebarTo('[data-tour="chemont-filter"]'),
      buttons: [
        { text: "Back", action: function (this: Shepherd.Tour) { this.back(); }, secondary: true },
        { text: "Next", action: function (this: Shepherd.Tour) { this.next(); } },
      ],
    },
    {
      id: "biome-lineage",
      text: "<strong>Biome Lineage</strong><p>For metagenome assemblies: filter by the environment of origin using the GOLD ecosystem classification, e.g. root:Environmental:Terrestrial:Soil.</p>",
      attachTo: { element: '[data-tour="biome-lineage"]', on: "right" },
      beforeShowPromise: scrollSidebarTo('[data-tour="biome-lineage"]'),
      buttons: [
        { text: "Back", action: function (this: Shepherd.Tour) { this.back(); }, secondary: true },
        { text: "Next", action: function (this: Shepherd.Tour) { this.next(); } },
      ],
    },
    {
      id: "assembly-roster",
      text: "<strong>Assembly Roster</strong><p>All assemblies matching your filters. Click a row to explore its BGCs. Right-click for actions like Evaluate or Add to Shortlist.</p>",
      attachTo: { element: '[data-tour="assembly-roster"]', on: "left" },
      buttons: [
        { text: "Back", action: function (this: Shepherd.Tour) { this.back(); }, secondary: true },
        { text: "Next", action: function (this: Shepherd.Tour) { this.next(); } },
      ],
    },
    {
      id: "assembly-space-map",
      text: "<strong>Assembly Space Map</strong><p>Each point is an assembly. Choose axes from Diversity, Novelty, Density, or Taxonomic Novelty. Click a point to select it.</p>",
      attachTo: { element: '[data-tour="assembly-space-map"]', on: "left" },
      buttons: [
        { text: "Back", action: function (this: Shepherd.Tour) { this.back(); }, secondary: true },
        { text: "Next", action: function (this: Shepherd.Tour) { this.next(); } },
      ],
    },
    {
      id: "bgc-roster",
      text: "<strong>BGC Roster</strong><p>BGCs from the selected or shortlisted assemblies. Sort by Novelty or Domain Novelty. Click a row for the full detail panel.</p>",
      attachTo: { element: '[data-tour="bgc-roster"]', on: "top" },
      buttons: [
        { text: "Back", action: function (this: Shepherd.Tour) { this.back(); }, secondary: true },
        { text: "Next", action: function (this: Shepherd.Tour) { this.next(); } },
      ],
    },
    {
      id: "assembly-shortlist",
      text: "<strong>Assembly Shortlist</strong><p>Pin up to 20 assemblies as you explore. Export as CSV for purchase decisions. Persists across mode switches.</p>",
      attachTo: { element: '[data-tour="assembly-shortlist"]', on: "right" },
      beforeShowPromise: scrollSidebarTo('[data-tour="assembly-shortlist"]'),
      buttons: [
        { text: "Back", action: function (this: Shepherd.Tour) { this.back(); }, secondary: true },
        { text: "Next", action: function (this: Shepherd.Tour) { this.next(); } },
      ],
    },
    {
      id: "bgc-shortlist",
      text: "<strong>BGC Shortlist</strong><p>Pin up to 20 BGCs. Export as GenBank (.gbk) files ready for cloning or synthesis workflows.</p>",
      attachTo: { element: '[data-tour="bgc-shortlist"]', on: "right" },
      beforeShowPromise: scrollSidebarTo('[data-tour="bgc-shortlist"]'),
      buttons: [
        { text: "Back", action: function (this: Shepherd.Tour) { this.back(); }, secondary: true },
        { text: "Next", action: function (this: Shepherd.Tour) { this.next(); } },
      ],
    },
    {
      id: "help-button",
      text: "<strong>Need help?</strong><p>Click this button anytime to relaunch the welcome guide or tour.</p>",
      attachTo: { element: '[data-tour="help-button"]', on: "bottom" },
      buttons: [
        { text: "Finish", action: function (this: Shepherd.Tour) { this.complete(); } },
      ],
    },
  ];
}
