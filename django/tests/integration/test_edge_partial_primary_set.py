"""Gene-margin contig-edge rule and the primary (clusterable) iBGC set.

Contig of 100 kb, genes of 900 bp (factory ranges are ``[start, end + 1)``).
The edge test is ``min(gap) < (margin + 1) × median gene span``.
"""

from __future__ import annotations

import pytest
from discovery.models import SourceBgcPrediction
from discovery.services.clustering.primary_set import clusterable_ibgc_ids
from discovery.services.ingestion.edge_partial import mark_edge_partials
from django.core.management import call_command
from tests.factories.discovery_models import (
    ContigCdsFactory,
    DashboardContigFactory,
    DashboardDetectorFactory,
    IntegratedBgcFactory,
    SourceBgcPredictionFactory,
)

L = 100_000
GENE = 900  # factory span = end - start + 1


@pytest.fixture
def det():
    return DashboardDetectorFactory(name="SanntiS v1", tool="SanntiS")


def _call(contig, det, start, end, *, genes=(), partial=False, validated=False):
    for g in genes:
        ContigCdsFactory(contig=contig, start_pos=g, end_pos=g + GENE - 1)
    return SourceBgcPredictionFactory(
        contig=contig,
        detector=det,
        start_pos=start,
        end_pos=end,
        is_partial=partial,
        is_validated=validated,
    )


def _flags():
    return dict(SourceBgcPrediction.objects.values_list("id", "is_partial"))


@pytest.mark.django_db
def test_gene_margin_rule(det):
    def ctg():
        return DashboardContigFactory(length=L)

    # Outer gene truncated at the contig start; call boundary inside it.
    trunc = _call(ctg(), det, 300, 5_000, genes=(0, 1_000, 2_000, 3_000, 4_000))
    # Left gap 120 bp: catalogue-style edge call, no complete gene fits.
    near = _call(ctg(), det, 120, 4_000, genes=(120, 1_000, 2_000, 3_000))
    # Interior call, far from both ends.
    mid = _call(ctg(), det, 50_000, 54_000, genes=(50_000, 51_000, 52_000, 53_000))
    # Right gap 1,350 bp = 1.5 genes: edge at margin 1, not at margin 0.
    one = _call(ctg(), det, 94_000, 98_650, genes=(94_000, 95_000, 96_000, 97_000))
    # Validated (MIBiG-like) at the edge: never partial.
    val = _call(ctg(), det, 0, 2_000, validated=True, partial=True)
    # Previously flagged but interior: recomputed, cleared.
    stale = _call(
        ctg(), det, 60_000, 63_000, genes=(60_000, 61_000, 62_000), partial=True
    )

    r = mark_edge_partials(gene_margin=1, dry_run=True)
    assert r["changed"] == 0 and _flags()[trunc.id] is False  # dry run writes nothing

    mark_edge_partials(gene_margin=1)
    f = _flags()
    assert f[trunc.id] and f[near.id] and f[one.id]
    assert not f[mid.id] and not f[val.id] and not f[stale.id]

    mark_edge_partials(gene_margin=0)
    f = _flags()
    assert f[trunc.id] and f[near.id] and not f[one.id]

    # Idempotent: same margin twice changes nothing the second time.
    assert mark_edge_partials(gene_margin=0)["changed"] == 0


@pytest.mark.django_db
def test_call_ending_on_last_base_is_edge(det):
    c = DashboardContigFactory(length=L)
    # The loader stores [start, end_position + 1); end_position = L is upper L + 1.
    last = _call(c, det, 90_000, L, genes=(90_000, 91_000))
    mark_edge_partials(gene_margin=0)
    assert _flags()[last.id] is True


@pytest.mark.django_db
def test_no_cds_falls_back_to_1kb_genes(det):
    c = DashboardContigFactory(length=L)
    edge = _call(c, det, 1_500, 9_000)  # 1.5 kb gap < 2 × 1 kb
    far = _call(c, det, 40_000, 49_000)
    mark_edge_partials(gene_margin=1)
    f = _flags()
    assert f[edge.id] and not f[far.id]


@pytest.mark.django_db
def test_primary_set_size_cap_and_validated_exemption(det):
    mib = DashboardDetectorFactory(name="mibig:5", tool="mibig")

    def ibgc(start, end, *, partial=False, validated=False):
        i = IntegratedBgcFactory(start_pos=start, end_pos=end)
        SourceBgcPredictionFactory(
            contig=i.contig,
            detector=mib if validated else det,
            integrated_bgc=i,
            start_pos=start,
            end_pos=end,
            is_partial=partial,
            is_validated=validated,
        )
        return i

    small = ibgc(1_100, 40_000)
    big = ibgc(1_100, 1_100 + 200_000)  # span 200,001 bp: over the cap
    under = ibgc(1_100, 1_100 + 199_998)  # span 199,999 bp
    edge = ibgc(1_100, 9_000, partial=True)
    curated_big = ibgc(1_100, 1_100 + 600_000, validated=True)

    ids = clusterable_ibgc_ids()
    assert small.id in ids and under.id in ids and curated_big.id in ids
    assert big.id not in ids and edge.id not in ids
    assert ids == sorted(ids)


@pytest.mark.django_db
def test_command_dry_run_reports(det, capsys):
    c = DashboardContigFactory(length=L)
    _call(c, det, 0, 5_000, genes=(0, 1_000))
    call_command("mark_edge_partials", "--dry-run")
    out = capsys.readouterr().out
    assert "dry_run=True" in out and "SanntiS" in out


@pytest.mark.django_db
@pytest.mark.parametrize("margin", [0, 1, 2])
def test_python_rule_matches_sql(det, margin):
    """``is_edge_partial`` (asset upload) and ``mark_edge_partials`` (DB) agree."""
    from discovery.services.ingestion.edge_partial import is_edge_partial

    cases = [
        (300, 5_000, (0, 1_000, 2_000, 3_000, 4_000)),
        (120, 4_000, (120, 1_000, 2_000, 3_000)),
        (2_500, 9_000, (2_500, 4_000, 6_000, 8_000)),
        (50_000, 54_000, (50_000, 51_000, 52_000, 53_000)),
        (94_000, 98_650, (94_000, 95_000, 96_000, 97_000)),
        (96_000, L, (96_000, 97_000, 98_000)),
        (1_500, 9_000, ()),
    ]
    made = []
    for start, end, genes in cases:
        c = DashboardContigFactory(length=L)
        made.append((_call(c, det, start, end, genes=genes), start, end, genes))
    mark_edge_partials(gene_margin=margin)
    f = _flags()
    for call, start, end, genes in made:
        py = is_edge_partial(
            start=start,
            end=end,
            contig_length=L,
            gene_spans=[(g, g + GENE - 1) for g in genes],
            gene_margin=margin,
        )
        assert f[call.id] is py, (start, end, margin)
