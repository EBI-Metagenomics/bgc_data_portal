import { useQuery } from "@tanstack/react-query";
import { mintIbgcIdset } from "@/api/ibgcs";

/**
 * Budget (in characters of the ``ibgc_ids`` CSV) below which the allow-list
 * rides inline on the GET request and above which it is swapped for a
 * server-cached ``ibgc_ids_token``.
 *
 * gunicorn's default ``--limit-request-line`` is 4094 bytes for the *whole*
 * request line (path + every query param). We keep a generous headroom for the
 * path and the other filter params, so anything past ~1.5 KB of ids alone gets
 * tokenised. Small queries stay inline — no extra round-trip, no cache
 * dependency — exactly as before this fix.
 */
const IBGC_IDS_INLINE_BUDGET = 1500;

export interface IbgcIdsetParam {
  /** Spread onto the roster/map/count fetch params. Either ``{ibgc_ids}`` (CSV,
   *  small sets) or ``{ibgc_ids_token}`` (large sets), or empty (no scope). */
  param: { ibgc_ids?: string; ibgc_ids_token?: string };
  /** False while a token mint is in flight — gate dependent queries on this so
   *  they don't fire an unscoped fetch before the token resolves. */
  ready: boolean;
}

/**
 * Resolve an ordered iBGC allow-list into a URL-param fragment, tokenising it
 * server-side when it would overflow the HTTP request line.
 *
 * Keyed on the joined id string, so react-query dedupes the mint across the
 * roster/UMAP/Variables/count consumers (one POST per unique ordering) and a
 * re-sort that changes the order mints a fresh token on demand. The mint is
 * idempotent server-side (token = hash of the ordered ids).
 */
export function useIbgcIdsetParam(ids: number[] | null): IbgcIdsetParam {
  const csv = ids && ids.length > 0 ? ids.join(",") : "";
  const needsToken = csv.length > IBGC_IDS_INLINE_BUDGET;

  const { data: token } = useQuery({
    queryKey: ["ibgc-idset", csv],
    queryFn: () => mintIbgcIdset(ids as number[]).then((r) => r.token),
    enabled: needsToken,
    staleTime: Infinity,
    gcTime: Infinity,
  });

  if (!csv) return { param: {}, ready: true };
  if (!needsToken) return { param: { ibgc_ids: csv }, ready: true };
  if (token) return { param: { ibgc_ids_token: token }, ready: true };
  return { param: {}, ready: false };
}
