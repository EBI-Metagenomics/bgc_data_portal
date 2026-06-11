"""Classify iBGC natural-product SMILES into ChemOnt via ClassyFire.

For every iBGC that has an :class:`IbgcNaturalProduct` with a SMILES, this runs
ClassyFire on the structure and stores the resulting ChemOnt classes in
:class:`IbgcChemOnt`. Those structure-derived classes are then pooled alongside
the gene-based CHAMOIS predictions (``CdsChemOnt``) by the chemical-similarity
search and the ChemOnt IC computation — so a query for a known compound matches
the cluster that actually makes it.

Classifications are cached in Redis by InChIKey under the same key the search
task uses (``chemont:classify:{inchikey}``), so each unique structure is sent to
ClassyFire at most once and the search reuses the result.

Idempotent: re-running only classifies SMILES not already covered (unless
``--reclassify``). After a run, re-run ``recompute_all_scores`` so the ChemOnt
IC reflects the new terms.
"""

from __future__ import annotations

import time

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = (
        "Classify iBGC natural-product SMILES into ChemOnt (ClassyFire) → IbgcChemOnt"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Only process this many iBGCs (for testing).",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=5.0,
            help="Seconds to wait after each ClassyFire submission (cache misses "
            "only) to respect rate limits. Default 5.",
        )
        parser.add_argument(
            "--reclassify",
            action="store_true",
            help="Re-run even for iBGCs that already have structure_chemont rows.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Classify and report, but do not write IbgcChemOnt rows.",
        )

    def handle(self, *args, **opts):
        from common_core.chemont import classyfire_client as cf
        from common_core.chemont.ontology import get_ontology

        from discovery.models import IbgcChemOnt, IbgcNaturalProduct

        ont = get_ontology()
        ttl = getattr(settings, "CHEMONT_CLASSIFY_CACHE_TTL", 60 * 60 * 24 * 30)
        base_url = getattr(settings, "CLASSYFIRE_URL", cf.DEFAULT_BASE_URL)
        timeout = getattr(settings, "CLASSYFIRE_TIMEOUT", 30.0)
        poll_timeout = getattr(settings, "CLASSYFIRE_POLL_TIMEOUT", 90.0)

        # iBGCs with at least one NP SMILES. Skip those already classified
        # unless --reclassify.
        nps = (
            IbgcNaturalProduct.objects.exclude(smiles="")
            .values_list("ibgc_id", "smiles")
            .order_by("ibgc_id")
        )
        if not opts["reclassify"]:
            done = set(IbgcChemOnt.objects.values_list("ibgc_id", flat=True).distinct())
        else:
            done = set()

        # Group SMILES per iBGC (an iBGC may claim several compounds).
        per_ibgc: dict[int, set[str]] = {}
        for ibgc_id, smiles in nps:
            if ibgc_id in done:
                continue
            per_ibgc.setdefault(ibgc_id, set()).add(smiles)

        ibgc_ids = sorted(per_ibgc)
        if opts["limit"]:
            ibgc_ids = ibgc_ids[: opts["limit"]]

        self.stdout.write(
            f"{len(ibgc_ids)} iBGC(s) with SMILES to classify "
            f"({'reclassify' if opts['reclassify'] else 'new only'})."
        )

        classified, rows_written, failures = 0, 0, 0
        for ibgc_id in ibgc_ids:
            terms: dict[str, str] = {}
            inchikey_for_ibgc = ""
            for smiles in sorted(per_ibgc[ibgc_id]):
                try:
                    cids, inchikey = self._classify_cached(
                        cf, smiles, base_url, timeout, poll_timeout, ttl, opts["sleep"]
                    )
                except cf.ClassyFireUnavailable as exc:
                    failures += 1
                    self.stderr.write(
                        self.style.WARNING(f"iBGC {ibgc_id}: ClassyFire failed: {exc}")
                    )
                    continue
                if inchikey:
                    inchikey_for_ibgc = inchikey
                for cid in cids:
                    term = ont.get_term(cid)
                    terms[cid] = term.name if term else ""

            if not terms:
                continue
            classified += 1

            if opts["dry_run"]:
                self.stdout.write(
                    f"iBGC {ibgc_id}: {len(terms)} ChemOnt terms (dry-run)"
                )
                continue

            with transaction.atomic():
                objs = [
                    IbgcChemOnt(
                        ibgc_id=ibgc_id,
                        chemont_id=cid,
                        chemont_name=name,
                        inchikey=inchikey_for_ibgc,
                    )
                    for cid, name in terms.items()
                ]
                created = IbgcChemOnt.objects.bulk_create(objs, ignore_conflicts=True)
                rows_written += len(created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Classified {classified} iBGC(s), wrote {rows_written} ChemOnt rows, "
                f"{failures} ClassyFire failure(s)."
            )
        )
        if classified and not opts["dry_run"]:
            self.stdout.write(
                "Next: run `recompute_all_scores` so ChemOnt IC includes the new terms."
            )

    def _classify_cached(self, cf, smiles, base_url, timeout, poll_timeout, ttl, sleep):
        """Classify a SMILES, reusing the search task's InChIKey Redis cache.

        Returns ``(chemont_ids, inchikey)``. A cache hit (or ClassyFire's own
        entity cache) avoids a fresh submission; only genuine submissions sleep.
        """
        inchikey = cf.smiles_to_inchikey(smiles)
        if inchikey is None:
            return [], ""
        cache_key = f"chemont:classify:{inchikey}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached, inchikey

        result = cf.classify(
            smiles, base_url=base_url, timeout=timeout, poll_timeout=poll_timeout
        )
        cids = result.chemont_ids if result else []
        cache.set(cache_key, cids, ttl)
        if sleep:
            time.sleep(sleep)  # rate-limit courtesy after a real submission/poll
        return cids, inchikey
