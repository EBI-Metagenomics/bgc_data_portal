import { useState } from "react";
import {
  postCombinedQuery,
  fetchCombinedQueryScores,
} from "@/api/queries";
import type {
  CombinedQueryCriterion,
  CombinedScoresResponse,
  CriterionScore,
} from "@/api/types";
import { useQueryStore } from "@/stores/query-store";
import {
  snapshotFiltersToApplied,
  useDiscoveryStore,
  type SearchSource,
} from "@/stores/discovery-store";
import { ApiError } from "@/api/client";
import { toast } from "sonner";

/**
 * Soft cap on how many iBGCs we propagate from a scored query into the
 * dashboard's roster + maps. Mirrors the server-side ``DASHBOARD_RESULT_CAP``.
 */
const QUERY_RESULT_CAP = 5_000;

/**
 * Hook that drives the Run Query button in the v2 dashboard.
 *
 * On every press it (a) snapshots the current filter-chip values into
 * ``discovery-store.appliedFilters`` — that's what the roster/maps key off, so
 * toggling chips alone does NOT refetch — and (b) resolves any active scoring
 * searches (domain conditions, architecture, sequence, chemical) into a single
 * combined multi-criterion query whose criteria are AND-intersected server-side.
 *
 * The combined query returns one score column per criterion (keyed by the
 * criterion's stable id). Those are stored in ``resultCriteria`` +
 * ``resultScoresByCriterion`` for the per-criterion roster columns / map axes;
 * the legacy single-similarity maps are back-filled from the dominant criterion
 * so the existing roster/Variables-map views keep working during the migration.
 */
export function useRunIbgcQuery() {
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const domainText = useQueryStore((s) => s.domainText);
  const domainThreshold = useQueryStore((s) => s.domainThreshold);
  const domainLogic = useQueryStore((s) => s.domainLogic);
  const architectureText = useQueryStore((s) => s.domainArchitectureText);
  const architectureWeight = useQueryStore((s) => s.architectureWeight);
  const architectureThreshold = useQueryStore((s) => s.architectureThreshold);
  const sequenceQuery = useQueryStore((s) => s.sequenceQuery);
  const sequenceMinBitscore = useQueryStore((s) => s.sequenceMinBitscore);
  const sequenceMinPident = useQueryStore((s) => s.sequenceMinPident);
  const sequenceMinQcov = useQueryStore((s) => s.sequenceMinQcov);
  const smilesQuery = useQueryStore((s) => s.smilesQuery);
  const similarityThreshold = useQueryStore((s) => s.similarityThreshold);

  const setQueryResult = useDiscoveryStore((s) => s.setQueryResult);
  const setCombinedResult = useDiscoveryStore((s) => s.setCombinedResult);
  const setAppliedFilters = useDiscoveryStore((s) => s.setAppliedFilters);

  const run = async () => {
    setError(null);

    // Snapshot chip values → applied filters every time Run Query is pressed.
    // Shared with the landing-page keyword redirect via
    // ``snapshotFiltersToApplied`` so both paths stay in lockstep. The roster
    // and maps apply these filters at fetch time; the combined query carries
    // only the scoring criteria, so filters narrow the result downstream.
    setAppliedFilters(snapshotFiltersToApplied());

    const archAccs = architectureText
      .split(/[,\s]+/)
      .map((t) => t.trim())
      .filter((t) => t.length > 0);
    const archActive = archAccs.length > 0;
    const booleanActive = domainText.trim().length > 0;
    const sequenceActive = sequenceQuery.trim().length > 0;
    const chemicalActive = smilesQuery.trim().length > 0;

    // Each active surface becomes one criterion. The current query builder
    // supports a single instance per type, so the type doubles as the stable
    // per-instance id; when the UI gains multi-instance criteria these become
    // client-generated unique ids.
    const criteria: CombinedQueryCriterion[] = [];
    if (booleanActive) {
      criteria.push({
        id: "domain",
        type: "domain",
        params: {
          domains_text: domainText,
          logic: domainLogic,
          threshold: domainThreshold,
        },
      });
    }
    if (archActive) {
      criteria.push({
        id: "architecture",
        type: "architecture",
        params: {
          architecture: archAccs,
          weight: architectureWeight,
          threshold: architectureThreshold,
          k: QUERY_RESULT_CAP,
        },
      });
    }
    if (sequenceActive) {
      criteria.push({
        id: "sequence",
        type: "sequence",
        params: {
          sequence: sequenceQuery,
          min_bitscore: sequenceMinBitscore,
          min_pident: sequenceMinPident,
          min_qcov: sequenceMinQcov,
        },
      });
    }
    if (chemicalActive) {
      criteria.push({
        id: "chemical",
        type: "chemical",
        params: {
          smiles: smilesQuery,
          similarity_threshold: similarityThreshold,
        },
      });
    }

    if (criteria.length === 0) {
      // Filters-only run: clear any prior scored-query allow-list so the roster
      // reflects the new filter snapshot.
      setQueryResult(null, null, null, null, null, null);
      setCombinedResult(null, null);
      toast.success("Filters applied");
      return;
    }

    setIsRunning(true);
    const abortController = new AbortController();
    try {
      const accepted = await postCombinedQuery({ criteria });
      const scores = await pollCombinedScores(
        accepted.task_id,
        abortController,
      );

      const ids = scores.items.map((r) => r.id);

      // Per-criterion score maps: criterion id → (iBGC id → score payload).
      const scoresByCriterion: Record<
        string,
        Record<number, CriterionScore>
      > = {};
      for (const col of scores.criteria) scoresByCriterion[col.id] = {};
      for (const row of scores.items) {
        for (const [cid, sc] of Object.entries(row.scores)) {
          (scoresByCriterion[cid] ??= {})[row.id] = sc;
        }
      }
      setCombinedResult(scores.criteria, scoresByCriterion);

      // Legacy back-fill: the existing roster/maps read a single similarity
      // map + sequence sub-metric maps + a ``searchSource`` label. Derive them
      // from the dominant criterion (sequence > chemical > architecture >
      // domain) so those views keep working until per-criterion columns land.
      const source: SearchSource = sequenceActive
        ? "sequence"
        : chemicalActive
          ? "chemical"
          : archActive
            ? "domain_architecture"
            : booleanActive
              ? "domain"
              : null;
      const sourceType =
        source === "domain_architecture" ? "architecture" : source;
      const sourceCol =
        scores.criteria.find((c) => c.type === sourceType) ??
        scores.criteria[0];

      const similarities: Record<number, number> = {};
      const bestHitProtein: Record<number, string> = {};
      const pident: Record<number, number> = {};
      const qcoverage: Record<number, number> = {};
      if (sourceCol) {
        const map = scoresByCriterion[sourceCol.id] ?? {};
        for (const id of ids) {
          const sc = map[id];
          if (sc?.value != null) similarities[id] = sc.value;
          if (sourceCol.type === "sequence") {
            if (sc?.pident != null) pident[id] = sc.pident;
            if (sc?.qcoverage != null) qcoverage[id] = sc.qcoverage;
            if (sc?.best_hit_protein_id) {
              bestHitProtein[id] = sc.best_hit_protein_id;
            }
          }
        }
      }

      setQueryResult(
        ids,
        similarities,
        source,
        source === "sequence" ? bestHitProtein : null,
        source === "sequence" ? pident : null,
        source === "sequence" ? qcoverage : null,
        scores.total_matched,
        scores.capped,
      );
      toast.success(`Query returned ${ids.length} iBGC(s)`);
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

// 1h matches the task result lifetime — past that the result is evicted and the
// poll would 503 forever, so capping polling here is the actionable boundary.
const POLL_HARD_CAP_MS = 60 * 60 * 1000;
const POLL_SLOW_NOTICE_MS = 2 * 60 * 1000;
const POLL_INITIAL_MS = 1000;
const POLL_MAX_MS = 5000;

/**
 * Poll an async task with backoff until it's ready.
 *
 * The backend returns 503 while the task is PENDING and 200 when ready. We back
 * off the poll interval to stay responsive for short runs (first hit at 1s)
 * without hammering the API during multi-minute ones. Past the slow-notice
 * threshold (~2 min) a cancellable "still searching" toast lets the user let go.
 */
async function pollTask<T>(
  taskId: string,
  abortController: AbortController,
  fetchStatus: (taskId: string) => Promise<T>,
  messages: { slow: string; timeout: string },
): Promise<T> {
  const start = Date.now();
  let waitMs = POLL_INITIAL_MS;
  let slowNoticeShown = false;
  let slowToastId: string | number | undefined;

  const dismissSlowToast = () => {
    if (slowToastId !== undefined) {
      toast.dismiss(slowToastId);
      slowToastId = undefined;
    }
  };

  while (Date.now() - start < POLL_HARD_CAP_MS) {
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
        if (!slowNoticeShown && Date.now() - start > POLL_SLOW_NOTICE_MS) {
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
        waitMs = Math.min(POLL_MAX_MS, Math.round(waitMs * 1.5));
        continue;
      }
      dismissSlowToast();
      throw e;
    }
  }
  dismissSlowToast();
  throw new Error(messages.timeout);
}

function pollCombinedScores(
  taskId: string,
  abortController: AbortController,
): Promise<CombinedScoresResponse> {
  return pollTask(
    taskId,
    abortController,
    (id) => fetchCombinedQueryScores(id),
    {
      slow: "Still searching… sequence and chemical criteria can take several minutes. Keep this tab open.",
      timeout:
        "Query exceeded the 1-hour result lifetime — retry with a shorter sequence or tighter filters.",
    },
  );
}
