"""Unit tests for the in-memory cBGC assigner.

CbgcAssigner owns the create / extend / merge decision per incoming
source BGC prediction. Tests confirm:

  * **create** — first prediction on a contig mints a new cBGC and a
    fresh registry row.
  * **extend** — overlapping single neighbour widens the existing cBGC
    and re-syncs its registry coords without reassigning the accession.
  * **merge** — two pre-existing cBGCs bridged by a new prediction
    collapse to the lowest-PK survivor; absorbed accessions land in
    ``AccessionAlias`` and resolve to the survivor.
  * Disjointness within a contig (the exclusion constraint must hold
    after the assigner runs).
  * ``prediction_accession`` follows ``MGYB-XXXXXX.<TOOL>.<NN>`` and the
    NN counter is monotonic per (cbgc, detector).
"""

from __future__ import annotations

import pytest
from discovery.models import (
    AccessionAlias,
    AccessionRegistry,
    ConsensusBgc,
)
from discovery.services.ingestion.cbgc_assigner import CbgcAssigner
from tests.factories.discovery_models import (
    ConsensusBgcFactory,
    DashboardContigFactory,
    DashboardDetectorFactory,
    SourceBgcPredictionFactory,
)


@pytest.fixture
def contig(db):
    return DashboardContigFactory()


@pytest.fixture
def detector(db):
    return DashboardDetectorFactory(tool="antiSMASH", tool_name_code="ANT")


@pytest.fixture
def assigner():
    return CbgcAssigner()


# ── create ────────────────────────────────────────────────────────────────────


class TestCreate:
    def test_first_prediction_mints_cbgc(self, contig, detector, assigner):
        cbgc_id, bgc_num, pred_acc = assigner.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=1000,
            end=11_000,
            detector_id=detector.id,
            tool_code=detector.tool_name_code,
        )
        assert bgc_num == 1
        cbgc = ConsensusBgc.objects.get(id=cbgc_id)
        assert cbgc.bgc_range.lower == 1000
        assert cbgc.bgc_range.upper == 11_001  # half-open
        assert pred_acc == f"{cbgc.accession}.ANT.01"

    def test_registry_row_minted_alongside(self, contig, detector, assigner):
        cbgc_id, *_ = assigner.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=1000,
            end=11_000,
            detector_id=detector.id,
            tool_code=detector.tool_name_code,
        )
        cbgc = ConsensusBgc.objects.get(id=cbgc_id)
        registry = AccessionRegistry.objects.get(accession=cbgc.accession)
        assert registry.current_cbgc_id == cbgc_id
        assert registry.start_pos == 1000
        assert registry.end_pos == 11_000


# ── extend ────────────────────────────────────────────────────────────────────


class TestExtend:
    def test_overlap_widens_cbgc(self, contig, detector, assigner):
        cbgc_id_a, *_ = assigner.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=1000,
            end=5_000,
            detector_id=detector.id,
            tool_code=detector.tool_name_code,
        )
        cbgc_id_b, _, pred_acc_b = assigner.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=4_500,
            end=10_000,
            detector_id=detector.id,
            tool_code=detector.tool_name_code,
        )
        assert cbgc_id_a == cbgc_id_b
        cbgc = ConsensusBgc.objects.get(id=cbgc_id_a)
        assert cbgc.bgc_range.lower == 1000
        assert cbgc.bgc_range.upper == 10_001
        # bgc_number increments per detector within the same cBGC.
        assert pred_acc_b == f"{cbgc.accession}.ANT.02"

    def test_registry_coords_track_extension(self, contig, detector, assigner):
        cbgc_id, *_ = assigner.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=1000,
            end=5_000,
            detector_id=detector.id,
            tool_code=detector.tool_name_code,
        )
        assigner.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=4_500,
            end=10_000,
            detector_id=detector.id,
            tool_code=detector.tool_name_code,
        )
        cbgc = ConsensusBgc.objects.get(id=cbgc_id)
        registry = AccessionRegistry.objects.get(accession=cbgc.accession)
        assert registry.start_pos == 1000
        assert registry.end_pos == 10_000

    def test_subsumed_prediction_does_not_widen(self, contig, detector, assigner):
        # Second prediction sits entirely inside the first: range stays put.
        cbgc_id, *_ = assigner.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=1000,
            end=10_000,
            detector_id=detector.id,
            tool_code=detector.tool_name_code,
        )
        assigner.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=4_000,
            end=6_000,
            detector_id=detector.id,
            tool_code=detector.tool_name_code,
        )
        cbgc = ConsensusBgc.objects.get(id=cbgc_id)
        assert cbgc.bgc_range.lower == 1000
        assert cbgc.bgc_range.upper == 10_001


# ── merge ─────────────────────────────────────────────────────────────────────


class TestMerge:
    def test_bridge_prediction_merges_two_cbgcs(self, contig, assigner):
        det1 = DashboardDetectorFactory(name="t1", tool="t1", version="1")
        det2 = DashboardDetectorFactory(name="t2", tool="t2", version="1")
        # Two disjoint cBGCs on the same contig, each via a different detector
        # so the per-detector exclusion constraint doesn't fire.
        cbgc_a, *_ = assigner.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=1000,
            end=4_000,
            detector_id=det1.id,
            tool_code="AAA",
        )
        cbgc_b, *_ = assigner.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=8_000,
            end=12_000,
            detector_id=det2.id,
            tool_code="BBB",
        )
        assert cbgc_a != cbgc_b
        accession_b_before = ConsensusBgc.objects.get(id=cbgc_b).accession

        # Bridging prediction spans both.
        det3 = DashboardDetectorFactory(name="t3", tool="t3", version="1")
        cbgc_bridge, *_ = assigner.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=3_500,
            end=9_000,
            detector_id=det3.id,
            tool_code="CCC",
        )

        # Survivor is the lowest-PK pre-existing cBGC.
        survivor_id = min(cbgc_a, cbgc_b)
        absorbed_id = max(cbgc_a, cbgc_b)
        assert cbgc_bridge == survivor_id

        survivor = ConsensusBgc.objects.get(id=survivor_id)
        assert survivor.bgc_range.lower == 1000
        assert survivor.bgc_range.upper == 12_001
        # Absorbed row is gone.
        assert not ConsensusBgc.objects.filter(id=absorbed_id).exists()
        # Absorbed accession lives on as an alias of the survivor's registry.
        absorbed_accession = (
            accession_b_before
            if cbgc_b == absorbed_id
            else ConsensusBgc.objects.filter(id=absorbed_id)
            .values_list("accession", flat=True)
            .first()
            or accession_b_before
        )
        registry = AccessionRegistry.objects.get(accession=survivor.accession)
        aliases = list(
            AccessionAlias.objects.filter(registry=registry).values_list(
                "alias_accession",
                flat=True,
            )
        )
        assert absorbed_accession in aliases


class TestPreMergeCallback:
    """The ``on_pre_merge`` hook lets a batching loader flush its in-flight
    ``SourceBgcPrediction`` rows before ``_merge`` deletes the cBGCs those
    rows still reference in memory. Without it, the loader's next
    ``bulk_create`` commit trips the source-BGC → cBGC FK constraint (this
    is the marine_v2.0 cycle-2026-07-23 failure the fix targets)."""

    def test_callback_fires_before_absorbed_delete(self, contig):
        det1 = DashboardDetectorFactory(name="p1", tool="p1", version="1")
        det2 = DashboardDetectorFactory(name="p2", tool="p2", version="1")

        # Record whether the callback saw the absorbed cBGC still live.
        absorbed_alive_when_hook_fired: list[bool] = []
        pre_existing_ids: list[int] = []

        def hook() -> None:
            # Both cBGCs must still exist at hook time — the merge hasn't
            # deleted anything yet.
            absorbed_alive_when_hook_fired.append(
                ConsensusBgc.objects.filter(id__in=pre_existing_ids).count() == 2
            )

        a = CbgcAssigner(on_pre_merge=hook)
        cbgc_a, *_ = a.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=1000,
            end=4_000,
            detector_id=det1.id,
            tool_code="AAA",
        )
        cbgc_b, *_ = a.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=8_000,
            end=12_000,
            detector_id=det2.id,
            tool_code="BBB",
        )
        pre_existing_ids.extend([cbgc_a, cbgc_b])

        det3 = DashboardDetectorFactory(name="p3", tool="p3", version="1")
        a.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=3_500,
            end=9_000,
            detector_id=det3.id,
            tool_code="CCC",
        )

        assert absorbed_alive_when_hook_fired == [True], (
            "on_pre_merge should fire exactly once, before either absorbed "
            "cBGC row is deleted"
        )

    def test_no_callback_still_merges_cleanly(self, contig):
        # The callback is optional; omitting it must not regress merge.
        det1 = DashboardDetectorFactory(name="q1", tool="q1", version="1")
        det2 = DashboardDetectorFactory(name="q2", tool="q2", version="1")
        a = CbgcAssigner()
        a.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=1000,
            end=4_000,
            detector_id=det1.id,
            tool_code="AAA",
        )
        a.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=8_000,
            end=12_000,
            detector_id=det2.id,
            tool_code="BBB",
        )
        det3 = DashboardDetectorFactory(name="q3", tool="q3", version="1")
        bridge, *_ = a.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=3_500,
            end=9_000,
            detector_id=det3.id,
            tool_code="CCC",
        )
        assert ConsensusBgc.objects.filter(id=bridge).exists()


# ── disjointness invariant ────────────────────────────────────────────────────


class TestDisjointness:
    def test_assigner_leaves_no_overlapping_cbgcs(self, contig, detector, assigner):
        # 50 partially-overlapping predictions should collapse to a single
        # cBGC (or a handful of disjoint cBGCs after merge), never two
        # overlapping ones.
        for i in range(50):
            start = 1000 + 100 * i
            end = start + 5_000
            assigner.assign(
                contig_id=contig.id,
                contig_accession=contig.accession,
                start=start,
                end=end,
                detector_id=detector.id,
                tool_code="ANT",
            )
        ranges = sorted(
            (c.bgc_range.lower, c.bgc_range.upper)
            for c in ConsensusBgc.objects.filter(contig_id=contig.id)
        )
        for (l1, u1), (l2, u2) in zip(ranges, ranges[1:]):
            # Half-open intervals are disjoint iff one's upper ≤ the next's
            # lower. (PG would reject otherwise via the exclusion constraint.)
            assert u1 <= l2, f"cBGCs [{l1},{u1}) and [{l2},{u2}) overlap"


# ── bgc_number sequencing ─────────────────────────────────────────────────────


# ── hydration (cross-dataset / re-load contigs) ───────────────────────────────


class TestHydration:
    """Fresh assigners must see cBGCs a prior load already persisted.

    Later datasets in the same cycle reuse the ``discovery_contig`` row via
    ``bulk_create(ignore_conflicts=True)`` in ``load_contigs``. Without
    hydration, ``_find_overlaps`` returns ``[]`` and ``_create`` collides
    with the ``excl_cbgc_overlap`` exclusion constraint.
    """

    def test_exact_range_reuses_existing_cbgc(self, contig, detector):
        existing = ConsensusBgcFactory(
            contig=contig, start_pos=0, end_pos=10_529
        )
        fresh = CbgcAssigner()
        got_id, bgc_num, pred_acc = fresh.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=0,
            end=10_529,
            detector_id=detector.id,
            tool_code=detector.tool_name_code,
        )
        assert got_id == existing.id
        assert ConsensusBgc.objects.filter(contig_id=contig.id).count() == 1
        assert pred_acc == f"{existing.accession}.ANT.{bgc_num:02}"

    def test_overlapping_range_extends_existing_cbgc(self, contig, detector):
        existing = ConsensusBgcFactory(
            contig=contig, start_pos=1_000, end_pos=5_000
        )
        fresh = CbgcAssigner()
        got_id, *_ = fresh.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=4_500,
            end=10_000,
            detector_id=detector.id,
            tool_code=detector.tool_name_code,
        )
        assert got_id == existing.id
        cbgc = ConsensusBgc.objects.get(id=existing.id)
        assert cbgc.bgc_range.lower == 1_000
        assert cbgc.bgc_range.upper == 10_001

    def test_bgc_number_counter_continues_after_hydration(self, contig, detector):
        existing = ConsensusBgcFactory(
            contig=contig, start_pos=1_000, end_pos=10_000
        )
        # Prior load left two antiSMASH source predictions on this cBGC.
        SourceBgcPredictionFactory(
            contig=contig,
            cbgc=existing,
            detector=detector,
            start_pos=1_000,
            end_pos=5_000,
            bgc_number=1,
            prediction_accession=f"{existing.accession}.ANT.01",
        )
        SourceBgcPredictionFactory(
            contig=contig,
            cbgc=existing,
            detector=detector,
            start_pos=6_000,
            end_pos=10_000,
            bgc_number=2,
            prediction_accession=f"{existing.accession}.ANT.02",
        )
        fresh = CbgcAssigner()
        _, bgc_num, pred_acc = fresh.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=2_000,
            end=4_000,
            detector_id=detector.id,
            tool_code=detector.tool_name_code,
        )
        assert bgc_num == 3
        assert pred_acc == f"{existing.accession}.ANT.03"

    def test_disjoint_range_creates_second_cbgc_without_collision(
        self, contig, detector
    ):
        existing = ConsensusBgcFactory(
            contig=contig, start_pos=0, end_pos=5_000
        )
        fresh = CbgcAssigner()
        got_id, *_ = fresh.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=20_000,
            end=25_000,
            detector_id=detector.id,
            tool_code=detector.tool_name_code,
        )
        assert got_id != existing.id
        assert ConsensusBgc.objects.filter(contig_id=contig.id).count() == 2


class TestBgcNumberSequencing:
    def test_separate_detectors_have_independent_counters(self, contig, assigner):
        ant = DashboardDetectorFactory(
            name="a", tool="antiSMASH", version="7", tool_name_code="ANT"
        )
        gec = DashboardDetectorFactory(
            name="g", tool="GECCO", version="0.10", tool_name_code="GEC"
        )
        # First prediction creates the cBGC.
        _, _, pred_ant_1 = assigner.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=1000,
            end=10_000,
            detector_id=ant.id,
            tool_code="ANT",
        )
        # Second prediction (different detector, overlapping) extends the same cBGC.
        _, _, pred_gec_1 = assigner.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=2_000,
            end=8_000,
            detector_id=gec.id,
            tool_code="GEC",
        )
        # A second antiSMASH inside the same cBGC.
        _, _, pred_ant_2 = assigner.assign(
            contig_id=contig.id,
            contig_accession=contig.accession,
            start=3_000,
            end=5_000,
            detector_id=ant.id,
            tool_code="ANT",
        )
        assert pred_ant_1.endswith(".ANT.01")
        assert pred_gec_1.endswith(".GEC.01")
        assert pred_ant_2.endswith(".ANT.02")
