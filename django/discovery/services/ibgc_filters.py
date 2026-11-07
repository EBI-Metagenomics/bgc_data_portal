"""The iBGC filter surface shared by the iBGC endpoints and the combined query.

``IbgcFilterParams`` declares the filters once; ``apply_ibgc_filters`` turns
them into queryset narrowing and ``apply_ibgc_sort`` orders the result the way
the roster does. Lives in the services layer so the combined-query worker can
use it without importing the HTTP layer.
"""

from __future__ import annotations

from django.db.models import Exists, F, Func, IntegerField, OuterRef, Q
from django.db.models.expressions import RawSQL
from ninja import Schema

from discovery.models import IbgcNpcLabel, IntegratedBgc
from discovery.services.npc import expand_term_ids, parse_term_csv


def ibgc_span_bp():
    """SQL expression for the width of an iBGC's ``bgc_range`` in base pairs.

    ``IntegratedBgc`` stores its genomic span as a Postgres ``int4range``
    (``bgc_range``) — there are no ``start_position``/``end_position`` columns.
    The ``upper()``/``lower()`` range accessors give the half-open bounds and
    their difference is the length in bp.
    """
    return Func(F("bgc_range"), function="upper", output_field=IntegerField()) - Func(
        F("bgc_range"), function="lower", output_field=IntegerField()
    )


class IbgcFilterParams(Schema):
    """The iBGC filter surface: every chip / slider the dashboard exposes.

    Used as ``Query[IbgcFilterParams]`` by the iBGC endpoints (the fields
    become query parameters) and as the ``filters`` body of the combined query.
    Every field defaults to "no narrowing".
    """

    include_partials: bool = True
    validated_only: bool = False
    min_length_kb: float | None = None
    max_length_kb: float | None = None
    min_novelty: float | None = None
    max_novelty: float | None = None
    min_domain_novelty: float | None = None
    max_domain_novelty: float | None = None
    detector_tools: str | None = None  # CSV; "any of" on iBGC.source_tools
    source_tools: str | None = None  # deprecated alias for detector_tools
    source_names: str | None = None  # CSV of AssemblySource.name
    assembly_type: str | None = None  # metagenome / genome / region
    leaf_path_prefix: str | None = None  # GCF ltree prefix
    bgc_class: str | None = None
    npc_terms: str | None = None  # CSV of NPClassifier term ids (+descendants)
    npc_confident: bool = True  # confident labels only
    accession: str | None = None  # smart single-field accession (any kind)
    bgc_accession: str | None = None  # deprecated: BGC-only accession field
    assembly_accession: str | None = None  # deprecated: assembly-only field
    assembly_ids: str | None = None  # CSV of DashboardAssembly ids
    organism: str | None = None
    biome_lineage: str | None = None
    taxonomy_path: str | None = None
    domain_text: str | None = None  # free text over the iBGC's domain annotations


# Modifiers that only matter alongside another filter; on their own they do
# not narrow the catalogue.
_MODIFIER_FIELDS = {"npc_confident"}


def filters_active(f: IbgcFilterParams) -> bool:
    """True when any chip / slider filter departs from its default.

    Decides whether an active asset should *also* surface filtered DB rows:
    a bare asset load stays asset-only, but as soon as the user narrows the
    catalogue the DB query runs with the asset pinned on top. Empty strings
    (the frontend may send them) do not count.
    """
    for name, value in f.model_dump().items():
        if name in _MODIFIER_FIELDS or value in (None, ""):
            continue
        if value != IbgcFilterParams.model_fields[name].default:
            return True
    return False


def asset_only_mode(
    asset_token: str | None,
    parsed_ids: list[int] | None,
    filters_active: bool = False,
) -> bool:
    """Return True when the iBGC endpoints should skip the DB queryset.

    An uploaded asset narrows the dashboard to *only* its own iBGCs on a bare
    load. DB rows re-enter the response — with the asset rows still pinned on
    top — as soon as the caller either:
      * supplies an explicit ``ibgc_ids`` allow-list (a Run Query result from
        a sequence/domain/similar-iBGC search), or
      * applies any chip / slider filter (``filters_active``).
    """
    return bool(asset_token) and not parsed_ids and not filters_active


def _protein_overlap_q(acc: str) -> Q:
    """``Q`` matching iBGCs that contain a CDS named *acc* within their span.

    Both conditions target the same ``contig__cds_list`` join so the protein
    id and the range-overlap apply to the *same* CDS row — this clips out
    proteins that merely share the iBGC's contig but sit outside its
    ``bgc_range``.
    """
    return Q(
        contig__cds_list__protein_id_str__iexact=acc,
        contig__cds_list__cds_range__overlap=F("bgc_range"),
    )


def _apply_accession_filter(qs, value: str):
    """Filter an ``IntegratedBgc`` queryset by one or more smart accessions.

    The value may carry several comma-separated accessions; they are OR-ed
    together (an iBGC matches if it matches any one). Each token's kind is
    auto-detected independently, so a mixed list (e.g. an iBGC accession plus
    a protein id plus an assembly accession) works. A single token takes the
    fast path and keeps the queryset's joins intact.
    """
    tokens = [t.strip() for t in (value or "").split(",") if t.strip()]
    if not tokens:
        return qs
    if len(tokens) == 1:
        return _apply_single_accession_filter(qs, tokens[0])
    # Multiple accessions → OR via a union of per-token id sets. Resolving each
    # token against a fresh base queryset keeps the smart per-kind semantics.
    ids: set[int] = set()
    for tok in tokens:
        ids.update(
            _apply_single_accession_filter(
                IntegratedBgc.objects.all(), tok
            ).values_list("id", flat=True)
        )
    return qs.filter(id__in=ids)


def _apply_single_accession_filter(qs, value: str):
    """Filter an ``IntegratedBgc`` queryset by a single smart accession value.

    The accession kind is auto-detected (see ``classify_accession``):

    * **iBGC** (``MGYB-XXXXXX-YY``) → exact match on the iBGC accession,
      resolved through the registry so aliases / tombstones behave.
    * **prediction** (``MGYB-XXXXXX.TOOL.NN``) → exact source-prediction
      accession.
    * **cBGC** (``MGYB-XXXXXX`` / legacy ``MGYBNNNN``) → resolve via the
      registry, match the parent cBGC.
    * **assembly** (``ERZ`` / ``GCA_`` / ``GCF_`` / MIBiG ``BGC#######``) →
      substring on the assembly accession.
    * **protein** (``MGYP…``) → CDS protein id, clipped to the iBGC span.
    * **unknown** (free-form) → OR over the contig accession and protein id
      (covers contig accessions and non-MGYP protein identifiers).
    """
    from discovery.services.keyword_resolver import classify_accession

    acc = (value or "").strip()
    if not acc:
        return qs
    kind = classify_accession(acc)

    if kind == "ibgc":
        from discovery.services.accession_registry import resolve as _acc_resolve

        resolved = _acc_resolve(acc.upper())
        if resolved is not None and resolved.current_id is not None:
            return qs.filter(id=resolved.current_id)
        return qs.filter(accession__iexact=acc)

    if kind == "prediction":
        return qs.filter(
            source_predictions__prediction_accession__iexact=acc
        ).distinct()

    if kind == "cbgc":
        from discovery.services.accession_registry import resolve as _acc_resolve

        resolved = _acc_resolve(acc.upper())
        if resolved is not None and resolved.current_id is not None:
            return qs.filter(cbgc_id=resolved.current_id).distinct()
        return qs.filter(
            source_predictions__prediction_accession__icontains=acc
        ).distinct()

    if kind == "assembly":
        return qs.filter(
            source_predictions__assembly__assembly_accession__icontains=acc
        ).distinct()

    if kind == "protein":
        return qs.filter(_protein_overlap_q(acc)).distinct()

    # unknown: free-form contig accession OR (non-MGYP) protein identifier.
    return qs.filter(
        Q(contig__accession__icontains=acc) | _protein_overlap_q(acc)
    ).distinct()


def apply_ibgc_filters(qs, f: IbgcFilterParams, *, ibgc_ids: list[int] | None = None):
    """Apply iBGC-level filters to a ``IntegratedBgc`` queryset.

    Used by ``/ibgcs/count|roster|ids|scatter/`` and the combined query so the
    same filter surface applies however the initial iBGC id set was produced.

    ``f.detector_tools`` filters on the iBGC's ``f.source_tools`` JSON column
    (which stores the contributing detection tools, e.g. ``antiSMASH``,
    ``MIBiG``, ``GECCO``, ``SanntiS``). ``f.source_tools`` is kept as a
    deprecated alias so old callers continue to work.

    Joins through ``source_bgcs → assembly`` are used for
    ``f.source_names``, ``f.assembly_type``, ``f.assembly_ids`` and
    ``f.bgc_accession``. All such filters apply ``.distinct()``.
    """
    if ibgc_ids is not None:
        qs = qs.filter(id__in=ibgc_ids)
    if not f.include_partials:
        # Primary iBGCs only: row was clustered directly (not projected) and
        # has a classification run.
        qs = qs.filter(classification_run_id__isnull=False, is_partial=False)
    if f.validated_only:
        qs = qs.filter(source_predictions__is_validated=True).distinct()
    if f.min_length_kb is not None or f.max_length_kb is not None:
        qs = qs.annotate(_span_bp=ibgc_span_bp())
        if f.min_length_kb is not None:
            qs = qs.filter(_span_bp__gte=int(f.min_length_kb * 1000))
        if f.max_length_kb is not None:
            qs = qs.filter(_span_bp__lte=int(f.max_length_kb * 1000))
    if f.min_novelty is not None:
        qs = qs.filter(novelty_score__gte=f.min_novelty)
    if f.max_novelty is not None:
        qs = qs.filter(novelty_score__lte=f.max_novelty)
    if f.min_domain_novelty is not None:
        qs = qs.filter(domain_novelty__gte=f.min_domain_novelty)
    if f.max_domain_novelty is not None:
        qs = qs.filter(domain_novelty__lte=f.max_domain_novelty)
    # ── Detector tools (iBGC.source_tools JSON, "any of") ───────────────────
    detector_csv = f.detector_tools or f.source_tools
    if detector_csv:
        tools = [t.strip() for t in detector_csv.split(",") if t.strip()]
        if tools:
            # JSONField "any of" — Postgres ?| operator: at least one tool
            # in `tools` is present in the iBGC's f.source_tools array.
            tool_q = Q()
            for t in tools:
                tool_q |= Q(source_tools__contains=[t])
            qs = qs.filter(tool_q)
    if f.source_names:
        names = [n.strip() for n in f.source_names.split(",") if n.strip()]
        if names:
            qs = qs.filter(
                source_predictions__assembly__source__name__in=names
            ).distinct()
    if f.assembly_type:
        from discovery.models import AssemblyType

        type_map = {v.label: v.value for v in AssemblyType}
        key = f.assembly_type.strip().lower()
        if key in type_map:
            qs = qs.filter(
                source_predictions__assembly__assembly_type=type_map[key]
            ).distinct()
    if f.leaf_path_prefix:
        # f.leaf_path_prefix targets the cluster-family ltree on the iBGC
        # itself (e.g. "42"); see ``ClusteringRun`` outputs.
        qs = qs.filter(
            Q(gene_cluster_family__istartswith=f.leaf_path_prefix + ".")
            | Q(gene_cluster_family__iexact=f.leaf_path_prefix)
        )
    if f.bgc_class:
        # ``f.bgc_class`` is the normalised product class served by
        # /filters/bgc-classes/ and stored on ``IntegratedBgc.bgc_class``
        # (derived from source predictions' classification_path). Selecting
        # "Hybrid" subsumes "Hybrid(P+N)" (prefix match); everything else is
        # an exact match.
        if f.bgc_class == "Hybrid":
            qs = qs.filter(bgc_class__startswith="Hybrid")
        else:
            qs = qs.filter(bgc_class__iexact=f.bgc_class)
    if f.npc_terms:
        selected = parse_term_csv(f.npc_terms)
        if selected:
            # NPClassifier terms (pathway / superclass / class). A selected term
            # matches an iBGC labelled with it or with any descendant (OR across
            # the selection); ``f.npc_confident`` keeps only labels the detector
            # called confidently (curated labels always are).
            wanted = expand_term_ids(selected)
            label_qs = IbgcNpcLabel.objects.filter(
                ibgc=OuterRef("pk"), term_id__in=wanted
            )
            if f.npc_confident:
                label_qs = label_qs.filter(confident=True)
            qs = qs.filter(Exists(label_qs))
    if f.accession:
        # Single smart f.accession field: auto-detect iBGC / prediction / cBGC /
        # assembly / contig / protein and apply the matching join. Supersedes
        # the legacy ``f.bgc_accession`` + ``f.assembly_accession`` pair below
        # (still accepted for back-compat with saved deep-link URLs).
        qs = _apply_accession_filter(qs, f.accession)
    if f.bgc_accession:
        # Reuse the assembly-side MGYB-aware semantics: structured f.accession
        # → exact match; bare MGYBxxx region f.accession → match by region id
        # or alias; everything else → substring.
        acc = f.bgc_accession.strip()
        upper = acc.upper()
        if "." in upper and upper.startswith("MGYB"):
            qs = qs.filter(
                source_predictions__prediction_accession__iexact=acc
            ).distinct()
        elif upper.startswith("MGYB") and "." not in upper:
            # cBGC f.accession (e.g. MGYB-ABC123). Resolve via the registry,
            # then filter iBGCs by their cBGC parent.
            from discovery.services.accession_registry import resolve as _acc_resolve

            resolved = _acc_resolve(upper)
            if resolved is not None and resolved.current_id is not None:
                qs = qs.filter(cbgc_id=resolved.current_id).distinct()
            else:
                qs = qs.filter(
                    source_predictions__prediction_accession__icontains=acc
                ).distinct()
        else:
            qs = qs.filter(
                source_predictions__prediction_accession__icontains=acc
            ).distinct()
    if f.assembly_accession:
        qs = qs.filter(
            source_predictions__assembly__assembly_accession__icontains=f.assembly_accession.strip()
        ).distinct()
    if f.assembly_ids:
        ids = [int(x) for x in f.assembly_ids.split(",") if x.strip().isdigit()]
        if ids:
            qs = qs.filter(source_predictions__assembly_id__in=ids).distinct()
        else:
            qs = qs.none()
    if f.organism:
        qs = qs.filter(
            source_predictions__assembly__organism_name__icontains=f.organism.strip()
        ).distinct()
    if f.biome_lineage:
        qs = qs.filter(
            source_predictions__assembly__biome_path__icontains=f.biome_lineage.strip()
        ).distinct()
    if f.taxonomy_path:
        from discovery.ltree import filter_contigs_by_taxonomy

        qs = qs.filter(
            contig__in=filter_contigs_by_taxonomy(f.taxonomy_path)
        ).distinct()
    if f.domain_text:
        # Free-text fallback for landing-page keyword search: match iBGCs
        # whose contig domains carry the term in their name / description /
        # InterPro description. Scopes to the iBGC's contig (denormalised
        # ``ContigDomain.contig`` FK, single join); it does NOT yet clip to
        # the iBGC's ``bgc_range`` so a hit elsewhere on the same contig can
        # match. TODO(v2-range-overlap).
        term = f.domain_text.strip()
        if term:
            qs = qs.filter(
                Q(contig__domains__domain_name__icontains=term)
                | Q(contig__domains__domain_description__icontains=term)
                | Q(contig__domains__interpro_entry_description__icontains=term)
            ).distinct()
    return qs


def apply_ibgc_sort(qs, sort_by: str, order: str, parsed_ids: list[int] | None):
    """Order an ``IntegratedBgc`` queryset the way ``/ibgcs/roster/`` does.

    Shared by the roster and the scatter map endpoint so the map'
    top-``max_points`` sample is exactly the roster's leading rows — not an
    unrelated ``id``-stride subset. Mirrors the roster's two cases:

      * ``sort_by="similarity"`` with a caller-supplied ``ibgc_ids`` order →
        rank by ``array_position`` in that list (Find-Similar / sequence query
        results, which arrive pre-ranked by similarity / bitscore).
      * otherwise → ``ORDER BY <field> [DESC] NULLS LAST`` over the stored
        score columns (``size_kb`` via the computed span annotation). Unknown
        keys fall back to ``novelty_score``.
    """
    if sort_by == "similarity" and parsed_ids:
        ordered_ids = list(parsed_ids) if order != "asc" else list(reversed(parsed_ids))
        # Qualify the id column: the queryset may join discovery_bgc /
        # discovery_assembly when a chip filter is active, which would make a
        # bare ``id`` ambiguous to Postgres.
        ibgc_id_col = f"{IntegratedBgc._meta.db_table}.id"
        return qs.annotate(
            _sim_pos=RawSQL(
                f"array_position(%s::int[], {ibgc_id_col})",
                [ordered_ids],
                output_field=IntegerField(),
            )
        ).order_by("_sim_pos")

    sort_map = {
        "novelty_score": "novelty_score",
        "domain_novelty": "domain_novelty",
        "classification_path": "gene_cluster_family",
        "id": "id",
    }
    if sort_by == "size_kb":
        qs = qs.annotate(_size=ibgc_span_bp())
        order_field = "_size"
    else:
        order_field = sort_map.get(sort_by, "novelty_score")
    # NULLS LAST keeps unscored partials out of the head of the result.
    return qs.order_by(
        F(order_field).desc(nulls_last=True)
        if order == "desc"
        else F(order_field).asc(nulls_last=True)
    )
