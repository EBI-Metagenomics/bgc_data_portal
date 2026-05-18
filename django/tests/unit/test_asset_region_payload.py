"""Asset region payload pins the contract RegionPlot.tsx depends on.

``RegionPlot.tsx`` (frontend) builds the per-CDS dominant GO slim colour
map exclusively from ``data.domain_list[*]`` — ``cds_list[*].pfam`` is
only used by the CDS-click protein info table. So the asset region
payload must mirror the persisted path's ``domain_list`` shape:
``parent_cds_id`` set, AA-to-NT positions computed, ``go_slim`` carried
as ``list[str]``.
"""

from __future__ import annotations

from discovery.services.asset_upload.project import VirtualNrb, _region_payload
from discovery.services.asset_upload.schemas import AssetCds, AssetDomain
from discovery.services.go_slim import go_slim_for


def _vnrb_with_domain(domain_acc: str = "PF01593") -> VirtualNrb:
    """Single CDS on the forward strand with one domain in AA[0:100]."""
    bgc_key = ("c1", 1000, 5000, "antiSMASH v7.1")
    cds = AssetCds(
        bgc_key=bgc_key,
        protein_id_str="Ga0181741_11_94",
        start_position=1100,
        end_position=1400,
        strand=1,
        protein_length=100,
    )
    domain = AssetDomain(
        bgc_key=bgc_key,
        cds_protein_id=cds.protein_id_str,
        domain_acc=domain_acc,
        domain_name="OxRed_like",
        domain_description="Oxidoreductase family",
        ref_db="Pfam",
        start_position=0,
        end_position=100,
        score=1.5,
        url="https://pfam.example/PF01593",
    )
    return VirtualNrb(
        neg_id=-1,
        contig_sha256="c1",
        contig_accession="CONTIG_1",
        assembly_accession="A1",
        organism_name="Asset organism",
        is_type_strain=False,
        start_position=1000,
        end_position=5000,
        source_tools=["antiSMASH"],
        member_bgcs=[],
        is_partial=False,
        is_validated=False,
        cds=[cds],
        domains=[domain],
    )


def test_region_payload_populates_domain_list_for_coloring():
    vnrb = _vnrb_with_domain("PF01593")
    payload = _region_payload(vnrb)

    # Per-CDS pfam list is still there (CDS click panel).
    cds = payload["cds_list"][0]
    assert cds["pfam"][0]["go_slim"] == go_slim_for("PF01593")

    # And critically — domain_list now carries the per-CDS slim for the plot.
    assert len(payload["domain_list"]) == 1
    dom = payload["domain_list"][0]
    assert dom["accession"] == "PF01593"
    assert dom["parent_cds_id"] == "Ga0181741_11_94"
    assert dom["go_slim"] == [go_slim_for("PF01593")]
    # NT coords relative to the NRB window (forward strand: CDS@1100, AA[0:100]
    # → NT[1100, 1400] → relative [100, 400] after subtracting window_start=1000).
    assert dom["start"] == 100
    assert dom["end"] == 400


def test_region_payload_empty_slim_yields_empty_list():
    """Unmapped Pfam stays in cds_list but contributes no colouring entry."""
    vnrb = _vnrb_with_domain("PF99999")  # not in pfam2goSlim.json
    payload = _region_payload(vnrb)
    dom = payload["domain_list"][0]
    assert dom["go_slim"] == []  # list[str] shape preserved; no false colour
    # cds pfam still surfaces an empty slim string (UI shows "—").
    assert payload["cds_list"][0]["pfam"][0]["go_slim"] == ""


def test_region_payload_reverse_strand_converts_coords():
    vnrb = _vnrb_with_domain("PF01593")
    vnrb.cds[0].strand = -1
    payload = _region_payload(vnrb)
    dom = payload["domain_list"][0]
    # Reverse strand: AA[0:100] over CDS NT[1100,1400] (300nt) flips to
    # NT[end - 100*3, end - 0*3] = [1100, 1400] → relative [100, 400].
    assert dom["start"] == 100
    assert dom["end"] == 400
    assert dom["strand"] == -1
