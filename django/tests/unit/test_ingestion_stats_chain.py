"""Unit tests for the chained DiscoveryStats refresh after ingestion commands.

Each ingestion/loading command (``load_discovery_data``,
``build_integrated_bgcs``, ``import_clustering_results``) enqueues a
platform-overview ``DiscoveryStats`` refresh once the load succeeds, opt-out via
``--skip-discovery-stats``. These tests mock the Celery tasks (and the heavy
load functions) and assert the dispatch wiring only — no DB or broker needed.
"""

from __future__ import annotations

from unittest import mock

from django.core.management import call_command

CMD = "discovery.management.commands"


# ── load_discovery_data ──────────────────────────────────────────────────────


def _run_load(**opts):
    """Invoke load_discovery_data with run_pipeline + tasks patched out."""
    with (
        mock.patch(f"{CMD}.load_discovery_data.run_pipeline") as run_pipeline,
        mock.patch("discovery.tasks.update_protein_search_index_task") as protein,
        mock.patch("discovery.tasks.update_discovery_stats_task") as stats,
    ):
        call_command("load_discovery_data", data_dir="/tmp/x", **opts)
        run_pipeline.assert_called_once()
        return protein, stats


def test_load_chains_stats_onto_protein_index_by_default():
    protein, stats = _run_load()
    # Stats is chained as the protein-index task's success link.
    stats.si.assert_called_once_with()
    link = protein.apply_async.call_args.kwargs["link"]
    assert link is stats.si.return_value.set.return_value
    stats.si.return_value.set.assert_called_once_with(queue="celery")


def test_load_skip_discovery_stats_leaves_link_empty():
    protein, stats = _run_load(skip_discovery_stats=True)
    assert protein.apply_async.call_args.kwargs["link"] is None
    stats.si.assert_not_called()
    stats.apply_async.assert_not_called()


def test_load_skip_protein_index_dispatches_stats_directly():
    protein, stats = _run_load(skip_protein_index=True)
    protein.apply_async.assert_not_called()
    stats.apply_async.assert_called_once_with(queue="celery")


def test_load_skip_both_dispatches_nothing():
    protein, stats = _run_load(skip_protein_index=True, skip_discovery_stats=True)
    protein.apply_async.assert_not_called()
    stats.apply_async.assert_not_called()
    stats.si.assert_not_called()


# ── build_integrated_bgcs ────────────────────────────────────────────────────


def _run_build(**opts):
    with (
        mock.patch(f"{CMD}.build_integrated_bgcs.build_integrated_bgcs_task") as build,
        mock.patch(f"{CMD}.build_integrated_bgcs.update_discovery_stats_task") as stats,
    ):
        call_command("build_integrated_bgcs", **opts)
        return build, stats


def test_build_async_chains_stats_on_parent_queue():
    build, stats = _run_build(queue="scores")
    link = build.apply_async.call_args.kwargs["link"]
    assert link is stats.si.return_value.set.return_value
    stats.si.return_value.set.assert_called_once_with(queue="scores")


def test_build_async_skip_discovery_stats():
    build, stats = _run_build(skip_discovery_stats=True)
    assert build.apply_async.call_args.kwargs["link"] is None
    stats.si.assert_not_called()


def test_build_sync_dispatches_stats_after_success():
    build, stats = _run_build(sync=True, queue="scores")
    build.apply.assert_called_once()
    stats.apply_async.assert_called_once_with(queue="scores")


def test_build_sync_skip_discovery_stats():
    build, stats = _run_build(sync=True, skip_discovery_stats=True)
    stats.apply_async.assert_not_called()


# ── import_clustering_results ────────────────────────────────────────────────

_PAYLOAD = {
    "run": {"sha256": "a" * 64, "device": "cpu", "n_levels": 2},
    "hierarchy": {"ibgc_id": []},
    "partial_assignments": {"ibgc_id": []},
    "gcf_nodes": {"family_path": []},
}


def _run_import(tmp_path, **opts):
    tarball = tmp_path / "out.tgz"
    tarball.write_bytes(b"x")
    with (
        mock.patch(
            "common_core.clustering.io.read_outputs_tarball", return_value=_PAYLOAD
        ),
        mock.patch(
            f"{CMD}.import_clustering_results.Command._apply",
            return_value=mock.Mock(pk=7),
        ) as apply,
        mock.patch("discovery.tasks.update_discovery_stats_task") as stats,
    ):
        call_command("import_clustering_results", str(tarball), **opts)
        return apply, stats


def test_import_dispatches_stats_after_success(tmp_path):
    apply, stats = _run_import(tmp_path)
    apply.assert_called_once()
    stats.apply_async.assert_called_once_with(queue="scores")


def test_import_dry_run_skips_stats(tmp_path):
    apply, stats = _run_import(tmp_path, dry_run=True)
    apply.assert_not_called()
    stats.apply_async.assert_not_called()


def test_import_skip_discovery_stats(tmp_path):
    apply, stats = _run_import(tmp_path, skip_discovery_stats=True)
    apply.assert_called_once()
    stats.apply_async.assert_not_called()
