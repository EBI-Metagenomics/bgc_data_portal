"""Resolve a landing-page keyword to the best-matching dashboard filter.

The resolver checks discovery models in priority order and returns the
first match as a dict containing the dashboard redirect URL and metadata.
"""

from __future__ import annotations

import re
from urllib.parse import urlencode

from django.conf import settings

# Compiled patterns for accession detection
# New format: MGYB-XXXXXX (cBGC) or MGYB-XXXXXX-YY (iBGC). Crockford base32.
_BGC_ACCESSION_RE = re.compile(
    r"^MGYB-[0-9A-HJKMNP-TV-Z]{6}(-[0-9A-HJKMNP-TV-Z]{2})?$", re.IGNORECASE
)
# Legacy format: MGYBNNNNNNNN (pre-refactor cBGC; resolved via AccessionAlias).
_BGC_LEGACY_RE = re.compile(r"^MGYB\d+$", re.IGNORECASE)
# Allow a trailing version segment (e.g. ``GCA_000001405.1``) — GCA/GCF
# accessions are commonly carried with their ``.N`` version.
_ASSEMBLY_ACCESSION_RE = re.compile(r"^(ERZ|GCA_|GCF_)[\w.]+$", re.IGNORECASE)
# MIBiG entry accession (e.g. ``BGC0000422``). MGnify ingests each MIBiG
# reference cluster as its own assembly keyed on this accession, so it must
# classify as ``assembly`` — without this it falls through to ``unknown`` and
# is mis-matched as a free-form contig/protein substring.
_MIBIG_ACCESSION_RE = re.compile(r"^BGC\d{7}$", re.IGNORECASE)
_DOMAIN_ACCESSION_RE = re.compile(r"^(PF\d{5}|TIGR\d{5})$", re.IGNORECASE)

# Narrow variants used by the unified roster "accession" filter, which must
# distinguish iBGC (MGYB-XXXXXX-YY) from bare cBGC (MGYB-XXXXXX).
_IBGC_ACCESSION_RE = re.compile(
    r"^MGYB-[0-9A-HJKMNP-TV-Z]{6}-[0-9A-HJKMNP-TV-Z]{2}$", re.IGNORECASE
)
_CBGC_ACCESSION_RE = re.compile(r"^MGYB-[0-9A-HJKMNP-TV-Z]{6}$", re.IGNORECASE)
# Mgnify protein identifier (ContigCds.protein_id_str may also carry free-form
# source ids — those fall through to the "unknown" bucket).
_PROTEIN_ACCESSION_RE = re.compile(r"^MGYP\d+$", re.IGNORECASE)


def classify_accession(value: str) -> str:
    """Classify an accession string into a roster-filter kind.

    Returns one of ``"ibgc"``, ``"prediction"``, ``"cbgc"``, ``"assembly"``,
    ``"protein"`` or ``"unknown"``. ``"unknown"`` covers free-form contig
    accessions and non-MGYP protein identifiers, which carry no
    distinguishing prefix and are matched by substring at the call site.

    Detection mirrors the semantics already used in ``_apply_ibgc_filters``:
    an MGYB accession carrying a ``.`` is a source-detector *prediction*
    (e.g. ``MGYB-AB12CD.ANT.01``); the bare form is a cBGC; the ``-YY``
    suffixed form is an iBGC.
    """
    v = (value or "").strip()
    if not v:
        return "unknown"
    if _IBGC_ACCESSION_RE.match(v):
        return "ibgc"
    upper = v.upper()
    if upper.startswith("MGYB") and "." in upper:
        return "prediction"
    if _CBGC_ACCESSION_RE.match(v) or _BGC_LEGACY_RE.match(v):
        return "cbgc"
    if _ASSEMBLY_ACCESSION_RE.match(v) or _MIBIG_ACCESSION_RE.match(v):
        return "assembly"
    if _PROTEIN_ACCESSION_RE.match(v):
        return "protein"
    return "unknown"


def _build_result(
    filter_param: str,
    filter_value: str,
    match_type: str,
) -> dict:
    """Build the resolver result dict with a dashboard redirect URL."""
    base = getattr(settings, "FORCE_SCRIPT_NAME", "") or ""
    params = urlencode(
        {"mode": "query", filter_param: filter_value, "auto_run": "true"}
    )
    return {
        "redirect_url": f"{base}/dashboard/?{params}",
        "match_type": match_type,
        "filter_param": filter_param,
        "filter_value": filter_value,
    }


def resolve_keyword(keyword: str) -> dict:
    """Resolve *keyword* to the single best-matching dashboard filter.

    Returns a dict with ``redirect_url``, ``match_type``, ``filter_param``,
    and ``filter_value``.  Always returns a result — the fallback maps
    the raw keyword to the dashboard ``search`` param.
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return _build_result("domain_text", "", "fallback")

    # Try each resolver in priority order; first match wins.
    for resolver in _RESOLVERS:
        result = resolver(keyword)
        if result is not None:
            return result

    # Fallback: a free-text biology term (e.g. "Polyketide") that matched no
    # accession/class/biome. Route it to the dashboard's ``domain_text``
    # filter, which searches the iBGC's domain annotations (name /
    # description / InterPro description) — the ``search`` param only matches
    # organism + assembly accession, so chemistry/product terms found nothing.
    return _build_result("domain_text", keyword, "fallback")


# ── Individual resolvers (private) ───────────────────────────────────────────


def _try_bgc_accession(keyword: str) -> dict | None:
    # Matches MGYB-XXXXXX (cBGC), MGYB-XXXXXX-YY (iBGC), and legacy MGYBNNNNNNNN.
    # Resolution goes through the accession registry + alias table.
    from discovery.models import AccessionAlias, AccessionRegistry

    if _BGC_ACCESSION_RE.match(keyword) or _BGC_LEGACY_RE.match(keyword):
        canonical = keyword.upper()
        if AccessionRegistry.objects.filter(accession=canonical).exists():
            return _build_result("search", canonical, "accession")
        alias = (
            AccessionAlias.objects.filter(alias_accession=canonical)
            .values_list("registry_id", flat=True)
            .first()
        )
        if alias:
            return _build_result("search", alias, "accession_alias")
    return None


def _try_assembly_accession(keyword: str) -> dict | None:
    if not (
        _ASSEMBLY_ACCESSION_RE.match(keyword)
        or _MIBIG_ACCESSION_RE.match(keyword)
    ):
        return None
    from discovery.models import DashboardAssembly

    match = (
        DashboardAssembly.objects.filter(assembly_accession__iexact=keyword)
        .values_list("assembly_accession", flat=True)
        .first()
    )
    if match:
        return _build_result("search", match, "assembly_accession")
    return None


def _try_domain_accession(keyword: str) -> dict | None:
    if not _DOMAIN_ACCESSION_RE.match(keyword):
        return None
    from discovery.models import DashboardDomain

    match = (
        DashboardDomain.objects.filter(acc__iexact=keyword)
        .values_list("acc", flat=True)
        .first()
    )
    if match:
        return _build_result("search", match, "domain_accession")
    return None


def _try_bgc_class(keyword: str) -> dict | None:
    from discovery.models import DashboardBgcClass

    # Exact match first
    exact = (
        DashboardBgcClass.objects.filter(name__iexact=keyword)
        .values_list("name", flat=True)
        .first()
    )
    if exact:
        return _build_result("bgc_class", exact, "bgc_class")

    # Partial match — pick the one with the most BGCs
    partial = (
        DashboardBgcClass.objects.filter(name__icontains=keyword)
        .order_by("-bgc_count")
        .values_list("name", flat=True)
        .first()
    )
    if partial:
        return _build_result("bgc_class", partial, "bgc_class")
    return None


def _try_detector(keyword: str) -> dict | None:
    from discovery.models import DashboardDetector

    # Exact tool name
    exact = (
        DashboardDetector.objects.filter(tool__iexact=keyword)
        .values_list("tool", flat=True)
        .first()
    )
    if exact:
        return _build_result("search", exact, "detector")

    # Partial match on human-readable name
    partial = (
        DashboardDetector.objects.filter(name__icontains=keyword)
        .values_list("tool", flat=True)
        .first()
    )
    if partial:
        return _build_result("search", partial, "detector")
    return None


def _try_biome(keyword: str) -> dict | None:
    from discovery.models import DashboardAssembly

    # Find the first distinct biome_path that contains the keyword
    match = (
        DashboardAssembly.objects.filter(biome_path__icontains=keyword)
        .exclude(biome_path="")
        .values_list("biome_path", flat=True)
        .distinct()[:1]
    )
    if match:
        # Extract the deepest matching segment as the filter value
        path = match[0]
        # Find the segment of the ltree path that contains the keyword
        segments = path.split(".")
        for seg in reversed(segments):
            if keyword.lower() in seg.lower():
                return _build_result("biome_lineage", seg, "biome")
        # If no single segment matches, use the keyword directly
        return _build_result("biome_lineage", keyword, "biome")
    return None


def _try_taxonomy(keyword: str) -> dict | None:
    from discovery.models import DashboardContig

    match = (
        DashboardContig.objects.filter(taxonomy_path__icontains=keyword)
        .exclude(taxonomy_path="")
        .values_list("taxonomy_path", flat=True)
        .distinct()[:1]
    )
    if match:
        path = match[0]
        # Build the prefix up to and including the matching segment
        segments = path.split(".")
        prefix_parts = []
        for seg in segments:
            prefix_parts.append(seg)
            if keyword.lower() in seg.lower():
                return _build_result(
                    "taxonomy_path", ".".join(prefix_parts), "taxonomy"
                )
        # Keyword spans segments or is a substring; use it directly
        return _build_result("taxonomy_path", keyword, "taxonomy")
    return None


def _try_organism_name(keyword: str) -> dict | None:
    from discovery.models import DashboardAssembly

    if DashboardAssembly.objects.filter(organism_name__icontains=keyword).exists():
        return _build_result("search", keyword, "organism_name")
    return None


def _try_natural_product(keyword: str) -> dict | None:
    from discovery.models import IbgcNaturalProduct

    if IbgcNaturalProduct.objects.filter(name__icontains=keyword).exists():
        return _build_result("search", keyword, "natural_product")
    return None


# Resolution order — first match wins.
_RESOLVERS = [
    _try_bgc_accession,
    _try_assembly_accession,
    _try_domain_accession,
    _try_bgc_class,
    _try_detector,
    _try_biome,
    _try_taxonomy,
    _try_organism_name,
    _try_natural_product,
]
