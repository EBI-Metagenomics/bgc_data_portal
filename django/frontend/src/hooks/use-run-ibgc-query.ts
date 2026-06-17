import { useState } from "react";
import {
  postIbgcDomainQueryScores,
  postIbgcArchitectureQueryScores,
  fetchIbgcSequenceQueryScores,
  fetchIbgcChemicalQueryScores,
} from "@/api/ibgcs";
import { postSequenceQuery, postChemicalQuery } from "@/api/queries";
import type { QueryScoresResponse } from "@/api/types";
import { useQueryStore } from "@/stores/query-store";
import {
  snapshotFiltersToApplied,
  useDiscoveryStore,
} from "@/stores/discovery-store";
import { ApiError } from "@/api/client";
import { toast } from "sonner";

/**
 * Soft cap on how many iBGCs we propagate from a scored query into the
 * dashboard's roster + maps. Mirrors the server-side
 * ``DASHBOARD_RESULT_CAP`` so the maps don't bother downsampling further.
 * When more than this many iBGCs come back, we keep the top-N by score —
 * that's what users actually care about for similarity-driven queries.
 */
const QUERY_RESULT_CAP = 5_000;

/**
 * Hook that drives the Run Query button in the v2 dashboard.
 *
 * On every press it (a) snapshots the current filter-chip values into
 * ``discovery-store.appliedFilters`` — that's what the roster/maps key
 * off, so toggling chips alone does NOT refetch — and (b) resolves any
 * active advanced searches (domain conditions + sequence) into an iBGC id
 * allow-list intersected with the filters.
 *
 * The chemical query path is not surfaced in v2 yet — it lives in P1.5b's
 * follow-up.
 */
export function useRunIbgcQuery() {
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const domainConditions = useQueryStore((s) => s.domainConditions);
  const domainMode = useQueryStore((s) => s.domainMode);
  const architectureText = useQueryStore((s) => s.domainArchitectureText);
  const architectureWeight = useQueryStore((s) => s.architectureWeight);
  const sequenceQuery = useQueryStore((s) => s.sequenceQuery);
  const sequenceMinBitscore = useQueryStore((s) => s.sequenceMinBitscore);
  const sequenceMinPident = useQueryStore((s) => s.sequenceMinPident);
  const sequenceMinQcov = useQueryStore((s) => s.sequenceMinQcov);
  const smilesQuery = useQueryStore((s) => s.smilesQuery);
  const similarityThreshold = useQueryStore((s) => s.similarityThreshold);

  const setQueryResult = useDiscoveryStore((s) => s.setQueryResult);
  const setAppliedFilters = useDiscoveryStore((s) => s.setAppliedFilters);

  const run = async () => {
    setError(null);

    // Snapshot chip values → applied filters every time Run Query is
    // pressed, regardless of whether an advanced query is also active.
    // Shared with the landing-page keyword redirect via
    // ``snapshotFiltersToApplied`` so both paths stay in lockstep.
    setAppliedFilters(snapshotFiltersToApplied());

    // Active "domain" surface depends on which mode the user picked.
    // In architecture mode we treat the textarea as the active input,
    // not the chip conditions (the UI hides the chips while in arch mode).
    const archAccs = architectureText
      .split(/[,\s]+/)
      .map((t) => t.trim())
      .filter((t) => t.length > 0);
    const archActive = domainMode === "architecture" && archAccs.length > 0;
    const booleanActive =
      domainMode !== "architecture" && domainConditions.length > 0;

    if (
      !booleanActive &&
      !archActive &&
      !sequenceQuery.trim() &&
      !smilesQuery.trim()
    ) {
      // Filters-only run: clear any prior advanced-query allow-list so the
      // roster reflects the new filter snapshot.
      setQueryResult(null, null, null, null, null, null);
      toast.success("Filters applied");
      return;
    }

    setIsRunning(true);
    const abortController = new AbortController();
    try {
      const idSets: Set<number>[] = [];
      const similarities: Record<number, number> = {};
      const bestHitProtein: Record<number, string> = {};
      const pident: Record<number, number> = {};
      const qcoverage: Record<number, number> = {};
      // Per-branch (total_matched, capped) so the roster banner can report
      // how many matched vs the 5k cap. Branches run domain → arch →
      // sequence → chemical, so the sequence bitscore overwrites a domain
      // hit's 1.0 when both hit the same iBGC (preferred — more informative).
      const branchStats: { total: number; capped: boolean }[] = [];
      const collect = (resp: QueryScoresResponse) => {
        idSets.push(new Set(resp.items.map((r) => r.id)));
        for (const item of resp.items) {
          if (item.similarity_score != null) {
            similarities[item.id] = item.similarity_score;
          }
          if (item.best_hit_protein_id) {
            bestHitProtein[item.id] = item.best_hit_protein_id;
          }
          if (item.best_pident != null) pident[item.id] = item.best_pident;
          if (item.best_qcoverage != null) {
            qcoverage[item.id] = item.best_qcoverage;
          }
        }
        branchStats.push({ total: resp.total_matched, capped: resp.capped });
      };

      // ── Domain branch ─────────────────────────────────────────────────
      if (booleanActive) {
        collect(
          await postIbgcDomainQueryScores(
            {
              domains: domainConditions.map((c) => ({
                acc: c.acc,
                required: c.required,
              })),
              logic: domainMode === "or" ? "or" : "and",
            },
            QUERY_RESULT_CAP,
          ),
        );
      }

      // ── Architecture branch (composite-Dice) ──────────────────────────
      if (archActive) {
        collect(
          await postIbgcArchitectureQueryScores(
            {
              architecture: archAccs,
              weight: architectureWeight,
              k: QUERY_RESULT_CAP,
            },
            QUERY_RESULT_CAP,
          ),
        );
      }

      // ── Sequence branch ───────────────────────────────────────────────
      if (sequenceQuery.trim()) {
        const accepted = await postSequenceQuery({
          sequence: sequenceQuery,
          min_bitscore: sequenceMinBitscore,
          min_pident: sequenceMinPident,
          min_qcov: sequenceMinQcov,
        });
        // Poll with backoff until the task is ready. Budget matches the
        // Celery result TTL (CELERY_RESULT_EXPIRES, default 1h): polling
        // longer is pointless because AsyncResult silently returns
        // PENDING for evicted task ids. Past the slow-notice threshold
        // (~2 min) we surface a cancellable "still searching" toast so
        // the user can let go without keeping the tab open.
        collect(await pollSequenceTask(accepted.task_id, abortController));
      }

      // ── Chemical branch (ChemOnt via ClassyFire) ──────────────────────
      if (smilesQuery.trim()) {
        const accepted = await postChemicalQuery({
          smiles: smilesQuery,
          similarity_threshold: similarityThreshold,
        });
        // Novel compounds absent from ClassyFire's cache classify slowly, so
        // reuse the same poll-with-backoff path as sequence search.
        collect(await pollChemicalTask(accepted.task_id, abortController));
      }

      // Intersect across active branches; if only one branch ran, that's
      // already the result. (Mirrors legacy intersection semantics.) Each
      // branch is already ranked best-first and server-capped at 5k, so the
      // single-branch allow-list stays in score order.
      let intersection: number[] = [];
      if (idSets.length === 1) {
        intersection = [...idSets[0]!];
      } else if (idSets.length > 1) {
        const first = idSets[0]!;
        intersection = [...first].filter((id) =>
          idSets.slice(1).every((s) => s.has(id)),
        );
      }

      // Match count + capped flag for the roster banner. Single branch: take
      // its server-reported total. Multi-branch intersection: the true total
      // is unknowable when any branch was itself capped, so report null +
      // capped so the banner stays honest.
      const anyBranchCapped = branchStats.some((b) => b.capped);
      let totalMatched: number | null;
      let capped: boolean;
      if (branchStats.length === 1) {
        totalMatched = branchStats[0]!.total;
        capped = branchStats[0]!.capped;
      } else {
        totalMatched = anyBranchCapped ? null : intersection.length;
        capped = anyBranchCapped;
      }

      // Defensive top-K clip (each branch is already ≤ cap server-side, so an
      // intersection can't exceed it — kept so the allow-list can never blow
      // past the cap if that ever changes).
      if (intersection.length > QUERY_RESULT_CAP) {
        intersection.sort((a, b) => {
          const sa = similarities[a] ?? -Infinity;
          const sb = similarities[b] ?? -Infinity;
          return sb - sa;
        });
        intersection = intersection.slice(0, QUERY_RESULT_CAP);
        capped = true;
      }

      // When sequence search is one of the branches, label the result
      // set as "sequence" so the roster shows bitscore + best-hit
      // protein columns. Domain-only runs keep the standard similarity
      // column. Mixed runs prefer the sequence label since that path
      // carries the more useful per-iBGC metadata.
      const source:
        | "sequence"
        | "chemical"
        | "domain"
        | "domain_architecture"
        | null = sequenceQuery.trim()
        ? "sequence"
        : smilesQuery.trim()
          ? "chemical"
          : archActive
            ? "domain_architecture"
            : booleanActive
              ? "domain"
              : null;
      setQueryResult(
        intersection,
        similarities,
        source,
        source === "sequence" ? bestHitProtein : null,
        source === "sequence" ? pident : null,
        source === "sequence" ? qcoverage : null,
        totalMatched,
        capped,
      );
      toast.success(`Query returned ${intersection.length} iBGC(s)`);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") {
        toast.info("Search cancelled");
      } else {
        const err = e as Error;
        setError(err);
        toast.error(
          e instanceof ApiError
            ? `Query failed (${e.status}): ${e.message}`
            : `Query failed: ${err.message}`,
        );
      }
    } finally {
      setIsRunning(false);
    }
  };

  return { run, isRunning, error };
}

// 1h matches CELERY_RESULT_EXPIRES — past that the result is evicted
// and AsyncResult would return PENDING forever, so capping polling
// here is the actionable boundary, not a UX guess.
const SEQUENCE_POLL_HARD_CAP_MS = 60 * 60 * 1000;
const SEQUENCE_POLL_SLOW_NOTICE_MS = 2 * 60 * 1000;
const SEQUENCE_POLL_INITIAL_MS = 1000;
const SEQUENCE_POLL_MAX_MS = 5000;

type StatusFetcher = (taskId: string) => Promise<QueryScoresResponse>;

/**
 * Poll an async iBGC-roster search task with backoff until it's ready.
 *
 * The backend returns 503 while the task is PENDING (so the dashboard stays
 * responsive) and 200 when ready. We back off the poll interval to avoid
 * hammering the API during multi-minute runs but stay responsive for short
 * ones — the first hit lands at 1s. Past the slow-notice threshold (~2 min) a
 * cancellable "still searching" toast lets the user let go.
 */
async function pollRosterTask(
  taskId: string,
  abortController: AbortController,
  fetchStatus: StatusFetcher,
  messages: { slow: string; timeout: string },
) {
  const start = Date.now();
  let waitMs = SEQUENCE_POLL_INITIAL_MS;
  let slowNoticeShown = false;
  let slowToastId: string | number | undefined;

  const dismissSlowToast = () => {
    if (slowToastId !== undefined) {
      toast.dismiss(slowToastId);
      slowToastId = undefined;
    }
  };

  while (Date.now() - start < SEQUENCE_POLL_HARD_CAP_MS) {
    if (abortController.signal.aborted) {
      dismissSlowToast();
      throw new DOMException("Search cancelled", "AbortError");
    }
    try {
      const result = await fetchStatus(taskId);
      dismissSlowToast();
      return result;
    } catch (e) {
      if (e instanceof ApiError && e.status === 503) {
        if (
          !slowNoticeShown &&
          Date.now() - start > SEQUENCE_POLL_SLOW_NOTICE_MS
        ) {
          slowNoticeShown = true;
          slowToastId = toast.message(messages.slow, {
            duration: Infinity,
            action: {
              label: "Cancel",
              onClick: () => abortController.abort(),
            },
          });
        }
        await new Promise((r) => setTimeout(r, waitMs));
        waitMs = Math.min(SEQUENCE_POLL_MAX_MS, Math.round(waitMs * 1.5));
        continue;
      }
      dismissSlowToast();
      throw e;
    }
  }
  dismissSlowToast();
  throw new Error(messages.timeout);
}

function pollSequenceTask(taskId: string, abortController: AbortController) {
  return pollRosterTask(
    taskId,
    abortController,
    (id) => fetchIbgcSequenceQueryScores(id, QUERY_RESULT_CAP),
    {
      slow: "Still searching… large protein queries can take several minutes. Keep this tab open.",
      timeout:
        "Sequence search exceeded the 1-hour result lifetime — retry with a shorter sequence or tighter filters.",
    },
  );
}

function pollChemicalTask(taskId: string, abortController: AbortController) {
  return pollRosterTask(
    taskId,
    abortController,
    (id) => fetchIbgcChemicalQueryScores(id, QUERY_RESULT_CAP),
    {
      slow: "Still classifying… novel structures can take a minute to classify in ClassyFire. Keep this tab open.",
      timeout:
        "Chemical search exceeded the 1-hour result lifetime — retry, or check that ClassyFire is reachable.",
    },
  );
}
